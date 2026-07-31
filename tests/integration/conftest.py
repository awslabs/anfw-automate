"""Integration test session fixtures.

Provides tenant-identity fixtures using the tenant-observable outcomes
model. Cleanup is handled by deleting configs from S3 (triggering the
real delete flow) rather than a manual MutationCleaner.

Fixtures:
- boto3_session: authenticated session for the INT account
- tenant_config: resolved from IntBaseStack CFN exports (bucket, vpc, log group)
- config_publisher: publishes/deletes configs to tenant S3
- log_checker: polls customer CloudWatch logs
- reachability: checks network reachability from tenant VPC via probe Lambda
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import boto3
import pytest

from tests.integration.env.stable import StableEnvResolver
from tests.integration.harness.config_publisher import ConfigPublisher
from tests.integration.harness.tenant_logs import TenantLogChecker
from tests.integration.harness.reachability import ReachabilityChecker

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Serial execution marker — integration tests run serially by default
# ---------------------------------------------------------------------------


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Mark all integration test items for serial execution."""
    for item in items:
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.serial)


# ---------------------------------------------------------------------------
# Data model for resolved tenant config
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TenantConfig:
    """Immutable handle set resolved from the deployed IntBaseStack."""

    account_id: str
    region: str
    config_bucket: str
    vpc_id: str
    log_group_name: str
    probe_function_name: str
    firewall_policy_arn: str


# ---------------------------------------------------------------------------
# Session-scoped fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def boto3_session() -> boto3.Session:
    """Provide a boto3.Session for the INT account."""
    return boto3.Session()


@pytest.fixture(scope="session")
def tenant_config(boto3_session: boto3.Session) -> TenantConfig:
    """Resolve tenant config from IntBaseStack CFN exports.

    Calls assert_is_int_account() first to guarantee safety.
    """
    resolver = StableEnvResolver()
    resolver.assert_is_int_account()

    name_prefix = resolver._load_name_prefix()
    stage = resolver._load_stage()
    region = boto3_session.region_name or "eu-west-1"

    sts = boto3_session.client("sts")
    account_id = sts.get_caller_identity()["Account"]

    export_map = resolver._read_cfn_exports(name_prefix, region)

    config_bucket = export_map.get(f"{name_prefix}-int-config-bucket-name-{stage}", "")
    vpc_id = export_map.get(f"{name_prefix}-int-tenant-vpc-id-{stage}", "")
    firewall_policy_arn = export_map.get(f"{name_prefix}-int-firewall-policy-arn-{stage}", "")
    probe_function_name = export_map.get(f"{name_prefix}-int-probe-function-name-{stage}", "")
    log_group_name = f"cw-{name_prefix}-CustomerLog-{stage}"

    assert config_bucket, f"Missing export: {name_prefix}-int-config-bucket-name-{stage}"
    assert vpc_id, f"Missing export: {name_prefix}-int-tenant-vpc-id-{stage}"

    return TenantConfig(
        account_id=account_id,
        region=region,
        config_bucket=config_bucket,
        vpc_id=vpc_id,
        log_group_name=log_group_name,
        probe_function_name=probe_function_name,
        firewall_policy_arn=firewall_policy_arn,
    )


# ---------------------------------------------------------------------------
# Function-scoped fixtures (per-test isolation via config cleanup)
# ---------------------------------------------------------------------------


@pytest.fixture
def config_publisher(
    boto3_session: boto3.Session,
    tenant_config: TenantConfig,
) -> ConfigPublisher:
    """Provide a ConfigPublisher that auto-cleans up after each test."""
    publisher = ConfigPublisher(
        session=boto3_session,
        bucket_name=tenant_config.config_bucket,
    )
    yield publisher
    logger.info("config_publisher teardown: cleaning up uploaded configs")
    publisher.cleanup_all()


@pytest.fixture
def log_checker(
    boto3_session: boto3.Session,
    tenant_config: TenantConfig,
) -> TenantLogChecker:
    """Provide a TenantLogChecker for the customer log group."""
    return TenantLogChecker(
        session=boto3_session,
        log_group_name=tenant_config.log_group_name,
    )


@pytest.fixture
def reachability(
    boto3_session: boto3.Session,
    tenant_config: TenantConfig,
) -> ReachabilityChecker:
    """Provide a ReachabilityChecker using the probe Lambda in the tenant VPC."""
    return ReachabilityChecker(
        session=boto3_session,
        checker_function_name=tenant_config.probe_function_name,
    )
