"""Case I-1: Happy-path create materialization.

Property 12: Create materialization — within 240 s a run-id rule group
with a rule named ``^{account}-{vpc}-[0-9a-f]{10}$`` appears after
publishing a valid TGW-attached VPC config.

Validates: Requirements 9.1
"""

from __future__ import annotations

import re

import pytest

from tests.integration.harness import ConfigPublisher, FirewallInspector, wait_until


# ---------------------------------------------------------------------------
# Expected rule-name pattern: {account_id}-{vpc_id}-<10 hex chars>
# ---------------------------------------------------------------------------

_RULE_NAME_RE = re.compile(r"^[0-9]{12}-vpc-[0-9a-f]+-[0-9a-f]{10}$")


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
        "      - example.com\n"
    )


@pytest.mark.integration
def test_happy_path_create(
    int_env,
    run_scope,
    mutation_cleaner,
    boto3_session,
):
    """Publish a valid config for a TGW-attached VPC and assert rule materialization.

    **Property 12: Create materialization**

    Steps:
        1. Build a valid config referencing the INT VPC (TGW-attached).
        2. Publish via ConfigPublisher (triggers EventBridge → Lambda pipeline).
        3. Wait up to 240 s for a run-id-scoped rule group to appear.
        4. Verify at least one rule name matches ^{account}-{vpc}-[0-9a-f]{10}$.

    Validates: Requirements 9.1
    """
    # --- Arrange ---
    publisher = ConfigPublisher(env=int_env, session=boto3_session, scope=run_scope)
    inspector = FirewallInspector(env=int_env, session=boto3_session)

    config_body = _build_valid_config(
        account_id=int_env.account_id,
        vpc_id=int_env.vpc_id,
        region=int_env.region,
    )

    # --- Act ---
    publisher.put_config(region=int_env.region, config_content=config_body)

    # --- Assert: rule group appears within 240 s ---
    def _rule_group_exists() -> bool:
        groups = inspector.list_rule_group_names(run_id=run_scope.run_id)
        return len(groups) > 0

    wait_until(
        _rule_group_exists,
        timeout_s=240,
        description=(
            f"run-id-scoped rule group for '{run_scope.run_id}' to appear"
        ),
    )

    # --- Assert: rule name matches expected pattern ---
    groups = inspector.list_rule_group_names(run_id=run_scope.run_id)
    assert groups, f"Expected at least one rule group scoped to '{run_scope.run_id}'"

    # Build the specific pattern for this account/vpc
    account = int_env.account_id
    vpc = int_env.vpc_id
    specific_pattern = re.compile(rf"^{re.escape(account)}-{re.escape(vpc)}-[0-9a-f]{{10}}$")

    rule_names_found: list[str] = []
    for group_name in groups:
        rule_names = inspector.rule_names_in_group(group_name)
        rule_names_found.extend(rule_names)

    matching = [name for name in rule_names_found if specific_pattern.match(name)]
    assert matching, (
        f"No rule name matched pattern "
        f"'^{account}-{vpc}-[0-9a-f]{{10}}$' "
        f"in rule names: {rule_names_found}"
    )
