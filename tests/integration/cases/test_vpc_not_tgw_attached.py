"""Case: VPC not TGW-attached is skipped.

Upload a config referencing a VPC that is NOT attached to the Transit
Gateway. RuleCollect detects this and emits a WARN log indicating the
VPC was skipped. No rules are generated for that VPC.
"""

from __future__ import annotations

import pytest

from tests.integration.harness import (
    ConfigPublisher,
    TenantLogChecker,
    ReachabilityChecker,
)


# A VPC ID that does not exist / is not attached to TGW in the INT account.
# Uses a plausible format but won't match any real TGW attachment.
_FAKE_VPC_ID = "vpc-0000000000notattached"


def _build_config_with_fake_vpc(
    account_id: str, vpc_id: str, region: str, domain: str
) -> str:
    """Build a config referencing a VPC that is NOT TGW-attached."""
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
def test_vpc_not_tgw_attached_is_skipped(
    tenant_config,
    config_publisher: ConfigPublisher,
    log_checker: TenantLogChecker,
    reachability: ReachabilityChecker,
):
    """Upload config with non-TGW-attached VPC, verify skip log and no rule applied.

    Steps:
        1. Build a config referencing a fake VPC ID that has no TGW attachment.
        2. Upload via ConfigPublisher (triggers the real event pipeline).
        3. Assert: customer logs show a WARN/skip message for the fake VPC
           (RuleCollect checks TGW attachment and skips VPCs without one).
        4. Assert: the domain is NOT reachable (no allow rule was created for
           that VPC, so default-deny still applies).
    """
    domain = "skipped-vpc.example.com"
    region = tenant_config.region

    config = _build_config_with_fake_vpc(
        account_id=tenant_config.account_id,
        vpc_id=_FAKE_VPC_ID,
        region=region,
        domain=domain,
    )

    # Act: upload config with non-TGW-attached VPC
    config_publisher.put_config(region, config)

    # Assert: skip/warning log appears in customer log group
    log_checker.wait_for_skip_log(vpc_id=_FAKE_VPC_ID)

    # Assert: domain remains blocked (no allow rule generated for this VPC)
    assert reachability.cannot_reach(domain, port=443), (
        f"Expected {domain}:443 to be BLOCKED since the VPC {_FAKE_VPC_ID} "
        "is not TGW-attached and rules should have been skipped"
    )
