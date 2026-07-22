#!/usr/bin/env bash
# int-run.sh — Integration test orchestration script
#
# Drives the full INT run flow:
#   1. Verify unit gate marker is fresh
#   2. Assert caller is the allowlisted INT account
#   3. Ensure stable tier is current (cdk deploy UPDATE / no-op)
#   4. Run integration tests (pytest -m integration)
#   5. Revert is handled by conftest.py fixtures (always runs)
#   6. Write INT gate marker on success
#
# Usage:
#   bash scripts/velocity/int-run.sh
#
# Exit codes:
#   0 — all integration tests passed
#   1 — unit gate marker missing/stale
#   2 — account guardrail rejection
#   3 — ensure_base_infra failed
#   4 — integration tests failed
#   5 — unexpected error

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$REPO_ROOT"

# Resolve Python runner
if command -v uv &>/dev/null; then
    PY="uv run python3"
else
    PY="python3"
fi

echo "═══════════════════════════════════════════════════════════════"
echo "  INT Run — Integration Test Orchestration"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# --- Step 1: Verify unit gate marker is fresh ---
echo "▶ Step 1: Checking unit gate marker freshness..."
HEAD_SHA=$(git rev-parse HEAD)

${PY} -c "
import sys
sys.path.insert(0, 'scripts/velocity')
from promoter import Promoter, PromotionError
try:
    p = Promoter()
    p.require_marker('unit', '${HEAD_SHA}')
    print('  ✓ Unit gate marker is fresh')
except PromotionError as e:
    print(f'  ✗ Unit gate marker check failed: {e}')
    sys.exit(1)
" || exit 1

echo ""

# --- Step 2: Run integration tests ---
# The conftest.py handles:
#   - Account guardrail (assert_is_int_account)
#   - RunScope creation
#   - Baseline capture
#   - Guaranteed revert in finally block
echo "▶ Step 2: Running integration tests..."
echo ""

cd app/src
if uv run pytest -m "integration" \
    --tb=short \
    --junitxml="../../.velocity/reports/int-junit.xml" \
    "../../tests/integration/cases/" 2>&1; then
    echo ""
    echo "  ✓ All integration tests passed"
    cd "$REPO_ROOT"

    # --- Step 3: Write INT gate marker ---
    echo ""
    echo "▶ Step 3: Writing INT gate marker..."
    ${PY} scripts/velocity/gate_marker.py --kind int --coverage 0
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "  ✓ INT Run PASSED"
    echo "═══════════════════════════════════════════════════════════════"
    exit 0
else
    EXIT_CODE=$?
    cd "$REPO_ROOT"
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "  ✗ INT Run FAILED (exit code ${EXIT_CODE})"
    echo "═══════════════════════════════════════════════════════════════"
    exit 4
fi
