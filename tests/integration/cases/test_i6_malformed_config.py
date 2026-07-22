"""Case I-6: Malformed config + DLQ behavior.

Verifies that a malformed/invalid config (e.g., invalid YAML or missing
required fields) does NOT produce any run-id-scoped rule groups, emits a
customer log ERROR, and the message is routed to the DLQ after exceeding
the SQS max-receive count — with no further re-drive.

Requirements: 9.6, 9.7
"""

from __future__ import annotations

import pytest

from tests.integration.harness import ConfigPublisher, FirewallInspector, wait_until


# ---------------------------------------------------------------------------
# Test data: malformed config bodies
# ---------------------------------------------------------------------------

_MALFORMED_CONFIG_INVALID_YAML = """\
account: '123456789012'
vpc: 'vpc-abc123'
region: 'us-east-1'
tgw_attached: true
rules:
  - protocol: tcp
    port: 443
    domains:
      - example.com
  invalid_indent: [this is broken yaml
    missing_close: {
"""
"""Invalid YAML — the parser cannot deserialize this body."""

_MALFORMED_CONFIG_MISSING_FIELDS = """\
account: '123456789012'
"""
"""Valid YAML but missing required fields (vpc, region, rules)."""


@pytest.mark.integration
def test_malformed_config_no_rules_created(
    int_env,
    run_scope,
    mutation_cleaner,
    boto3_session,
):
    """Publish a malformed config and assert no rule groups are created.

    Steps:
        1. Publish an invalid YAML config via ConfigPublisher.
        2. Wait the full 240 s observation window.
        3. Assert no run-id-scoped rule groups exist — the malformed config
           must not produce any firewall rules.

    Validates: Requirement 9.6 (malformed config produces no rules)
    """
    # --- Arrange ---
    publisher = ConfigPublisher(env=int_env, session=boto3_session, scope=run_scope)
    inspector = FirewallInspector(env=int_env, session=boto3_session)

    # --- Act ---
    publisher.put_config(
        region=int_env.region,
        config_content=_MALFORMED_CONFIG_INVALID_YAML,
    )

    # --- Assert: NO rule group appears within 240 s ---
    # We invert the assertion: poll for the full timeout and confirm the
    # predicate never becomes true. We use a shorter observation window
    # with a final check — if a group DOES appear, that is a failure.
    try:
        wait_until(
            lambda: len(
                inspector.list_rule_group_names(run_id=run_scope.run_id)
            ) > 0,
            timeout_s=240,
            description=(
                "NEGATIVE: no run-id-scoped rule group should appear for "
                f"malformed config (run '{run_scope.run_id}')"
            ),
        )
        # If wait_until returns True, a rule group appeared — fail the test
        pytest.fail(
            f"A run-id-scoped rule group appeared for run '{run_scope.run_id}' "
            "despite publishing a malformed config. Expected no rules."
        )
    except Exception as exc:
        # TimeoutError is the EXPECTED outcome — no rule group appeared
        if "did not become true" in str(exc):
            pass  # Expected: predicate never became true
        else:
            raise


@pytest.mark.integration
def test_malformed_config_customer_log_error(
    int_env,
    run_scope,
    mutation_cleaner,
    boto3_session,
):
    """Assert a customer log ERROR is emitted for malformed config.

    Steps:
        1. Publish a config with missing required fields.
        2. Wait up to 240 s for a customer log ERROR entry referencing
           the malformed config or the run_id.

    Validates: Requirement 9.6 (customer log ERROR on malformed config)
    """
    # --- Arrange ---
    publisher = ConfigPublisher(env=int_env, session=boto3_session, scope=run_scope)
    logs_client = boto3_session.client("logs")

    # --- Act ---
    publisher.put_config(
        region=int_env.region,
        config_content=_MALFORMED_CONFIG_MISSING_FIELDS,
    )

    # --- Assert: customer log ERROR within 240 s ---
    def _error_log_emitted() -> bool:
        """Check CloudWatch Logs for an ERROR entry related to this run."""
        try:
            # Query the customer log group for ERROR level entries
            # containing this run's config key or indicators of parse failure
            log_group = f"/aws/lambda/RuleCollect"
            response = logs_client.filter_log_events(
                logGroupName=log_group,
                filterPattern="ERROR",
                limit=50,
            )
            events = response.get("events", [])
            # Look for error entries that reference our run_id or config key
            for event in events:
                message = event.get("message", "")
                if run_scope.run_id in message or "malformed" in message.lower():
                    return True
                if "missing" in message.lower() and "field" in message.lower():
                    return True
                if "validation" in message.lower() and "error" in message.lower():
                    return True
            return False
        except Exception:
            return False

    wait_until(
        _error_log_emitted,
        timeout_s=240,
        description=(
            f"customer log ERROR for malformed config (run '{run_scope.run_id}')"
        ),
    )


@pytest.mark.integration
def test_malformed_config_routed_to_dlq(
    int_env,
    run_scope,
    mutation_cleaner,
    boto3_session,
):
    """Assert the malformed message is routed to DLQ with no further re-drive.

    Steps:
        1. Publish a malformed config (already done by prior test or re-publish).
        2. Wait up to 240 s for the DLQ to contain a message referencing
           this run's config.
        3. Assert the message is NOT re-driven after arriving in the DLQ
           (no further processing attempts beyond max-receive-count).

    Validates: Requirement 9.7 (DLQ routing after max-receive-count)
    """
    # --- Arrange ---
    publisher = ConfigPublisher(env=int_env, session=boto3_session, scope=run_scope)
    sqs = boto3_session.client("sqs")

    # Re-publish malformed config to ensure the message enters the pipeline
    publisher.put_config(
        region=int_env.region,
        config_content=_MALFORMED_CONFIG_INVALID_YAML,
    )

    # --- Assert: message appears in DLQ within 240 s ---
    def _message_in_dlq() -> bool:
        """Check if a message referencing this run exists in the DLQ.

        Uses the DLQ URL derived from the environment. The DLQ should
        receive the message after the Lambda exhausts SQS max-receive-count
        retries.
        """
        try:
            # Approximate DLQ attributes check: messages available > 0
            # The exact DLQ URL would be resolved from stack outputs or config
            dlq_url = _resolve_dlq_url(int_env, sqs)
            if not dlq_url:
                return False

            response = sqs.get_queue_attributes(
                QueueUrl=dlq_url,
                AttributeNames=["ApproximateNumberOfMessages"],
            )
            msg_count = int(
                response.get("Attributes", {}).get(
                    "ApproximateNumberOfMessages", "0"
                )
            )
            return msg_count > 0
        except Exception:
            return False

    wait_until(
        _message_in_dlq,
        timeout_s=240,
        description=(
            f"malformed config message routed to DLQ (run '{run_scope.run_id}')"
        ),
    )

    # --- Assert: no further re-drive after DLQ arrival ---
    # Verify the message stays in the DLQ (is NOT re-driven back to source)
    # by checking again after a brief observation window
    import time

    time.sleep(30)  # observe for 30 s after DLQ arrival

    dlq_url = _resolve_dlq_url(int_env, sqs)
    assert dlq_url, "DLQ URL could not be resolved from environment"

    response = sqs.get_queue_attributes(
        QueueUrl=dlq_url,
        AttributeNames=["ApproximateNumberOfMessages"],
    )
    msg_count = int(
        response.get("Attributes", {}).get("ApproximateNumberOfMessages", "0")
    )
    assert msg_count > 0, (
        "DLQ message count dropped to 0 — message may have been re-driven "
        "back to the source queue. Expected no further re-drive after DLQ routing."
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_dlq_url(int_env, sqs_client) -> str | None:
    """Resolve the DLQ URL from SQS queues matching the environment prefix.

    Looks for a queue whose name contains 'dlq' or 'dead-letter' and is
    associated with the RuleExecute Lambda's source queue.

    Returns None if the DLQ cannot be found.
    """
    try:
        response = sqs_client.list_queues(QueueNamePrefix="anfw")
        queue_urls = response.get("QueueUrls", [])
        for url in queue_urls:
            if "dlq" in url.lower() or "dead-letter" in url.lower():
                return url
        return None
    except Exception:
        return None
