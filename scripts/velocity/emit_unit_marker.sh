#!/usr/bin/env bash
# emit_unit_marker.sh — Run unit tests and emit the unit gate marker on success.
#
# This script implements the fail-closed gate marker behavior:
# - On all-pass: extracts coverage and writes GateMarker(kind="unit")
# - On any failure: exits non-zero without writing a marker
# - Leaves any prior marker unchanged on failure
#
# Requirements: 1.3, 1.4, 1.5, 1.8
#
# Usage:
#   bash scripts/velocity/emit_unit_marker.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$REPO_ROOT"

# --- Run Python unit tests and capture coverage ---
echo "🐍 Running Python unit/property tests..."
PYTEST_OUTPUT=$(cd app/src && uv run pytest -m "not integration" \
    --cov=. --cov-report=term-missing --cov-fail-under="${COV_MIN:-40}" 2>&1) || {
    echo "❌ Python unit tests failed. No marker emitted."
    echo "$PYTEST_OUTPUT" | tail -20
    exit 1
}

# Extract coverage percentage from pytest-cov output.
# pytest-cov prints a line like "TOTAL    123    45    63%" at the end.
COVERAGE=$(echo "$PYTEST_OUTPUT" | grep -E "^TOTAL\s" | awk '{print $NF}' | tr -d '%')

if [ -z "$COVERAGE" ]; then
    # Fallback: try to find coverage in the "Required test coverage" line
    COVERAGE=$(echo "$PYTEST_OUTPUT" | grep -oP '(?<=coverage: )\d+(\.\d+)?' | tail -1)
fi

if [ -z "$COVERAGE" ]; then
    echo "⚠️  Could not extract coverage from pytest output. Using 0."
    COVERAGE="0"
fi

echo "   Python coverage: ${COVERAGE}%"

# --- Run CDK Jest assertion tests ---
echo "🏗️  Running CDK assertion tests..."
if ! yarn workspace app test 2>&1; then
    echo "❌ CDK assertion tests failed. No marker emitted."
    exit 1
fi

# --- All tests passed — emit the gate marker ---
echo "🎯 All unit tests passed. Emitting gate marker..."
python3 "$SCRIPT_DIR/gate_marker.py" --kind unit --coverage "$COVERAGE"
