#!/usr/bin/env python3
"""Coverage ratchet: reads COV_MIN from config.toml and enforces non-decreasing values.

This script implements the Coverage_Ratchet mechanism (Requirement 3.7):
- Reads `cov_min` from `scripts/velocity/config.toml`
- Compares against the most recently committed `cov_min` (via git)
- Rejects any configured value lower than the committed threshold
- On success, prints the current COV_MIN value (for shell interpolation)

Exit codes:
  0 — valid (same or higher); prints COV_MIN to stdout
  1 — ratchet violation (current < committed) or read error

Usage:
  python3 scripts/velocity/coverage_ratchet.py
  COV_MIN=$(python3 scripts/velocity/coverage_ratchet.py)
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

# Use tomllib (Python 3.11+) if available; otherwise fall back to a minimal
# regex-based parser that only extracts `cov_min` from the [coverage] section.
_HAS_TOMLLIB = False
try:
    import tomllib

    _HAS_TOMLLIB = True
except ModuleNotFoundError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]

        _HAS_TOMLLIB = True
    except ModuleNotFoundError:
        pass

# Path to the config file, relative to the repository root.
CONFIG_REL_PATH = "scripts/velocity/config.toml"

# Regex to extract `cov_min = <integer>` from the [coverage] section.
# Works as a fallback when tomllib is not available.
_COV_MIN_RE = re.compile(r"^\s*cov_min\s*=\s*(\d+)", re.MULTILINE)


def _parse_cov_min_from_text(text: str) -> int | None:
    """Extract cov_min from raw TOML text using regex (fallback parser)."""
    match = _COV_MIN_RE.search(text)
    if match:
        return int(match.group(1))
    return None


def _parse_cov_min_from_toml(text: str) -> int | None:
    """Extract cov_min using tomllib if available, else regex fallback."""
    if _HAS_TOMLLIB:
        try:
            config = tomllib.loads(text)
            return int(config["coverage"]["cov_min"])
        except (KeyError, TypeError, ValueError):
            return None
    return _parse_cov_min_from_text(text)


def _repo_root() -> Path:
    """Resolve the repository root directory."""
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        # Fallback: assume this script is at scripts/velocity/coverage_ratchet.py
        return Path(__file__).resolve().parent.parent.parent
    return Path(result.stdout.strip())


def _read_cov_min_from_file(path: Path) -> int:
    """Read the cov_min value from a config.toml file on disk."""
    text = path.read_text(encoding="utf-8")
    value = _parse_cov_min_from_toml(text)
    if value is None:
        raise ValueError(f"Cannot read [coverage].cov_min from {path}")
    return value


def _read_committed_cov_min(repo_root: Path) -> int | None:
    """Read the cov_min from the most recently committed version of config.toml.

    Returns None if the file does not exist in git history (first commit scenario).
    """
    result = subprocess.run(
        ["git", "show", f"HEAD:{CONFIG_REL_PATH}"],
        capture_output=True,
        text=True,
        cwd=repo_root,
        check=False,
    )
    if result.returncode != 0:
        # File not in git yet — allow any value (first commit).
        return None

    return _parse_cov_min_from_toml(result.stdout)


def main() -> int:
    repo_root = _repo_root()
    config_path = repo_root / CONFIG_REL_PATH

    # --- Read the current (working-tree) cov_min ---
    if not config_path.exists():
        print(
            f"ERROR: Config file not found: {config_path}",
            file=sys.stderr,
        )
        return 1

    try:
        current_cov_min = _read_cov_min_from_file(config_path)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    # --- Read the committed cov_min (the ratchet baseline) ---
    committed_cov_min = _read_committed_cov_min(repo_root)

    if committed_cov_min is None:
        # First commit — no baseline to compare against; allow any value.
        print(current_cov_min)
        return 0

    # --- Enforce the ratchet: current must be >= committed ---
    if current_cov_min < committed_cov_min:
        print(
            f"ERROR: Coverage ratchet violation! "
            f"Configured cov_min ({current_cov_min}) is lower than the "
            f"committed threshold ({committed_cov_min}). "
            f"COV_MIN can only stay the same or increase.",
            file=sys.stderr,
        )
        return 1

    # Valid — print the current value for shell interpolation.
    print(current_cov_min)
    return 0


if __name__ == "__main__":
    sys.exit(main())
