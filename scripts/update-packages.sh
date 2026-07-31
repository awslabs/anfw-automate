#!/usr/bin/env bash

set -eo pipefail

CURRENT_DIR=$(pwd)

# Find Python directories with pyproject.toml, excluding build and dependency directories
PYTHON_DIRS=$(find . -name pyproject.toml -not -path "./node_modules/*" -not -path "./cdk.out/*" -not -path "*/.venv/*" -not -path "./dist/*" -print0 | xargs -0 -n1 dirname)

echo "Found Python directories: $PYTHON_DIRS"

# Define a list of blacklist patterns
BLACKLIST=("cdk.out" "node_modules" "./dist" ".venv")

# Configure Poetry to not interfere with existing .venv directories
export POETRY_VENV_IN_PROJECT=false
export POETRY_CACHE_DIR="${HOME}/.cache/pypoetry"

for dir in $PYTHON_DIRS; do   
    DIR_NAME=$(echo "$dir" | sed 's|^\./\([^/]*\)/.*|\1|')
    
    # Check if the directory matches any blacklist pattern
    if [[ " ${BLACKLIST[@]} " =~ " $DIR_NAME " ]]; then
        echo "Directory $DIR_NAME will be ignored."
        continue
    fi
    
    # Skip if directory contains .venv to avoid conflicts
    if [[ -d "$dir/.venv" ]]; then
        echo "Found existing .venv in $dir - using Poetry's existing virtual environment"
        # Continue processing instead of skipping
    fi
    
    echo "Processing directory: $dir"
    pushd "$dir" > /dev/null
    
    # Ensure Poetry uses its own virtual environment
    if poetry env info --path > /dev/null 2>&1; then
        echo "Using existing Poetry virtual environment"
    else
        echo "Creating new Poetry virtual environment"
    fi
    
    # Install all dependencies including test group
    echo "Installing dependencies with test group..."
    poetry install --with test
    
    # Update packages
    poetry lock
    poetry update
    poetry version patch
    
    # Generate NOTICE file with pip-licenses
    poetry run pip-licenses --output-file NOTICE
    
    popd > /dev/null
done

# Update npm packages from root directory to handle workspaces correctly
if [[ -f "../package.json" ]] && grep -q "workspaces" "../package.json"; then
    echo "Updating npm packages from root directory (workspace detected)..."
    pushd .. > /dev/null
    npm update --workspace=$(basename "$CURRENT_DIR")
    popd > /dev/null
elif [[ -f "package.json" ]]; then
    echo "Updating npm packages..."
    npm update
else
    echo "No package.json found, skipping npm update"
fi