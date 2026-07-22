"""Unit tests for StableEnvResolver.resolve(run_id) -> IntEnv.

These tests verify:
- Successful resolution of all handles from CloudFormation exports (Req 6.5)
- Abort with ResolveError when a required handle is missing (Req 6.6)
- Abort with ResolveError when CloudFormation API fails (Req 6.6)
- No infrastructure is provisioned — resolve is read-only (Req 6.5)

**Validates: Requirements 6.5, 6.6**
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError, ConnectTimeoutError

from tests.integration.env.stable import (
    IntEnv,
    ResolveError,
    StableEnvResolver,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ACCOUNT_ID = "123456789012"
_REGION = "eu-west-1"
_NAME_PREFIX = "anfw"
_RUN_ID = "int-abcd1234-1700000000"


def _write_config(tmp_path: Path, account_id: str = _ACCOUNT_ID) -> Path:
    """Write a minimal config.toml with the given account_id."""
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        f'[int_account]\naccount_id = "{account_id}"\n'
    )
    return config_file


def _make_exports_response(
    *,
    vpc_id: str = "vpc-abc123",
    firewall_policy_arn: str = "arn:aws:network-firewall:eu-west-1:123456789012:firewall-policy/anfw-int",
    config_bucket: str = "anfw-int-config-123456789012-eu-west-1",
    xaccount_role_arn: str = "arn:aws:iam::123456789012:role/rle.anfw.xaccount.lmb.eu-west-1.int",
    event_bus_arn: str = "arn:aws:events:eu-west-1:123456789012:event-bus/anfw-int-ConfigEventBus",
    omit: list[str] | None = None,
) -> dict:
    """Build a mock list_exports paginator response with all required exports."""
    omit = omit or []
    all_exports = [
        {"Name": f"{_NAME_PREFIX}-int-vpc-id", "Value": vpc_id},
        {"Name": f"{_NAME_PREFIX}-int-firewall-policy-arn", "Value": firewall_policy_arn},
        {"Name": f"{_NAME_PREFIX}-int-config-bucket-name", "Value": config_bucket},
        {"Name": f"{_NAME_PREFIX}-int-xaccount-role-arn", "Value": xaccount_role_arn},
        {"Name": f"{_NAME_PREFIX}-int-event-bus-arn", "Value": event_bus_arn},
        # Extra export that should be ignored (not required)
        {"Name": f"{_NAME_PREFIX}-int-config-bucket-arn", "Value": "arn:aws:s3:::bucket"},
    ]
    exports = [e for e in all_exports if e["Name"] not in omit]
    return [{"Exports": exports}]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestResolveSuccess:
    """Tests for successful handle resolution from CFN exports."""

    @patch("tests.integration.env.stable.boto3.session.Session")
    @patch("tests.integration.env.stable.boto3.client")
    def test_resolves_all_handles(
        self, mock_client: MagicMock, mock_session_cls: MagicMock, tmp_path: Path
    ) -> None:
        """resolve() returns a fully populated IntEnv when all exports exist (Req 6.5)."""
        config_file = _write_config(tmp_path)

        # Mock STS for _resolve_caller_account
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {"Account": _ACCOUNT_ID}

        # Mock CloudFormation paginator for _read_cfn_exports
        mock_cfn = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = _make_exports_response()
        mock_cfn.get_paginator.return_value = mock_paginator

        def client_factory(service_name, **kwargs):
            if service_name == "sts":
                return mock_sts
            if service_name == "cloudformation":
                return mock_cfn
            raise ValueError(f"Unexpected service: {service_name}")

        mock_client.side_effect = client_factory

        # Mock session for region
        mock_session = MagicMock()
        mock_session.region_name = _REGION
        mock_session_cls.return_value = mock_session

        resolver = StableEnvResolver(config_path=config_file)
        env = resolver.resolve(_RUN_ID)

        assert isinstance(env, IntEnv)
        assert env.run_id == _RUN_ID
        assert env.account_id == _ACCOUNT_ID
        assert env.region == _REGION
        assert env.config_bucket == "anfw-int-config-123456789012-eu-west-1"
        assert env.vpc_id == "vpc-abc123"
        assert env.firewall_policy_arn == (
            "arn:aws:network-firewall:eu-west-1:123456789012:firewall-policy/anfw-int"
        )
        assert env.xaccount_role_arn == (
            "arn:aws:iam::123456789012:role/rle.anfw.xaccount.lmb.eu-west-1.int"
        )
        assert env.event_bus_arn == (
            "arn:aws:events:eu-west-1:123456789012:event-bus/anfw-int-ConfigEventBus"
        )

    @patch("tests.integration.env.stable.boto3.session.Session")
    @patch("tests.integration.env.stable.boto3.client")
    def test_does_not_provision_infrastructure(
        self, mock_client: MagicMock, mock_session_cls: MagicMock, tmp_path: Path
    ) -> None:
        """resolve() only reads — it never calls create/deploy/update APIs (Req 6.5)."""
        config_file = _write_config(tmp_path)

        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {"Account": _ACCOUNT_ID}

        mock_cfn = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = _make_exports_response()
        mock_cfn.get_paginator.return_value = mock_paginator

        def client_factory(service_name, **kwargs):
            if service_name == "sts":
                return mock_sts
            if service_name == "cloudformation":
                return mock_cfn
            raise ValueError(f"Unexpected service: {service_name}")

        mock_client.side_effect = client_factory

        mock_session = MagicMock()
        mock_session.region_name = _REGION
        mock_session_cls.return_value = mock_session

        resolver = StableEnvResolver(config_path=config_file)
        resolver.resolve(_RUN_ID)

        # Verify only read operations were called
        mock_cfn.get_paginator.assert_called_once_with("list_exports")
        # Verify no create/update/deploy calls
        mock_cfn.create_stack.assert_not_called()
        mock_cfn.update_stack.assert_not_called()
        mock_cfn.delete_stack.assert_not_called()


class TestResolveMissingHandle:
    """Tests for abort when a required handle is missing."""

    @patch("tests.integration.env.stable.boto3.session.Session")
    @patch("tests.integration.env.stable.boto3.client")
    def test_missing_vpc_id_raises(
        self, mock_client: MagicMock, mock_session_cls: MagicMock, tmp_path: Path
    ) -> None:
        """resolve() raises ResolveError naming the missing export (Req 6.6)."""
        config_file = _write_config(tmp_path)

        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {"Account": _ACCOUNT_ID}

        mock_cfn = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = _make_exports_response(
            omit=[f"{_NAME_PREFIX}-int-vpc-id"]
        )
        mock_cfn.get_paginator.return_value = mock_paginator

        def client_factory(service_name, **kwargs):
            if service_name == "sts":
                return mock_sts
            if service_name == "cloudformation":
                return mock_cfn
            raise ValueError(f"Unexpected service: {service_name}")

        mock_client.side_effect = client_factory

        mock_session = MagicMock()
        mock_session.region_name = _REGION
        mock_session_cls.return_value = mock_session

        resolver = StableEnvResolver(config_path=config_file)

        with pytest.raises(ResolveError, match="anfw-int-vpc-id"):
            resolver.resolve(_RUN_ID)

    @patch("tests.integration.env.stable.boto3.session.Session")
    @patch("tests.integration.env.stable.boto3.client")
    def test_missing_multiple_handles_names_all(
        self, mock_client: MagicMock, mock_session_cls: MagicMock, tmp_path: Path
    ) -> None:
        """resolve() names all missing exports in the error (Req 6.6)."""
        config_file = _write_config(tmp_path)

        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {"Account": _ACCOUNT_ID}

        mock_cfn = MagicMock()
        mock_paginator = MagicMock()
        # Omit multiple handles
        mock_paginator.paginate.return_value = _make_exports_response(
            omit=[
                f"{_NAME_PREFIX}-int-vpc-id",
                f"{_NAME_PREFIX}-int-event-bus-arn",
            ]
        )
        mock_cfn.get_paginator.return_value = mock_paginator

        def client_factory(service_name, **kwargs):
            if service_name == "sts":
                return mock_sts
            if service_name == "cloudformation":
                return mock_cfn
            raise ValueError(f"Unexpected service: {service_name}")

        mock_client.side_effect = client_factory

        mock_session = MagicMock()
        mock_session.region_name = _REGION
        mock_session_cls.return_value = mock_session

        resolver = StableEnvResolver(config_path=config_file)

        with pytest.raises(ResolveError) as exc_info:
            resolver.resolve(_RUN_ID)

        msg = str(exc_info.value)
        assert "anfw-int-vpc-id" in msg
        assert "anfw-int-event-bus-arn" in msg

    @patch("tests.integration.env.stable.boto3.session.Session")
    @patch("tests.integration.env.stable.boto3.client")
    def test_empty_exports_raises(
        self, mock_client: MagicMock, mock_session_cls: MagicMock, tmp_path: Path
    ) -> None:
        """resolve() raises when no exports exist (stack not deployed) (Req 6.6)."""
        config_file = _write_config(tmp_path)

        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {"Account": _ACCOUNT_ID}

        mock_cfn = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"Exports": []}]
        mock_cfn.get_paginator.return_value = mock_paginator

        def client_factory(service_name, **kwargs):
            if service_name == "sts":
                return mock_sts
            if service_name == "cloudformation":
                return mock_cfn
            raise ValueError(f"Unexpected service: {service_name}")

        mock_client.side_effect = client_factory

        mock_session = MagicMock()
        mock_session.region_name = _REGION
        mock_session_cls.return_value = mock_session

        resolver = StableEnvResolver(config_path=config_file)

        with pytest.raises(ResolveError, match="not found in CloudFormation exports"):
            resolver.resolve(_RUN_ID)


class TestResolveApiFailure:
    """Tests for abort when AWS API calls fail."""

    @patch("tests.integration.env.stable.boto3.client")
    def test_sts_timeout_raises_resolve_error(
        self, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        """resolve() raises ResolveError when STS times out (Req 6.6)."""
        config_file = _write_config(tmp_path)

        mock_sts = MagicMock()
        mock_sts.get_caller_identity.side_effect = ConnectTimeoutError(
            endpoint_url="https://sts.amazonaws.com"
        )
        mock_client.return_value = mock_sts

        resolver = StableEnvResolver(config_path=config_file)

        with pytest.raises(ResolveError, match="failed to determine caller account"):
            resolver.resolve(_RUN_ID)

    @patch("tests.integration.env.stable.boto3.session.Session")
    @patch("tests.integration.env.stable.boto3.client")
    def test_cfn_client_error_raises_resolve_error(
        self, mock_client: MagicMock, mock_session_cls: MagicMock, tmp_path: Path
    ) -> None:
        """resolve() raises ResolveError when CFN list_exports fails (Req 6.6)."""
        config_file = _write_config(tmp_path)

        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {"Account": _ACCOUNT_ID}

        mock_cfn = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access denied"}},
            "ListExports",
        )
        mock_cfn.get_paginator.return_value = mock_paginator

        def client_factory(service_name, **kwargs):
            if service_name == "sts":
                return mock_sts
            if service_name == "cloudformation":
                return mock_cfn
            raise ValueError(f"Unexpected service: {service_name}")

        mock_client.side_effect = client_factory

        mock_session = MagicMock()
        mock_session.region_name = _REGION
        mock_session_cls.return_value = mock_session

        resolver = StableEnvResolver(config_path=config_file)

        with pytest.raises(ResolveError, match="list_exports failed"):
            resolver.resolve(_RUN_ID)
