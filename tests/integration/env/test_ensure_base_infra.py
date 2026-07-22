"""Unit tests for StableEnvResolver.ensure_base_infra().

These tests verify:
- Idempotent no-op when CDK reports no changes (Req 6.2)
- Successful UPDATE when there are changes (Req 6.3)
- Never calls cdk destroy or replaces stable resources (Req 6.4)
- Relies on CloudFormation native rollback on failure (Req 6.7)
- Timeout handling with EnsureBaseInfraError

**Validates: Requirements 6.2, 6.3, 6.4, 6.7**
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tests.integration.env.stable import (
    EnsureBaseInfraError,
    StableEnvResolver,
    _CDK_DEPLOY_TIMEOUT_SECONDS,
    _INT_ENV_DIR,
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


def _make_resolver(tmp_path: Path) -> StableEnvResolver:
    """Create a StableEnvResolver with a valid config file."""
    config_file = _write_config(tmp_path)
    return StableEnvResolver(config_path=config_file)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEnsureBaseInfra:
    """Tests for ensure_base_infra()."""

    @patch("tests.integration.env.stable.subprocess.run")
    def test_noop_on_no_changes(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """No-op when CDK reports no changes (empty changeset). Req 6.2."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=["npx", "cdk", "deploy"],
            returncode=0,
            stdout="",
            stderr="IntBaseStack: no changes\n",
        )

        resolver = _make_resolver(tmp_path)
        # Should not raise
        resolver.ensure_base_infra()

        # Verify cdk deploy was called with correct args
        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert "cdk" in cmd
        assert "deploy" in cmd
        assert "IntBaseStack" in cmd
        assert "--require-approval" in cmd
        assert "never" in cmd

    @patch("tests.integration.env.stable.subprocess.run")
    def test_successful_update(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Successful UPDATE when there are changes. Req 6.3."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=["npx", "cdk", "deploy"],
            returncode=0,
            stdout="IntBaseStack: deploying...\nIntBaseStack: creating/updating resources\n",
            stderr="",
        )

        resolver = _make_resolver(tmp_path)
        # Should not raise
        resolver.ensure_base_infra()

    @patch("tests.integration.env.stable.subprocess.run")
    def test_failure_raises_ensure_error(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Deploy failure raises EnsureBaseInfraError with details. Req 6.7."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=["npx", "cdk", "deploy"],
            returncode=1,
            stdout="",
            stderr="Error: Stack IntBaseStack failed to deploy: UPDATE_ROLLBACK_COMPLETE\n",
        )

        resolver = _make_resolver(tmp_path)

        with pytest.raises(EnsureBaseInfraError) as exc_info:
            resolver.ensure_base_infra()

        msg = str(exc_info.value)
        assert "cdk deploy exited with status 1" in msg
        assert "CloudFormation native rollback" in msg
        assert "NOT destroyed or recreated" in msg
        assert "UPDATE_ROLLBACK_COMPLETE" in msg

    @patch("tests.integration.env.stable.subprocess.run")
    def test_timeout_raises_ensure_error(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Timeout raises EnsureBaseInfraError. Req 6.7."""
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd=["npx", "cdk", "deploy"],
            timeout=_CDK_DEPLOY_TIMEOUT_SECONDS,
            output="partial output",
            stderr="partial stderr",
        )

        resolver = _make_resolver(tmp_path)

        with pytest.raises(EnsureBaseInfraError, match="timed out"):
            resolver.ensure_base_infra()

    @patch("tests.integration.env.stable.subprocess.run")
    def test_cwd_is_int_env_dir(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """cdk deploy runs from the tests/integration/env/ directory."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="no changes", stderr=""
        )

        resolver = _make_resolver(tmp_path)
        resolver.ensure_base_infra()

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["cwd"] == str(_INT_ENV_DIR)

    @patch("tests.integration.env.stable.subprocess.run")
    def test_timeout_value_is_600s(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Deploy timeout is set to 600 seconds."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="no changes", stderr=""
        )

        resolver = _make_resolver(tmp_path)
        resolver.ensure_base_infra()

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["timeout"] == 600

    @patch("tests.integration.env.stable.subprocess.run")
    def test_never_calls_destroy(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """ensure_base_infra never invokes 'cdk destroy'. Req 6.4."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        resolver = _make_resolver(tmp_path)
        resolver.ensure_base_infra()

        # Verify the command does not contain 'destroy'
        cmd = mock_run.call_args[0][0]
        assert "destroy" not in cmd

    @patch("tests.integration.env.stable.subprocess.run")
    def test_capture_output_enabled(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """subprocess.run is called with capture_output=True and text=True."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="no changes", stderr=""
        )

        resolver = _make_resolver(tmp_path)
        resolver.ensure_base_infra()

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["capture_output"] is True
        assert call_kwargs["text"] is True

    @patch("tests.integration.env.stable.subprocess.run")
    def test_did_not_change_detected_as_noop(
        self, mock_run: MagicMock, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Alternate no-change message 'did not change' is detected as no-op."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="IntBaseStack did not change\n",
            stderr="",
        )

        resolver = _make_resolver(tmp_path)

        import logging
        with caplog.at_level(logging.INFO, logger="tests.integration.env.stable"):
            resolver.ensure_base_infra()

        assert any("no-op" in record.message for record in caplog.records)
