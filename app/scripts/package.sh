#!/bin/bash
# ANFW Automate - Pre-Synth Script for local cdk synth

# Ensure that the required applications and configuration variables are in place

# main
set -eo pipefail

echo "executing pre-synth"

# ─── Export runtime dependencies for Lambda bundling ───────────────────────────
# The CDK PythonLayerVersion bundling image does not have uv installed, so we
# export a pip-compatible requirements.txt that it can use to install deps.
# (Requirement 2.7/2.8: Lambda dependency bundling with uv export fallback)
echo "exporting runtime dependencies via uv export..."
cd src
uv export --format requirements-txt --no-default-groups --no-hashes --no-emit-project > requirements.txt
echo "requirements.txt generated at app/src/requirements.txt"
cd ..

# ─── Package the source code ──────────────────────────────────────────────────
rm -rf dist
mkdir -p dist
cp -r src/* dist/
cp -r dist/data dist/RuleCollect/data && cp -r dist/lib dist/RuleCollect/lib
cp -r dist/data dist/RuleExecute/data && cp -r dist/lib dist/RuleExecute/lib