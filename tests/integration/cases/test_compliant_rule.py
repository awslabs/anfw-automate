"""Case: Compliant rule allows traffic (happy path).

Upload a valid config allowing a domain, verify:
1. Customer logs show successful processing
2. Domain is reachable from the tenant VPC (traffic passes NFW)
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
def test_compliant_rule_allows_traffic(
    tenant_config,
    config_publisher: ConfigPublisher,
    log_checker: TenantLogChecker,
    reachability: ReachabilityChecker,
):
    """Upload a valid config allowing example.com, verify processing and reachability.

    Steps:
        1. Build a valid config with a TGW-attached VPC allowing example.com:443.
        2. Upload via ConfigPublisher (triggers the real event pipeline).
        3. Assert: customer logs show successful processing of the config.
        4. Assert: example.com is reachable from the tenant VPC (rule applied).
    """
    domain = "example.com"
    region = tenant_config.region

    config = _build_valid_config(
        account_id=tenant_config.account_id,
        vpc_id=tenant_config.vpc_id,
        region=region,
        domain=domain,
    )

    # Act: upload config
    config_publisher.put_config(region, config)

    # Assert: success log appears in customer log group
    log_checker.wait_for_success_log(key=f"{region}-config.yaml")

    # Assert: domain is reachable from tenant VPC (traffic passes NFW)
    assert reachability.can_reach(domain, port=443), (
        f"Expected {domain}:443 to be reachable from tenant VPC after "
        "compliant rule was applied"
    )
