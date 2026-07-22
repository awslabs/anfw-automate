"""Case I-8: Reserved default-deny group present.

Property 15: Reserved default-deny invariant — after any successful run
(e.g., I-1 happy-path create or equivalent) a ``-reserved`` default-deny
rule group exists in Network Firewall.

This test uses ``FirewallInspector.reserved_group_exists()`` to verify the
invariant holds. It depends on a prior successful config publish (I-1 or
equivalent) having run during the same session.

Validates: Requirements 9.9
"""

from __future__ import annotations

import pytest

from tests.integration.harness import ConfigPublisher, FirewallInspector, wait_until


def _build_valid_config(account_id: str, vpc_id: str, region: str) -> str:
    """Build a minimal valid YAML config for a TGW-attached VPC.

    Used to trigger a successful run so the reserved default-deny group
    invariant can be verified.
    """
    return (
        f"account: '{account_id}'\n"
        f"vpc: '{vpc_id}'\n"
        f"region: '{region}'\n"
        "tgw_attached: true\n"
        "rules:\n"
        "  - protocol: tcp\n"
        "    port: 443\n"
        "    domains:\n"
        "      - example.com\n"
    )


@pytest.mark.integration
def test_reserved_default_deny_group_exists(
    int_env,
    run_scope,
    mutation_cleaner,
    boto3_session,
):
    """After a successful run, assert a -reserved default-deny rule group exists.

    **Property 15: Reserved default-deny invariant**

    Steps:
        1. Publish a valid config to trigger a successful run (equivalent
           to I-1 happy-path create).
        2. Wait for the run-id rule group to materialize (confirms success).
        3. Assert that a ``-reserved`` default-deny rule group exists using
           ``FirewallInspector.reserved_group_exists()``.

    The reserved default-deny group is a system-managed rule group that must
    always be present after any successful automation run. It provides the
    baseline deny-all posture that custom rules selectively open.

    Validates: Requirements 9.9
    """
    # --- Arrange ---
    publisher = ConfigPublisher(env=int_env, session=boto3_session, scope=run_scope)
    inspector = FirewallInspector(env=int_env, session=boto3_session)

    config_body = _build_valid_config(
        account_id=int_env.account_id,
        vpc_id=int_env.vpc_id,
        region=int_env.region,
    )

    # --- Act: trigger a successful run ---
    publisher.put_config(region=int_env.region, config_content=config_body)

    # Wait for the run to succeed (rule group appears)
    wait_until(
        lambda: len(
            inspector.list_rule_group_names(run_id=run_scope.run_id)
        ) > 0,
        timeout_s=240,
        description=(
            f"run-id-scoped rule group for '{run_scope.run_id}' to appear "
            "(precondition for reserved group check)"
        ),
    )

    # --- Assert: reserved default-deny group exists ---
    assert inspector.reserved_group_exists(), (
        "Expected a '-reserved' default-deny rule group to exist after a "
        "successful run, but FirewallInspector.reserved_group_exists() "
        "returned False. The reserved default-deny group is a system invariant "
        "that must always be present."
    )
