#!/usr/bin/env bash

set -eo

PYTHON_DIRS=$(find . -name pyproject.toml | egrep -v "cdk.out|node_modules")

pip install poetry

# Install python depndencies
for d in $PYTHON_DIRS
do
    pushd $(dirname $d)
    pwd
    echo "Installing in $d"
    python3 -m venv .venv
    source .venv/bin/activate
    poetry install --no-root
    poetry run pip-audit --local --ignore-vuln PYSEC-2022-43012
    poetry run bandit -r . -x "**.venv/*","**test/*"
    poetry run pip-licenses --output NOTICE
    popd
done


# Install npm depndencies
npm install
npm ci
# Run the CDK synth
npx cdk synth