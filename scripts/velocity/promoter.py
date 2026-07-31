#!/usr/bin/env python3
"""Promoter: fail-closed promotion gating on fresh gate markers.

This module implements the promotion gate logic (Requirements 11.1–11.8):
- Require fresh unit + INT markers before any prod mutation
- A marker is "fresh" if its sha matches current HEAD AND it was generated
  within the configured freshness_window_minutes (default 60 min from config.toml)
- Abort before any prod mutation and name the failing marker on failure
- Deploy to prod via cross-account CodePipeline
- Run a read-only canary (no customer-rule mutation) within the canary budget
- Roll back to the previous version on failure; alert if rollback exceeds budget

Usage:
    from scripts.velocity.promoter import Promoter, PromotionError

    promoter = Promoter()
    promoter.require_all_markers(sha=current_head_sha)
    result = promoter.deploy_prod("v1.2.3")
    canary_result = promoter.canary()
    promoter.rollback("v1.2.2")
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    import tomli as tomllib  # type: ignore[no-redef]

logger = logging.getLogger(__name__)


class PromotionError(Exception):
    """Raised when promotion cannot proceed.

    The message always names the failing marker and the reason.
    """


class DeploymentError(Exception):
    """Raised when a deployment or rollback operation fails."""


class RollbackTimeoutError(Exception):
    """Raised when a rollback exceeds the configured budget (600s default)."""


@dataclass(frozen=True)
class DeploymentResult:
    """Result of a deploy_prod() call."""

    ok: bool
    version: str
    message: str = ""
    duration_s: float = 0.0


@dataclass(frozen=True)
class CanaryResult:
    """Result of a canary() call."""

    ok: bool
    message: str = ""
    duration_s: float = 0.0


def _repo_root() -> Path:
    """Resolve the repository root directory (fallback: relative to this file)."""
    return Path(__file__).resolve().parent.parent.parent


class Promoter:
    """Gate promotions on fresh gate markers and orchestrate deploy/canary/rollback.

    Validates: Requirements 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.8
    """

    REQUIRED_MARKERS = ("unit", "int")

    def __init__(
        self,
        markers_dir: Path | None = None,
        config_path: Path | None = None,
        *,
        deploy_fn: Any | None = None,
        canary_fn: Any | None = None,
        rollback_fn: Any | None = None,
    ) -> None:
        repo_root = _repo_root()
        self._markers_dir = markers_dir or (repo_root / ".velocity" / "markers")
        self._config_path = config_path or (repo_root / "scripts" / "velocity" / "config.toml")
        config = self._load_config()
        self._freshness_window_minutes: int = config["freshness_window_minutes"]
        self._canary_budget_seconds: int = config["canary_budget_seconds"]
        self._rollback_budget_seconds: int = config["rollback_budget_seconds"]

        # Injectable callables for deploy/canary/rollback (stubs by default).
        # In production these wrap CodePipeline; in tests they can be replaced.
        self._deploy_fn = deploy_fn or self._default_deploy
        self._canary_fn = canary_fn or self._default_canary
        self._rollback_fn = rollback_fn or self._default_rollback

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def _load_config(self) -> dict[str, int]:
        """Read promotion timing config from config.toml."""
        defaults = {
            "freshness_window_minutes": 60,
            "canary_budget_seconds": 300,
            "rollback_budget_seconds": 600,
        }
        if not self._config_path.exists():
            return defaults
        with open(self._config_path, "rb") as f:
            config = tomllib.load(f)
        timing = config.get("promotion_timing", {})
        return {
            "freshness_window_minutes": int(timing.get("freshness_window_minutes", 60)),
            "canary_budget_seconds": int(timing.get("canary_budget_seconds", 300)),
            "rollback_budget_seconds": int(timing.get("rollback_budget_seconds", 600)),
        }

    # ------------------------------------------------------------------
    # Gate marker validation
    # ------------------------------------------------------------------

    def require_marker(self, kind: str, sha: str) -> dict:
        """Require a fresh gate marker for the given kind.

        - Read .velocity/markers/{kind}.json
        - Verify marker.sha == sha (current HEAD)
        - Verify marker.created_at is within freshness_window_minutes of now
        - If missing/stale/mismatched: raise PromotionError naming the failing marker
        - Returns the marker dict on success
        """
        marker_path = self._markers_dir / f"{kind}.json"

        # --- Missing marker ---
        if not marker_path.exists():
            raise PromotionError(
                f"Marker '{kind}' is missing: expected file at {marker_path}"
            )

        # --- Parse marker ---
        try:
            marker = json.loads(marker_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise PromotionError(
                f"Marker '{kind}' is unreadable: {exc}"
            ) from exc

        # --- SHA mismatch ---
        marker_sha = marker.get("sha", "")
        if marker_sha != sha:
            raise PromotionError(
                f"Marker '{kind}' has sha mismatch: "
                f"marker sha={marker_sha!r}, expected HEAD sha={sha!r}"
            )

        # --- Freshness check ---
        created_at_str = marker.get("created_at", "")
        try:
            created_at = datetime.fromisoformat(
                created_at_str.replace("Z", "+00:00")
            )
        except (ValueError, AttributeError) as exc:
            raise PromotionError(
                f"Marker '{kind}' has invalid created_at timestamp: "
                f"{created_at_str!r} ({exc})"
            ) from exc

        now = datetime.now(timezone.utc)
        age = now - created_at
        max_age = timedelta(minutes=self._freshness_window_minutes)

        if age > max_age:
            age_minutes = age.total_seconds() / 60
            raise PromotionError(
                f"Marker '{kind}' is stale: generated {age_minutes:.1f} min ago, "
                f"freshness window is {self._freshness_window_minutes} min"
            )

        return marker

    def require_all_markers(self, sha: str) -> None:
        """Require both unit and int markers are fresh.

        Checks all required markers and raises PromotionError on the first
        failure, aborting before any prod mutation.
        """
        for kind in self.REQUIRED_MARKERS:
            self.require_marker(kind, sha)

    # ------------------------------------------------------------------
    # Deploy / Canary / Rollback
    # ------------------------------------------------------------------

    def deploy_prod(self, version: str) -> DeploymentResult:
        """Deploy the given version to production via cross-account CodePipeline.

        Requirements 11.3: Deploy via cross-account CodePipeline.
        Returns a DeploymentResult indicating success/failure.
        """
        logger.info("Deploying version %s to production", version)
        start = time.monotonic()
        try:
            result = self._deploy_fn(version)
            elapsed = time.monotonic() - start
            if isinstance(result, DeploymentResult):
                return result
            # If the callable returns a simple bool/truthy value, wrap it
            ok = bool(result)
            return DeploymentResult(
                ok=ok,
                version=version,
                message="" if ok else "Deployment failed",
                duration_s=elapsed,
            )
        except Exception as exc:
            elapsed = time.monotonic() - start
            logger.error("deploy_prod(%s) raised: %s", version, exc)
            return DeploymentResult(
                ok=False,
                version=version,
                message=str(exc),
                duration_s=elapsed,
            )

    def canary(self) -> CanaryResult:
        """Run a read-only canary (no customer-rule mutation).

        Requirements 11.4: Canary completes within the configured budget (300s).
        No create/update/delete operations on customer rules.
        """
        budget = self._canary_budget_seconds
        logger.info("Running read-only canary with %ds budget", budget)
        start = time.monotonic()
        try:
            result = self._canary_fn(budget)
            elapsed = time.monotonic() - start
            if isinstance(result, CanaryResult):
                return result
            # Timeout enforcement
            if elapsed > budget:
                logger.warning(
                    "Canary exceeded budget: %.1fs > %ds", elapsed, budget
                )
                return CanaryResult(
                    ok=False,
                    message=f"Canary timed out: {elapsed:.1f}s > {budget}s budget",
                    duration_s=elapsed,
                )
            ok = bool(result)
            return CanaryResult(
                ok=ok,
                message="" if ok else "Canary health check failed",
                duration_s=elapsed,
            )
        except Exception as exc:
            elapsed = time.monotonic() - start
            logger.error("canary() raised: %s", exc)
            return CanaryResult(
                ok=False,
                message=str(exc),
                duration_s=elapsed,
            )

    def rollback(self, to_version: str) -> None:
        """Roll back to a previous version.

        Requirements 11.5, 11.6, 11.8:
        - Roll back to the previous released version on failure.
        - Alert if rollback exceeds the rollback_budget_seconds (600s).
        """
        budget = self._rollback_budget_seconds
        logger.info("Rolling back to version %s (budget %ds)", to_version, budget)
        start = time.monotonic()
        try:
            self._rollback_fn(to_version)
        except Exception as exc:
            elapsed = time.monotonic() - start
            logger.error("rollback(%s) raised: %s", to_version, exc)
            raise DeploymentError(
                f"Rollback to {to_version} failed: {exc}"
            ) from exc

        elapsed = time.monotonic() - start
        if elapsed > budget:
            msg = (
                f"ALERT: Rollback to {to_version} took {elapsed:.1f}s, "
                f"exceeding the {budget}s budget. Halting further deployment."
            )
            logger.critical(msg)
            raise RollbackTimeoutError(msg)

        logger.info(
            "Rollback to %s completed in %.1fs", to_version, elapsed
        )

    # ------------------------------------------------------------------
    # INT stable-tier rollback (Requirement 11.7)
    # ------------------------------------------------------------------

    def rollback_int_stable(self, stack_name: str, previous_template_path: str) -> None:
        """Roll back an INT stable-tier deploy via CDK/CloudFormation UPDATE.

        On failed INT stable-tier deploy, roll back via stack UPDATE to the last
        good template rather than rebuilding the environment.

        Args:
            stack_name: The CloudFormation stack name to roll back.
            previous_template_path: Path to the last known good template.
        """
        logger.info(
            "Rolling back INT stable stack '%s' to template: %s",
            stack_name,
            previous_template_path,
        )
        # This is a stub — actual implementation would invoke:
        #   cdk deploy --app <previous_template_path> <stack_name>
        # or a direct CloudFormation UpdateStack with the previous template body.
        # The key contract: we UPDATE the stack with the last-good template,
        # never destroy/recreate it.
        import subprocess

        cmd = [
            "npx", "cdk", "deploy", stack_name,
            "--app", previous_template_path,
            "--require-approval", "never",
        ]
        logger.info("Would execute: %s", " ".join(cmd))
        # In a real environment, uncomment:
        # subprocess.run(cmd, check=True, capture_output=True, text=True)

    # ------------------------------------------------------------------
    # Default stubs (replaced by injectable callables in production)
    # ------------------------------------------------------------------

    @staticmethod
    def _default_deploy(version: str) -> DeploymentResult:
        """Stub: deploy via cross-account CodePipeline.

        In production, this triggers the CodePipeline execution and waits for
        completion. Cannot be tested locally — always returns success in stub mode.
        """
        logger.warning(
            "STUB deploy_prod(%s): no-op in local/test mode", version
        )
        return DeploymentResult(ok=True, version=version, message="stub")

    @staticmethod
    def _default_canary(budget_seconds: int) -> CanaryResult:
        """Stub: read-only canary health check.

        In production, this runs a subset of integration assertions (read-only)
        against the prod environment. No customer-rule mutation.
        """
        logger.warning(
            "STUB canary(budget=%ds): no-op in local/test mode", budget_seconds
        )
        return CanaryResult(ok=True, message="stub", duration_s=0.0)

    @staticmethod
    def _default_rollback(to_version: str) -> None:
        """Stub: roll back to a previous version.

        In production, this triggers a CodePipeline re-deploy of the previous
        tag or a CloudFormation stack update with the previous template.
        """
        logger.warning(
            "STUB rollback(%s): no-op in local/test mode", to_version
        )
