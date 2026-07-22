#!/usr/bin/env bash
# promote.sh — Guarded promotion script
#
# This script orchestrates the promotion flow:
# 1. Gets current HEAD sha
# 2. Validates gate markers (unit + INT must be fresh)
# 3. Deploys to prod via cross-account CodePipeline
# 4. Runs a read-only canary
# 5. Rolls back on any failure
#
# Usage:
#   bash scripts/velocity/promote.sh --version v1.2.3 --prev v1.2.2
#
#   # Write INT gate marker after successful INT run:
#   bash scripts/velocity/promote.sh --int-gate-only --coverage 85.0
#
# Exit codes match promote.py:
#   0 — success
#   1 — gate check failed
#   2 — deploy failed (rollback triggered)
#   3 — canary failed (rollback triggered)
#   4 — rollback failed
#   5 — invalid arguments or unexpected error

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Resolve Python — prefer uv run if available
if command -v uv &>/dev/null; then
    PYTHON="uv run python3"
else
    PYTHON="python3"
fi

exec ${PYTHON} "${SCRIPT_DIR}/promote.py" "$@"
