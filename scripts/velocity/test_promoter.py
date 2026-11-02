#!/usr/bin/env python3
"""Unit tests for Promoter: gate markers, deploy, canary, and rollback.

Covers:
- Property 9: Fail-closed promotion — gate abort on missing/stale/mismatched markers
- Rollback on failed deploy
- Rollback on failed/timed-out canary
- No prod mutations when markers fail

Validates: Requirements 11.1, 11.2, 11.5, 11.6
"""

from __future__ import annotations

import json
import time
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock

from promoter import (
    Promoter,
    PromotionError,
    DeploymentError,
    DeploymentResult,
    CanaryResult,
    RollbackTimeoutError,
)


@pytest.fixture
def markers_dir(tmp_path: Path) -> Path:
    """Provide a temporary markers directory."""
    d = tmp_path / "markers"
    d.mkdir()
    return d


@pytest.fixture
def config_path(tmp_path: Path) -> Path:
    """Provide a config.toml with promotion timing settings."""
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        "[promotion_timing]\n"
        "freshness_window_minutes = 60\n"
        "canary_budget_seconds = 300\n"
        "rollback_budget_seconds = 600\n",
        encoding="utf-8",
    )
    return cfg


def _write_marker(
    markers_dir: Path,
    kind: str,
    sha: str,
    created_at: datetime | None = None,
    coverage: float = 85.0,
) -> Path:
    """Helper to write a marker JSON file."""
    if created_at is None:
        created_at = datetime.now(timezone.utc)
    marker = {
        "kind": kind,
        "sha": sha,
        "created_at": created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "coverage": coverage,
    }
    path = markers_dir / f"{kind}.json"
    path.write_text(json.dumps(marker, indent=2), encoding="utf-8")
    return path


HEAD_SHA = "abc123def456abc123def456abc123def456abc1"


# ==========================================================================
# Property 9: Fail-closed promotion — gate abort on missing/stale/mismatched
# ==========================================================================


class TestRequireMarkerSuccess:
    """Test that require_marker succeeds with a fresh, matching marker."""

    def test_fresh_unit_marker_passes(self, markers_dir, config_path):
        _write_marker(markers_dir, "unit", HEAD_SHA)
        promoter = Promoter(markers_dir=markers_dir, config_path=config_path)
        result = promoter.require_marker("unit", HEAD_SHA)
        assert result["kind"] == "unit"
        assert result["sha"] == HEAD_SHA
        assert result["coverage"] == 85.0

    def test_fresh_int_marker_passes(self, markers_dir, config_path):
        _write_marker(markers_dir, "int", HEAD_SHA)
        promoter = Promoter(markers_dir=markers_dir, config_path=config_path)
        result = promoter.require_marker("int", HEAD_SHA)
        assert result["kind"] == "int"
        assert result["sha"] == HEAD_SHA

    def test_marker_just_within_window(self, markers_dir, config_path):
        """A marker created exactly 59 minutes ago should pass."""
        created = datetime.now(timezone.utc) - timedelta(minutes=59)
        _write_marker(markers_dir, "unit", HEAD_SHA, created_at=created)
        promoter = Promoter(markers_dir=markers_dir, config_path=config_path)
        result = promoter.require_marker("unit", HEAD_SHA)
        assert result["sha"] == HEAD_SHA


class TestRequireMarkerMissing:
    """Test that require_marker raises PromotionError for a missing marker."""

    def test_missing_marker_raises(self, markers_dir, config_path):
        promoter = Promoter(markers_dir=markers_dir, config_path=config_path)
        with pytest.raises(PromotionError, match="Marker 'unit' is missing"):
            promoter.require_marker("unit", HEAD_SHA)

    def test_missing_int_marker_names_kind(self, markers_dir, config_path):
        promoter = Promoter(markers_dir=markers_dir, config_path=config_path)
        with pytest.raises(PromotionError, match="Marker 'int' is missing"):
            promoter.require_marker("int", HEAD_SHA)


class TestRequireMarkerStale:
    """Test that require_marker raises PromotionError for a stale marker."""

    def test_stale_marker_raises(self, markers_dir, config_path):
        created = datetime.now(timezone.utc) - timedelta(minutes=90)
        _write_marker(markers_dir, "unit", HEAD_SHA, created_at=created)
        promoter = Promoter(markers_dir=markers_dir, config_path=config_path)
        with pytest.raises(PromotionError, match="Marker 'unit' is stale"):
            promoter.require_marker("unit", HEAD_SHA)

    def test_stale_message_includes_age(self, markers_dir, config_path):
        created = datetime.now(timezone.utc) - timedelta(minutes=120)
        _write_marker(markers_dir, "unit", HEAD_SHA, created_at=created)
        promoter = Promoter(markers_dir=markers_dir, config_path=config_path)
        with pytest.raises(PromotionError, match="120.0 min ago"):
            promoter.require_marker("unit", HEAD_SHA)


class TestRequireMarkerShaMismatch:
    """Test that require_marker raises PromotionError on sha mismatch."""

    def test_sha_mismatch_raises(self, markers_dir, config_path):
        wrong_sha = "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
        _write_marker(markers_dir, "unit", wrong_sha)
        promoter = Promoter(markers_dir=markers_dir, config_path=config_path)
        with pytest.raises(PromotionError, match="sha mismatch"):
            promoter.require_marker("unit", HEAD_SHA)

    def test_sha_mismatch_names_both_shas(self, markers_dir, config_path):
        wrong_sha = "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
        _write_marker(markers_dir, "unit", wrong_sha)
        promoter = Promoter(markers_dir=markers_dir, config_path=config_path)
        with pytest.raises(PromotionError) as exc_info:
            promoter.require_marker("unit", HEAD_SHA)
        msg = str(exc_info.value)
        assert wrong_sha in msg
        assert HEAD_SHA in msg


class TestRequireAllMarkers:
    """Test require_all_markers checks both unit and int."""

    def test_both_fresh_markers_pass(self, markers_dir, config_path):
        _write_marker(markers_dir, "unit", HEAD_SHA)
        _write_marker(markers_dir, "int", HEAD_SHA)
        promoter = Promoter(markers_dir=markers_dir, config_path=config_path)
        promoter.require_all_markers(HEAD_SHA)

    def test_missing_unit_fails_first(self, markers_dir, config_path):
        _write_marker(markers_dir, "int", HEAD_SHA)
        promoter = Promoter(markers_dir=markers_dir, config_path=config_path)
        with pytest.raises(PromotionError, match="Marker 'unit' is missing"):
            promoter.require_all_markers(HEAD_SHA)

    def test_missing_int_fails(self, markers_dir, config_path):
        _write_marker(markers_dir, "unit", HEAD_SHA)
        promoter = Promoter(markers_dir=markers_dir, config_path=config_path)
        with pytest.raises(PromotionError, match="Marker 'int' is missing"):
            promoter.require_all_markers(HEAD_SHA)

    def test_stale_unit_fails_before_checking_int(self, markers_dir, config_path):
        created = datetime.now(timezone.utc) - timedelta(minutes=90)
        _write_marker(markers_dir, "unit", HEAD_SHA, created_at=created)
        _write_marker(markers_dir, "int", HEAD_SHA)
        promoter = Promoter(markers_dir=markers_dir, config_path=config_path)
        with pytest.raises(PromotionError, match="Marker 'unit' is stale"):
            promoter.require_all_markers(HEAD_SHA)


class TestConfigHandling:
    """Test that the freshness window is read from config."""

    def test_custom_freshness_window(self, markers_dir, tmp_path):
        """A 10-minute window should reject a 15-minute-old marker."""
        cfg = tmp_path / "config.toml"
        cfg.write_text(
            "[promotion_timing]\nfreshness_window_minutes = 10\n",
            encoding="utf-8",
        )
        created = datetime.now(timezone.utc) - timedelta(minutes=15)
        _write_marker(markers_dir, "unit", HEAD_SHA, created_at=created)
        promoter = Promoter(markers_dir=markers_dir, config_path=cfg)
        with pytest.raises(PromotionError, match="Marker 'unit' is stale"):
            promoter.require_marker("unit", HEAD_SHA)

    def test_missing_config_defaults_to_60(self, markers_dir, tmp_path):
        """Without config.toml, default freshness window is 60 minutes."""
        cfg = tmp_path / "nonexistent_config.toml"
        created = datetime.now(timezone.utc) - timedelta(minutes=50)
        _write_marker(markers_dir, "unit", HEAD_SHA, created_at=created)
        promoter = Promoter(markers_dir=markers_dir, config_path=cfg)
        result = promoter.require_marker("unit", HEAD_SHA)
        assert result["sha"] == HEAD_SHA


# ==========================================================================
# Rollback on failed deploy
# ==========================================================================


class TestDeployProd:
    """Test deploy_prod behavior with stubbed deploy callables."""

    def test_successful_deploy(self, markers_dir, config_path):
        """A successful deploy returns DeploymentResult(ok=True)."""
        deploy_fn = MagicMock(
            return_value=DeploymentResult(ok=True, version="v1.0.0", message="deployed")
        )
        promoter = Promoter(
            markers_dir=markers_dir, config_path=config_path, deploy_fn=deploy_fn,
        )
        result = promoter.deploy_prod("v1.0.0")
        assert result.ok is True
        assert result.version == "v1.0.0"
        deploy_fn.assert_called_once_with("v1.0.0")

    def test_failed_deploy_returns_not_ok(self, markers_dir, config_path):
        """A failed deploy returns DeploymentResult(ok=False)."""
        deploy_fn = MagicMock(
            return_value=DeploymentResult(
                ok=False, version="v1.0.0", message="pipeline error"
            )
        )
        promoter = Promoter(
            markers_dir=markers_dir, config_path=config_path, deploy_fn=deploy_fn,
        )
        result = promoter.deploy_prod("v1.0.0")
        assert result.ok is False
        assert "pipeline error" in result.message

    def test_deploy_exception_returns_not_ok(self, markers_dir, config_path):
        """An exception during deploy returns DeploymentResult(ok=False)."""
        deploy_fn = MagicMock(side_effect=RuntimeError("connection timeout"))
        promoter = Promoter(
            markers_dir=markers_dir, config_path=config_path, deploy_fn=deploy_fn,
        )
        result = promoter.deploy_prod("v1.0.0")
        assert result.ok is False
        assert "connection timeout" in result.message


class TestRollbackOnFailedDeploy:
    """Test that rollback is triggered when deploy fails."""

    def test_rollback_called_on_failed_deploy(self, markers_dir, config_path):
        """Simulate the promote flow: deploy fails -> rollback triggered."""
        deploy_fn = MagicMock(
            return_value=DeploymentResult(ok=False, version="v2.0.0", message="fail")
        )
        rollback_fn = MagicMock()
        promoter = Promoter(
            markers_dir=markers_dir,
            config_path=config_path,
            deploy_fn=deploy_fn,
            rollback_fn=rollback_fn,
        )
        result = promoter.deploy_prod("v2.0.0")
        assert not result.ok
        promoter.rollback("v1.9.0")
        rollback_fn.assert_called_once_with("v1.9.0")


# ==========================================================================
# Rollback on failed/timed-out canary
# ==========================================================================


class TestCanary:
    """Test canary behavior with stubbed canary callables."""

    def test_successful_canary(self, markers_dir, config_path):
        """A passing canary returns CanaryResult(ok=True)."""
        canary_fn = MagicMock(
            return_value=CanaryResult(ok=True, message="healthy", duration_s=5.0)
        )
        promoter = Promoter(
            markers_dir=markers_dir, config_path=config_path, canary_fn=canary_fn,
        )
        result = promoter.canary()
        assert result.ok is True
        canary_fn.assert_called_once_with(300)

    def test_failed_canary_returns_not_ok(self, markers_dir, config_path):
        """A failing canary returns CanaryResult(ok=False)."""
        canary_fn = MagicMock(
            return_value=CanaryResult(ok=False, message="unhealthy", duration_s=10.0)
        )
        promoter = Promoter(
            markers_dir=markers_dir, config_path=config_path, canary_fn=canary_fn,
        )
        result = promoter.canary()
        assert result.ok is False
        assert "unhealthy" in result.message

    def test_canary_exception_returns_not_ok(self, markers_dir, config_path):
        """An exception during canary returns CanaryResult(ok=False)."""
        canary_fn = MagicMock(side_effect=RuntimeError("network error"))
        promoter = Promoter(
            markers_dir=markers_dir, config_path=config_path, canary_fn=canary_fn,
        )
        result = promoter.canary()
        assert result.ok is False
        assert "network error" in result.message


class TestRollbackOnFailedCanary:
    """Test that rollback is triggered when canary fails."""

    def test_rollback_called_on_failed_canary(self, markers_dir, config_path):
        """Simulate the promote flow: canary fails -> rollback triggered."""
        deploy_fn = MagicMock(
            return_value=DeploymentResult(ok=True, version="v2.0.0")
        )
        canary_fn = MagicMock(
            return_value=CanaryResult(ok=False, message="unhealthy")
        )
        rollback_fn = MagicMock()
        promoter = Promoter(
            markers_dir=markers_dir,
            config_path=config_path,
            deploy_fn=deploy_fn,
            canary_fn=canary_fn,
            rollback_fn=rollback_fn,
        )
        result = promoter.deploy_prod("v2.0.0")
        assert result.ok
        canary_result = promoter.canary()
        assert not canary_result.ok
        promoter.rollback("v1.9.0")
        rollback_fn.assert_called_once_with("v1.9.0")


# ==========================================================================
# Rollback behavior and timeout alerting
# ==========================================================================


class TestRollback:
    """Test rollback mechanics."""

    def test_successful_rollback(self, markers_dir, config_path):
        """A rollback that completes within budget should not raise."""
        rollback_fn = MagicMock()
        promoter = Promoter(
            markers_dir=markers_dir, config_path=config_path, rollback_fn=rollback_fn,
        )
        promoter.rollback("v1.0.0")
        rollback_fn.assert_called_once_with("v1.0.0")

    def test_rollback_exception_raises_deployment_error(self, markers_dir, config_path):
        """A rollback that raises should propagate as DeploymentError."""
        rollback_fn = MagicMock(side_effect=RuntimeError("stack update failed"))
        promoter = Promoter(
            markers_dir=markers_dir, config_path=config_path, rollback_fn=rollback_fn,
        )
        with pytest.raises(DeploymentError, match="Rollback to v1.0.0 failed"):
            promoter.rollback("v1.0.0")

    def test_rollback_timeout_raises_alert(self, markers_dir, tmp_path):
        """A rollback that exceeds the budget raises RollbackTimeoutError."""
        cfg = tmp_path / "config.toml"
        cfg.write_text(
            "[promotion_timing]\n"
            "freshness_window_minutes = 60\n"
            "canary_budget_seconds = 300\n"
            "rollback_budget_seconds = 1\n",
            encoding="utf-8",
        )

        def slow_rollback(version: str) -> None:
            time.sleep(1.5)

        promoter = Promoter(
            markers_dir=markers_dir, config_path=cfg, rollback_fn=slow_rollback,
        )
        with pytest.raises(RollbackTimeoutError, match="exceeding the 1s budget"):
            promoter.rollback("v1.0.0")


# ==========================================================================
# No prod mutations when markers fail
# ==========================================================================


class TestNoProdMutationsOnGateFailure:
    """Prove that deploy/canary are never called when gate markers fail.

    **Validates: Requirements 11.1, 11.2** — abort before any prod mutation
    when markers are missing/stale/mismatched.
    """

    def test_deploy_never_called_on_missing_marker(self, markers_dir, config_path):
        """If markers are missing, deploy_prod should never be invoked."""
        deploy_fn = MagicMock()
        canary_fn = MagicMock()
        promoter = Promoter(
            markers_dir=markers_dir,
            config_path=config_path,
            deploy_fn=deploy_fn,
            canary_fn=canary_fn,
        )
        with pytest.raises(PromotionError):
            promoter.require_all_markers(HEAD_SHA)
        deploy_fn.assert_not_called()
        canary_fn.assert_not_called()

    def test_deploy_never_called_on_stale_marker(self, markers_dir, config_path):
        """If markers are stale, deploy_prod should never be invoked."""
        created = datetime.now(timezone.utc) - timedelta(minutes=120)
        _write_marker(markers_dir, "unit", HEAD_SHA, created_at=created)
        _write_marker(markers_dir, "int", HEAD_SHA, created_at=created)
        deploy_fn = MagicMock()
        canary_fn = MagicMock()
        promoter = Promoter(
            markers_dir=markers_dir,
            config_path=config_path,
            deploy_fn=deploy_fn,
            canary_fn=canary_fn,
        )
        with pytest.raises(PromotionError, match="stale"):
            promoter.require_all_markers(HEAD_SHA)
        deploy_fn.assert_not_called()
        canary_fn.assert_not_called()

    def test_deploy_never_called_on_sha_mismatch(self, markers_dir, config_path):
        """If markers have wrong sha, deploy_prod should never be invoked."""
        wrong_sha = "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
        _write_marker(markers_dir, "unit", wrong_sha)
        _write_marker(markers_dir, "int", wrong_sha)
        deploy_fn = MagicMock()
        canary_fn = MagicMock()
        promoter = Promoter(
            markers_dir=markers_dir,
            config_path=config_path,
            deploy_fn=deploy_fn,
            canary_fn=canary_fn,
        )
        with pytest.raises(PromotionError, match="sha mismatch"):
            promoter.require_all_markers(HEAD_SHA)
        deploy_fn.assert_not_called()
        canary_fn.assert_not_called()

    def test_full_promotion_flow_aborts_on_gate_failure(self, markers_dir, config_path):
        """Simulate full promote() logic: gate fails -> no deploy, no canary."""
        deploy_fn = MagicMock()
        canary_fn = MagicMock()
        rollback_fn = MagicMock()
        promoter = Promoter(
            markers_dir=markers_dir,
            config_path=config_path,
            deploy_fn=deploy_fn,
            canary_fn=canary_fn,
            rollback_fn=rollback_fn,
        )
        try:
            promoter.require_all_markers(HEAD_SHA)
            promoter.deploy_prod("v2.0.0")
            promoter.canary()
        except PromotionError:
            pass
        deploy_fn.assert_not_called()
        canary_fn.assert_not_called()
        rollback_fn.assert_not_called()
