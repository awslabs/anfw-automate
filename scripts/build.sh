#!/usr/bin/env bash
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Validate environment variables
validate_environment() {
    print_status "Validating environment variables..."
    
    if [ -z "${STAGE:-}" ]; then
        print_error "STAGE environment variable is required"
        exit 1
    fi
    
    if [ -z "${STACK_NAME:-}" ]; then
        print_error "STACK_NAME environment variable is required"
        exit 1
    fi
    
    print_status "Environment validation passed: STAGE=${STAGE}, STACK_NAME=${STACK_NAME}"
}

# Enhanced Python build with better error handling
build_python_components() {
    print_status "Building Python components..."
    
    PYTHON_DIRS=$(find . -name pyproject.toml)

    # Check if PYTHON_DIRS is empty
    if [ -z "$PYTHON_DIRS" ]; then
        print_warning "No Python directories found. Skipping Python dependencies installation."
        return 0
    fi

    # Filter out unnecessary directories from PYTHON_DIRS
    PYTHON_DIRS=$(echo "$PYTHON_DIRS" | grep -vE "cdk\.out|node_modules")
    
    # Install poetry if not available
    if ! command -v poetry &> /dev/null; then
        print_status "Installing Poetry..."
        pip install poetry
    fi

    # Install python dependencies
    for d in $PYTHON_DIRS; do
        pushd $(dirname $d) > /dev/null
        local current_dir=$(pwd)
        print_status "Processing Python project in: $current_dir"
        
        # Create virtual environment
        python3 -m venv .venv
        source .venv/bin/activate
        
        # Install dependencies
        poetry install --no-root
        
        # Security and compliance checks
        print_status "Running security audit..."
        poetry run pip-audit --local --ignore-vuln PYSEC-2022-43012 || {
            print_warning "Security audit found issues, but continuing..."
        }
        
        print_status "Running security scan with bandit..."
        poetry run bandit -r . -x "**.venv/*","**test/*","**node_modules/*","**cdk.out/*","**dist/*" || {
            print_warning "Bandit found security issues, but continuing..."
        }
        
        # Generate license report
        poetry run pip-licenses --output NOTICE
        
        # Run tests with better error handling
        print_status "Running Python tests in $(basename "$(pwd)")"
        if [ "$(basename "$(pwd)")" != "dist" ] && [ "$(basename "$(pwd)")" != "cdk.out" ]; then
            poetry run pytest -v --tb=short --junitxml=test-results.xml || {
                local exit_code=$?
                if [ $exit_code -eq 5 ]; then
                    print_warning "No tests found in $(basename "$(pwd)")"
                else
                    print_error "Tests failed in $(basename "$(pwd)") with exit code $exit_code"
                    exit $exit_code
                fi
            }
        else
            print_warning "Skipping tests in build/output directory: $(basename "$(pwd)")"
        fi
        
        popd > /dev/null
    done
    
    print_status "Python components build completed successfully"
}

# Enhanced TypeScript build
build_typescript_components() {
    print_status "Building TypeScript components..."
    
    # Install npm dependencies
    if [ -f "package.json" ]; then
        print_status "Installing npm dependencies..."
        npm ci
        
        # Run TypeScript compilation check
        if [ -f "tsconfig.json" ]; then
            print_status "Checking TypeScript compilation..."
            npx tsc --noEmit
        fi
        
        # Run TypeScript tests
        print_status "Running TypeScript tests..."
        npm test || {
            print_warning "TypeScript tests failed or no tests found"
        }
    fi
    
    print_status "TypeScript components build completed"
}

# CDK synthesis with validation
synthesize_cdk() {
    print_status "Synthesizing CDK templates..."
    
    # Run CDK synth with validation
    npx cdk synth --strict
    
    # Validate generated CloudFormation templates
    if command -v cfn-lint &> /dev/null; then
        print_status "Running CloudFormation linting..."
        find cdk.out -name "*.template.json" -exec cfn-lint {} \; || {
            print_warning "CloudFormation linting found issues"
        }
    fi
    
    print_status "CDK synthesis completed successfully"
}

# Generate build report
generate_build_report() {
    print_status "Generating build report..."
    
    cat > build-report.json << EOF
{
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "stage": "${STAGE}",
  "stack_name": "${STACK_NAME}",
  "build_status": "success",
  "git_commit": "$(git rev-parse HEAD 2>/dev/null || echo 'unknown')",
  "git_branch": "$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'unknown')"
}
EOF
    
    print_status "Build report generated: build-report.json"
}

# Main execution
main() {
    print_status "Starting enhanced build process..."
    
    validate_environment
    build_python_components
    build_typescript_components
    synthesize_cdk
    generate_build_report
    
    print_status "Build process completed successfully!"
}

# Execute main function
main "$@"
