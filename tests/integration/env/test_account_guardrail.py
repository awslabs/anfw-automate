"""Unit tests for StableEnvResolver.assert_is_int_account (account guardrail).

These tests verify:
- Rejection when caller account != allowlisted INT account (Req 5.2, 5.7)
- Abort on STS timeout (Req 5.6)
- Acceptance when caller account matches (Req 5.1, 5.5)
- Error messages name the rejected account (Req 5.7)

**Validates: Requirements 5.1, 5.2, 5.5, 5.6, 5.7**
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ConnectTimeoutError, ReadTimeoutError

from tests.integration.env.stable import (
    AccountGuardError,
    StableEnvResolver,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_config(tmp_path: Path, account_id: str = "123456789012") -> Path:
    """Write a minimal config.toml with the given account_id."""
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        f'[int_account]\naccount_id = "{account_id}"\n'
    )
    return config_file


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAssertIsIntAccount:
    """Tests for the account guardrail."""

    @patch("tests.integration.env.stable.boto3.client")
    def test_matching_account_passes(self, mock_client: MagicMock, tmp_path: Path) -> None:
        """Guardrail passes when caller is the allowlisted account."""
        config_file = _write_config(tmp_path, "123456789012")
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {"Account": "123456789012"}
        mock_client.return_value = mock_sts

        resolver = StableEnvResolver(config_path=config_file)
        # Should not raise
        resolver.assert_is_int_account()

    @patch("tests.integration.env.stable.boto3.client")
    def test_rejects_non_allowlisted_account(self, mock_client: MagicMock, tmp_path: Path) -> None:
        """Guardrail rejects and names the wrong account (Req 5.2, 5.7)."""
        config_file = _write_config(tmp_path, "123456789012")
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {"Account": "999888777666"}
        mock_client.return_value = mock_sts

        resolver = StableEnvResolver(config_path=config_file)

        with pytest.raises(AccountGuardError, match="999888777666") as exc_info:
            resolver.assert_is_int_account()

        # Error message must name the rejected account and the allowlisted account
        msg = str(exc_info.value)
        assert "999888777666" in msg
        assert "123456789012" in msg
        assert "NOT the allowlisted INT account" in msg

    @patch("tests.integration.env.stable.boto3.client")
    def test_timeout_aborts_with_clear_message(self, mock_client: MagicMock, tmp_path: Path) -> None:
        """Guardrail aborts on STS timeout (Req 5.6)."""
        config_file = _write_config(tmp_path, "123456789012")
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.side_effect = ConnectTimeoutError(endpoint_url="https://sts.amazonaws.com")
        mock_client.return_value = mock_sts

        resolver = StableEnvResolver(config_path=config_file)

        with pytest.raises(AccountGuardError, match="timed out"):
            resolver.assert_is_int_account()

    @patch("tests.integration.env.stable.boto3.client")
    def test_read_timeout_aborts(self, mock_client: MagicMock, tmp_path: Path) -> None:
        """Guardrail aborts on read timeout (Req 5.6)."""
        config_file = _write_config(tmp_path, "123456789012")
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.side_effect = ReadTimeoutError(endpoint_url="https://sts.amazonaws.com")
        mock_client.return_value = mock_sts

        resolver = StableEnvResolver(config_path=config_file)

        with pytest.raises(AccountGuardError, match="timed out"):
            resolver.assert_is_int_account()

    def test_missing_config_file_raises(self, tmp_path: Path) -> None:
        """Guardrail fails if config.toml does not exist."""
        missing = tmp_path / "nonexistent.toml"

        with pytest.raises(AccountGuardError, match="config file not found"):
            StableEnvResolver(config_path=missing)

    def test_placeholder_account_raises(self, tmp_path: Path) -> None:
        """Guardrail fails if account_id is still the placeholder."""
        config_file = _write_config(tmp_path, "PLACEHOLDER_INT_ACCOUNT_ID")

        with pytest.raises(AccountGuardError, match="placeholder"):
            StableEnvResolver(config_path=config_file)

    def test_empty_account_raises(self, tmp_path: Path) -> None:
        """Guardrail fails if account_id is empty."""
        config_file = _write_config(tmp_path, "")

        with pytest.raises(AccountGuardError, match="placeholder"):
            StableEnvResolver(config_path=config_file)

    def test_missing_int_account_section_raises(self, tmp_path: Path) -> None:
        """Guardrail fails if [int_account] section is missing."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("[other_section]\nkey = 'value'\n")

        with pytest.raises(AccountGuardError, match="not found"):
            StableEnvResolver(config_path=config_file)

    @patch("tests.integration.env.stable.boto3.client")
    def test_sts_configured_with_5s_timeout(self, mock_client: MagicMock, tmp_path: Path) -> None:
        """STS client is configured with 5-second connect and read timeouts (Req 5.1)."""
        config_file = _write_config(tmp_path, "123456789012")
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {"Account": "123456789012"}
        mock_client.return_value = mock_sts

        resolver = StableEnvResolver(config_path=config_file)
        resolver.assert_is_int_account()

        # Verify boto3.client was called with the timeout config
        call_kwargs = mock_client.call_args
        assert call_kwargs[0][0] == "sts"
        boto_config = call_kwargs[1]["config"]
        assert boto_config.connect_timeout == 5
        assert boto_config.read_timeout == 5
        assert boto_config.retries["max_attempts"] == 0
