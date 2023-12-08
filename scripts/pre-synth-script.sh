#!/bin/bash
# ANFW Automate - Pre-Synth Script for local cdk synth

# Ensure that the required applications and configuration variables are in place

# main
set -eo pipefail

echo "executing pre-synth"
# Package the source code
rm -r dist/* || mkdir -p dist
cp -r app/* dist/
cp -r dist/data dist/RuleCollect/data && cp -r dist/lib dist/RuleCollect/lib
cp -r dist/data dist/RuleExecute/data && cp -r dist/lib dist/RuleExecute/lib