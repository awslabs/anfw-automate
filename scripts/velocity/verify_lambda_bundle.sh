#!/bin/bash
# verify_lambda_bundle.sh — Verify Lambda dependency bundling with uv export fallback
#
# This script:
#   1. Runs the pre-synth package.sh to generate requirements.txt via uv export
#   2. Installs the exported requirements into a temp directory
#   3. Verifies every runtime dependency from pyproject.toml is present
#   4. Reports success or lists missing packages
#
# Requirements: 2.7, 2.8
set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
APP_DIR="$REPO_ROOT/app"
SRC_DIR="$APP_DIR/src"
PYPROJECT="$SRC_DIR/pyproject.toml"

echo "═══════════════════════════════════════════════════════════════"
echo "  Lambda Dependency Bundle Verification"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Step 1: Run package.sh to generate requirements.txt
echo "▶ Step 1: Running package.sh to export dependencies..."
cd "$APP_DIR"
bash scripts/package.sh
echo ""

# Step 2: Verify requirements.txt was generated
REQUIREMENTS="$SRC_DIR/requirements.txt"
if [ ! -f "$REQUIREMENTS" ]; then
    echo "✗ FAIL: requirements.txt was not generated at $REQUIREMENTS"
    exit 1
fi
echo "✓ requirements.txt generated successfully"
echo ""

# Step 3: Install into a temp directory using uv pip install
TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT

echo "▶ Step 2: Installing requirements into temp directory..."
uv pip install --quiet --target "$TMPDIR" -r "$REQUIREMENTS" 2>/dev/null || {
    echo "✗ FAIL: uv pip install failed for requirements.txt"
    exit 1
}
echo "✓ Dependencies installed successfully"
echo ""

# Step 4: Extract runtime dependencies from pyproject.toml and verify
echo "▶ Step 3: Verifying all runtime dependencies are present..."

# Extract dependency names from pyproject.toml [project] dependencies
RUNTIME_DEPS=$(python3 -c "
import sys
# Python 3.11+ has tomllib, fallback to parsing for 3.9
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        # Manual parse: extract lines between 'dependencies = [' and ']'
        import re
        with open('$PYPROJECT', 'r') as f:
            content = f.read()
        match = re.search(r'dependencies\s*=\s*\[(.*?)\]', content, re.DOTALL)
        if match:
            deps_str = match.group(1)
            for line in deps_str.strip().split('\n'):
                line = line.strip().strip(',').strip('\"').strip(\"'\")
                if line:
                    name = re.split(r'[><=!~\[]', line)[0].strip()
                    print(name.lower())
        sys.exit(0)

with open('$PYPROJECT', 'rb') as f:
    data = tomllib.load(f)

deps = data.get('project', {}).get('dependencies', [])
import re
for dep in deps:
    name = re.split(r'[><=!~\[]', dep)[0].strip()
    print(name.lower())
")

MISSING=()
FOUND=()

for dep in $RUNTIME_DEPS; do
    # Normalize package name: PEP 503 says hyphens/underscores/dots are equivalent
    dep_underscore=$(echo "$dep" | tr '-' '_')
    dep_hyphen=$(echo "$dep" | tr '_' '-')

    # Check for dist-info directory (the canonical proof a package is installed)
    if find "$TMPDIR" -maxdepth 1 -type d -iname "${dep_underscore}-*.dist-info" 2>/dev/null | grep -q . || \
       find "$TMPDIR" -maxdepth 1 -type d -iname "${dep_hyphen}-*.dist-info" 2>/dev/null | grep -q .; then
        FOUND+=("$dep")
        echo "  ✓ $dep"
    else
        MISSING+=("$dep")
        echo "  ✗ $dep (MISSING)"
    fi
done

echo ""

# Step 5: Report results
if [ ${#MISSING[@]} -eq 0 ]; then
    echo "═══════════════════════════════════════════════════════════════"
    echo "  ✓ PASS: All ${#FOUND[@]} runtime dependencies are bundled"
    echo "═══════════════════════════════════════════════════════════════"
    exit 0
else
    echo "═══════════════════════════════════════════════════════════════"
    echo "  ✗ FAIL: ${#MISSING[@]} runtime dependencies are MISSING:"
    for m in "${MISSING[@]}"; do
        echo "    - $m"
    done
    echo "═══════════════════════════════════════════════════════════════"
    exit 1
fi
