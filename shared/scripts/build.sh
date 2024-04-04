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
    poetry run bandit -r . -x "**.venv/*","**test/*","**node_modules/*","**cdk.out/*","**dist/*"
    poetry run pip-licenses --output NOTICE
    # Run tests if not in dist or cdk.out directory
    echo "Running tests in $(basename "$(pwd)")"
    if [ "$(basename "$(pwd)")" != "dist" ]; then
        poetry run pytest -k test_ || ([ $? -eq 5 ] && exit 0 || exit $?)
    else
        echo "Current directory is 'dist' or 'cdk.out', skipping tests."
    fi
    popd
done


# Install npm depndencies
npm install
npm ci
# Run the CDK synth
npx cdk synth