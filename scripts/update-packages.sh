#!/usr/bin/env bash

set -eo 

CURRENT_DIR=$(pwd)
PYTHON_DIRS=$(find . -name pyproject.toml -print0 | xargs -0 -n1 dirname)

echo $PYTHON_DIRS

# Define a list of blacklist patterns
BLACKLIST=("cdk.out" "node_modules" "./dist")

for dir in $PYTHON_DIRS; do   
    DIR_NAME=$(echo "$dir" | sed 's|^\./\([^/]*\)/.*|\1|')
    # Check if the directory matches any blacklist pattern
    if [[ " ${BLACKLIST[@]} " =~ " $DIR_NAME " ]]; then
        echo "Directory $DIR_NAME will be ignored."
    else
        echo "Processing directory: $dir"
        pushd $dir
        poetry lock 
        poetry update
        poetry version patch
        poetry run pip-licenses --output NOTICE
        popd
    fi
done

npm update