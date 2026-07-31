"""Case: Delete config removes rules (cleanup path).

Upload a valid config, verify reachable, delete config, verify unreachable.
This models the full lifecycle a tenant would observe.
"""

from __future__ import annotations

import pytest

from tests.integration.harness import (
    ConfigPublisher,
    TenantLogChecker,
    ReachabilityChecker,
    wait_until,
)


def _build_valid_config(account_id: str, vpc_id: str, region: str, domain: str) -> str:
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
        f"      - {domain}\n"
    )


@pytest.mark.integration
def test_delete_config_removes_rules(
    tenant_config,
    config_publisher: ConfigPublisher,
    log_checker: TenantLogChecker,
    reachability: ReachabilityChecker,
):
    """Upload valid config, verify reachable, delete config, verify unreachable.

    Steps:
        1. Upload a valid config allowing deleteme.example.com:443.
        2. Wait for success log confirming processing.
        3. Assert domain is reachable from tenant VPC.
        4. Delete the config from S3.
        5. Wait for log confirming the delete was processed.
        6. Assert domain is no longer reachable (rules removed, default-deny applies).
    """
    domain = "deleteme.example.com"
    region = tenant_config.region

    config = _build_valid_config(
        account_id=tenant_config.account_id,
        vpc_id=tenant_config.vpc_id,
        region=region,
        domain=domain,
    )

    # Step 1-2: Upload and wait for success
    key = config_publisher.put_config(region, config)
    log_checker.wait_for_success_log(key=f"{region}-config.yaml")

    # Step 3: Verify domain is reachable
    assert reachability.can_reach(domain, port=443), (
        f"Expected {domain}:443 to be reachable after config upload"
    )

    # Step 4: Delete the config
    config_publisher.delete_config(region, key)

    # Step 5: Wait for delete-flow log confirmation
    log_checker.wait_for_success_log(key="delete")

    # Step 6: Verify domain is no longer reachable
    # Use wait_until with a short poll to allow for propagation delay
    def _domain_blocked() -> bool:
        return reachability.cannot_reach(domain, port=443)

    wait_until(
        _domain_blocked,
        timeout_s=240,
        description=f"{domain}:443 to become unreachable after config deletion",
    )
