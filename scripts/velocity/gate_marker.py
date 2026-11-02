#!/usr/bin/env python3
"""Gate Marker: writes a JSON marker file on successful gate pass.

This script implements the Gate_Marker mechanism (Requirements 1.3, 1.4, 1.5, 1.8):
- Takes --kind (e.g. "unit") and --coverage <float> arguments
- Reads current HEAD sha via `git rev-parse HEAD`
- Writes a JSON file at `.velocity/markers/{kind}.json` with:
    {
      "kind": "<kind>",
      "sha": "<current HEAD sha>",
      "created_at": "<ISO-8601 UTC timestamp>",
      "coverage": <float 0..100>,
      "report_uri": "app/src/htmlcov/index.html"
    }
- Creates the `.velocity/markers/` directory if needed
- Is deterministic: same SHA + same coverage produces the same output (minus timestamp)

Exit codes:
  0 — marker written successfully
  1 — invalid arguments or git error

Usage:
  python3 scripts/velocity/gate_marker.py --kind unit --coverage 85.3
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def _repo_root() -> Path:
    """Resolve the repository root directory."""
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        # Fallback: assume this script is at scripts/velocity/gate_marker.py
        return Path(__file__).resolve().parent.parent.parent
    return Path(result.stdout.strip())


def _get_head_sha() -> str | None:
    """Get the current HEAD sha."""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Emit a gate marker JSON file on successful gate pass."
    )
    parser.add_argument(
        "--kind",
        required=True,
        help="Marker kind (e.g. 'unit', 'int')",
    )
    parser.add_argument(
        "--coverage",
        required=True,
        type=float,
        help="Coverage percentage (0..100)",
    )
    args = parser.parse_args()

    # Validate coverage range
    if not (0.0 <= args.coverage <= 100.0):
        print(
            f"ERROR: Coverage must be between 0 and 100, got {args.coverage}",
            file=sys.stderr,
        )
        return 1

    # Get HEAD sha
    sha = _get_head_sha()
    if sha is None:
        print("ERROR: Cannot resolve HEAD sha via git rev-parse HEAD", file=sys.stderr)
        return 1

    # Build the marker
    marker = {
        "kind": args.kind,
        "sha": sha,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "coverage": args.coverage,
        "report_uri": "app/src/htmlcov/index.html",
    }

    # Write the marker file
    repo_root = _repo_root()
    markers_dir = repo_root / ".velocity" / "markers"
    markers_dir.mkdir(parents=True, exist_ok=True)

    marker_path = markers_dir / f"{args.kind}.json"
    marker_path.write_text(
        json.dumps(marker, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"✅ Gate marker written: {marker_path}")
    print(f"   kind={args.kind} sha={sha[:12]}... coverage={args.coverage}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
