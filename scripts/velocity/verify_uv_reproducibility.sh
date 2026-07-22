#!/usr/bin/env bash
# verify_uv_reproducibility.sh
#
# Verifies that repeated `uv sync --frozen` from an unchanged uv.lock on the
# same OS/arch resolves an identical set of package names and versions.
#
# Validates: Requirement 2.10

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
APP_SRC="$REPO_ROOT/app/src"

if [ ! -f "$APP_SRC/uv.lock" ]; then
  echo "ERROR: uv.lock not found at $APP_SRC/uv.lock"
  exit 1
fi

TMPDIR_BASE=$(mktemp -d)
trap 'rm -rf "$TMPDIR_BASE"' EXIT

SNAPSHOT_1="$TMPDIR_BASE/packages_run1.json"
SNAPSHOT_2="$TMPDIR_BASE/packages_run2.json"

echo "=== uv sync reproducibility check ==="
echo "Working directory: $APP_SRC"
echo ""

# --- Run 1 ---
echo "[1/4] Running uv sync --frozen (first run)..."
(cd "$APP_SRC" && uv sync --frozen --quiet)

echo "[2/4] Capturing installed packages (first snapshot)..."
(cd "$APP_SRC" && uv pip list --format json | python3 -c "
import json, sys
pkgs = json.load(sys.stdin)
# Normalize: sort by name (case-insensitive) for stable comparison
pkgs.sort(key=lambda p: p['name'].lower())
json.dump(pkgs, sys.stdout, indent=2, sort_keys=True)
") > "$SNAPSHOT_1"

# --- Run 2 ---
echo "[3/4] Running uv sync --frozen (second run)..."
(cd "$APP_SRC" && uv sync --frozen --quiet)

echo "[4/4] Capturing installed packages (second snapshot)..."
(cd "$APP_SRC" && uv pip list --format json | python3 -c "
import json, sys
pkgs = json.load(sys.stdin)
pkgs.sort(key=lambda p: p['name'].lower())
json.dump(pkgs, sys.stdout, indent=2, sort_keys=True)
") > "$SNAPSHOT_2"

# --- Compare ---
echo ""
if diff -q "$SNAPSHOT_1" "$SNAPSHOT_2" > /dev/null 2>&1; then
  PKG_COUNT=$(python3 -c "import json; print(len(json.load(open('$SNAPSHOT_1'))))")
  echo "SUCCESS: Both runs resolved an identical set of $PKG_COUNT packages."
  echo "uv sync is reproducible from the unchanged uv.lock on this OS/arch."
  exit 0
else
  echo "FAILURE: Package lists differ between the two runs!"
  echo ""
  echo "--- Differences ---"
  diff --unified "$SNAPSHOT_1" "$SNAPSHOT_2" || true
  echo ""
  echo "uv sync is NOT reproducible. Investigate the lock file or environment."
  exit 1
fi
