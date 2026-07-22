"""Case I-4: Delete S3 config object removes all rules.

Property 14: Delete cleanup — within 240 s all rules for the
account/region are removed after the config object is deleted from S3.

Validates: Requirements 9.4
"""

from __future__ import annotations

import pytest

from tests.integration.harness import ConfigPublisher, FirewallInspector, wait_until


def _build_valid_config(account_id: str, vpc_id: str, region: str) -> str:
    """Build a minimal valid YAML config for a TGW-attached VPC."""
    return (
        f"account: '{account_id}'\n"
        f"vpc: '{vpc_id}'\n"
        f"region: '{region}'\n"
        "tgw_attached: true\n"
        "rules:\n"
        "  - protocol: tcp\n"
        "    port: 443\n"
        "    domains:\n"
        "      - delete-test.example.com\n"
    )


@pytest.mark.integration
def test_delete_config_removes_rules(
    int_env,
    run_scope,
    mutation_cleaner,
    boto3_session,
):
    """Publish config, wait for rules, delete config, assert rules removed.

    **Property 14: Delete cleanup**

    Steps:
        1. Publish a valid config via ConfigPublisher.
        2. Wait up to 240 s for run-id-scoped rule group to appear.
        3. Delete the S3 config object via ConfigPublisher.delete_config.
        4. Wait up to 240 s for ALL rules for the account/region to be removed.

    Validates: Requirements 9.4
    """
    # --- Arrange ---
    publisher = ConfigPublisher(env=int_env, session=boto3_session, scope=run_scope)
    inspector = FirewallInspector(env=int_env, session=boto3_session)

    config_body = _build_valid_config(
        account_id=int_env.account_id,
        vpc_id=int_env.vpc_id,
        region=int_env.region,
    )

    # --- Act 1: Publish config and wait for rules to appear ---
    key = publisher.put_config(region=int_env.region, config_content=config_body)

    def _rules_exist() -> bool:
        groups = inspector.list_rule_group_names(run_id=run_scope.run_id)
        return len(groups) > 0

    wait_until(
        _rules_exist,
        timeout_s=240,
        description="run-id-scoped rule group to appear after config publish",
    )

    # Confirm rules are present
    groups_before = inspector.list_rule_group_names(run_id=run_scope.run_id)
    assert groups_before, "Expected rule groups before delete"

    # --- Act 2: Delete the config object ---
    publisher.delete_config(region=int_env.region, key=key)

    # --- Assert: all rules for the run_id are removed within 240 s ---
    def _rules_removed() -> bool:
        groups = inspector.list_rule_group_names(run_id=run_scope.run_id)
        return len(groups) == 0

    wait_until(
        _rules_removed,
        timeout_s=240,
        description=(
            f"all run-id-scoped rule groups for '{run_scope.run_id}' "
            "to be removed after config deletion"
        ),
    )

    # Final assertion
    groups_after = inspector.list_rule_group_names(run_id=run_scope.run_id)
    assert not groups_after, (
        f"Expected all rule groups removed after config delete, "
        f"but found: {groups_after}"
    )
