#!/usr/bin/env python3
"""Promotion script: guarded promote flow (unit → INT → prod).

This script implements the full promotion orchestration (Requirements 11.1–11.6):
1. Gets current HEAD sha
2. Calls Promoter.require_all_markers(sha) to enforce freshness gates
3. If fresh: proceeds with deploy_prod → canary → done
4. On failure: calls rollback
5. Writes the INT Gate_Marker on INT success using gate_marker.py

Usage:
    python3 scripts/velocity/promote.py --version v1.2.3 --prev v1.2.2

    # With INT gate marker only (for use after successful INT run):
    python3 scripts/velocity/promote.py --int-gate-only --coverage 85.0

Exit codes:
    0 — promotion completed successfully (or INT gate marker written)
    1 — gate marker validation failed (missing/stale/mismatched)
    2 — deployment failed and rollback was triggered
    3 — canary failed and rollback was triggered
    4 — rollback itself failed or timed out
    5 — invalid arguments or unexpected error
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from pathlib import Path

# Allow importing sibling modules when run as a script
sys.path.insert(0, str(Path(__file__).resolve().parent))

from promoter import (  # noqa: E402
    Promoter,
    PromotionError,
    DeploymentError,
    RollbackTimeoutError,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("promote")


def _get_head_sha() -> str | None:
    """Get the current HEAD sha via git."""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _write_int_gate_marker(coverage: float) -> int:
    """Write the INT gate marker using gate_marker.py."""
    gate_marker_script = Path(__file__).resolve().parent / "gate_marker.py"
    result = subprocess.run(
        [
            sys.executable,
            str(gate_marker_script),
            "--kind", "int",
            "--coverage", str(coverage),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        logger.error("Failed to write INT gate marker: %s", result.stderr)
        return 1
    logger.info("INT gate marker written: %s", result.stdout.strip())
    return 0


def promote(version: str, prev: str) -> int:
    """Execute the guarded promotion flow.

    Args:
        version: The version to deploy (e.g. "v1.2.3").
        prev: The previous version to roll back to on failure (e.g. "v1.2.2").

    Returns:
        Exit code (0=success, 1=gate fail, 2=deploy fail, 3=canary fail, 4=rollback fail).
    """
    sha = _get_head_sha()
    if sha is None:
        logger.error("Cannot resolve HEAD sha via git rev-parse HEAD")
        return 5

    logger.info("Promotion attempt: version=%s prev=%s sha=%s", version, prev, sha[:12])

    # --- Gate check: require fresh unit + INT markers ---
    promoter = Promoter()
    try:
        promoter.require_all_markers(sha)
    except PromotionError as exc:
        logger.error("Gate check failed: %s", exc)
        return 1

    logger.info("All gate markers are fresh. Proceeding with deployment.")

    # --- Deploy ---
    deploy_result = promoter.deploy_prod(version)
    if not deploy_result.ok:
        logger.error(
            "Deployment failed: %s. Triggering rollback to %s.",
            deploy_result.message,
            prev,
        )
        try:
            promoter.rollback(prev)
        except (DeploymentError, RollbackTimeoutError) as exc:
            logger.critical("Rollback also failed: %s", exc)
            return 4
        return 2

    logger.info("Deployment succeeded. Running canary...")

    # --- Canary ---
    canary_result = promoter.canary()
    if not canary_result.ok:
        logger.error(
            "Canary failed: %s. Triggering rollback to %s.",
            canary_result.message,
            prev,
        )
        try:
            promoter.rollback(prev)
        except (DeploymentError, RollbackTimeoutError) as exc:
            logger.critical("Rollback also failed: %s", exc)
            return 4
        return 3

    logger.info(
        "Promotion complete: version=%s deployed and canary passed (%.1fs).",
        version,
        canary_result.duration_s,
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Guarded promotion flow: gate check → deploy → canary → done."
    )
    parser.add_argument(
        "--version",
        help="Version to deploy (e.g. v1.2.3)",
    )
    parser.add_argument(
        "--prev",
        help="Previous version to rollback to on failure (e.g. v1.2.2)",
    )
    parser.add_argument(
        "--int-gate-only",
        action="store_true",
        help="Only write the INT gate marker (for use after successful INT run)",
    )
    parser.add_argument(
        "--coverage",
        type=float,
        default=0.0,
        help="Coverage percentage for INT gate marker (used with --int-gate-only)",
    )
    args = parser.parse_args()

    # INT gate marker mode: just write the marker and exit
    if args.int_gate_only:
        return _write_int_gate_marker(args.coverage)

    # Full promotion mode: require --version and --prev
    if not args.version or not args.prev:
        parser.error("--version and --prev are required for full promotion")
        return 5

    return promote(args.version, args.prev)


if __name__ == "__main__":
    sys.exit(main())
