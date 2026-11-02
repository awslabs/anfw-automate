"""Case: Non-compliant rule rejected (negative path).

Upload a config with a reserved keyword, verify:
1. Customer logs show a format error
2. Domain is NOT reachable (rule was not applied, default-deny blocks traffic)
"""

from __future__ import annotations

import pytest

from tests.integration.harness import (
    ConfigPublisher,
    TenantLogChecker,
    ReachabilityChecker,
)


def _build_invalid_config(
    account_id: str, vpc_id: str, region: str, domain: str
) -> str:
    """Build a config containing a reserved keyword (sid:) in a custom rule."""
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
        "    custom_rule: 'alert tcp any any -> any any (sid:1000001; msg:\"test\";)'\n"
    )


@pytest.mark.integration
def test_non_compliant_rule_rejected(
    tenant_config,
    config_publisher: ConfigPublisher,
    log_checker: TenantLogChecker,
    reachability: ReachabilityChecker,
):
    """Upload a config with reserved keyword, verify rejection and unreachability.

    Steps:
        1. Build a config with a custom rule containing ``sid:`` (reserved).
        2. Upload via ConfigPublisher (triggers the real event pipeline).
        3. Assert: customer logs show a format error / reserved keyword rejection.
        4. Assert: domain is NOT reachable (blocked by default-deny since the
           invalid rule was never applied).
    """
    domain = "malicious.example.com"
    region = tenant_config.region

    config = _build_invalid_config(
        account_id=tenant_config.account_id,
        vpc_id=tenant_config.vpc_id,
        region=region,
        domain=domain,
    )

    # Act: upload invalid config
    config_publisher.put_config(region, config)

    # Assert: error log appears in customer log group
    log_checker.wait_for_error_log(pattern="FormatError|reserved|Invalid Format")

    # Assert: domain is NOT reachable (blocked by default-deny)
    assert reachability.cannot_reach(domain, port=443), (
        f"Expected {domain}:443 to be BLOCKED from tenant VPC since "
        "the non-compliant rule was rejected"
    )
