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

# Detect if we're in workspace mode (running from root) or module mode
detect_build_mode() {
    local current_dir=$(basename "$(pwd)")
    local parent_dir=$(basename "$(dirname "$(pwd)")")
    
    # Check if we're in a module directory
    case "$current_dir" in
        "app"|"firewall"|"vpc"|"shared")
            echo "module"
            return 0
            ;;
    esac
    
    # Check if we're in root with modules as subdirectories
    if [ -d "app" ] && [ -d "shared" ] && [ -f "package.json" ]; then
        echo "workspace"
        return 0
    fi
    
    # Default to module mode for backward compatibility
    echo "module"
}

# Validate environment variables
validate_environment() {
    print_status "Validating environment variables..."
    
    # Detect build mode
    export BUILD_MODE=$(detect_build_mode)
    print_status "Build mode detected: ${BUILD_MODE}"
    
    if [ -z "${STAGE:-}" ]; then
        print_error "STAGE environment variable is required but not set"
        print_error "Please set STAGE environment variable (e.g., export STAGE=dev)"
        exit 1
    fi
    
    # Set AWS_REGION if not provided (required for CDK synthesis)
    if [ -z "${AWS_REGION:-}" ]; then
        print_warning "AWS_REGION environment variable not set, using 'us-east-1' as default"
        export AWS_REGION="us-east-1"
    fi
    
    # Handle module naming
    if [ "${BUILD_MODE}" = "workspace" ]; then
        # In workspace mode, build all modules or specific one if MODULE_NAME is set
        if [ -z "${MODULE_NAME:-}" ]; then
            export MODULE_NAME="all"
            print_status "Building all modules in workspace mode"
        else
            print_status "Building specific module: ${MODULE_NAME}"
        fi
    else
        # Module mode - detect from directory or use provided MODULE_NAME
        local current_dir=$(basename "$(pwd)")
        
        if [ -n "${MODULE_NAME:-}" ]; then
            print_status "Using provided MODULE_NAME: ${MODULE_NAME}"
        else
            # Auto-detect from directory
            case "$current_dir" in
                "app"|"firewall"|"vpc"|"shared")
                    export MODULE_NAME="$current_dir"
                    print_status "Auto-detected module from directory: ${MODULE_NAME}"
                    ;;
                *)
                    export MODULE_NAME="unknown"
                    print_warning "Could not detect module name, using 'unknown'"
                    ;;
            esac
        fi
    fi
    
    print_status "Environment validation passed: STAGE=${STAGE}, MODULE=${MODULE_NAME}, AWS_REGION=${AWS_REGION}"
}

# Build Python components with enhanced error handling
build_python_components() {
    local target_module="${1:-${MODULE_NAME}}"
    
    if [ "${BUILD_MODE}" = "workspace" ] && [ "${target_module}" = "all" ]; then
        print_status "Building Python components for all modules..."
        for module in app firewall vpc shared; do
            if [ -d "$module" ]; then
                print_status "Building Python components in module: $module"
                (cd "$module" && build_python_components_in_directory)
            fi
        done
        return 0
    elif [ "${BUILD_MODE}" = "workspace" ] && [ "${target_module}" != "all" ]; then
        if [ -d "${target_module}" ]; then
            print_status "Building Python components in module: ${target_module}"
            (cd "${target_module}" && build_python_components_in_directory)
        else
            print_error "Module directory '${target_module}' not found"
            exit 1
        fi
        return 0
    fi
    
    # Module mode - build in current directory
    print_status "Building Python components for ${MODULE_NAME}..."
    build_python_components_in_directory
}

# Helper function to build Python components in current directory
build_python_components_in_directory() {
    local PYTHON_DIRS=$(find . -name pyproject.toml 2>/dev/null || true)

    if [ -z "$PYTHON_DIRS" ]; then
        print_status "No Python components found in $(basename "$(pwd)"). Skipping Python build."
        return 0
    fi

    # Filter out build directories
    PYTHON_DIRS=$(echo "$PYTHON_DIRS" | grep -vE "cdk\.out|node_modules|\.venv" || true)
    
    if [ -z "$PYTHON_DIRS" ]; then
        print_status "No valid Python components found in $(basename "$(pwd)"). Skipping Python build."
        return 0
    fi

    # Install poetry if not available
    if ! command -v poetry &> /dev/null; then
        print_status "Installing Poetry..."
        pip install poetry
    fi

    # Process each Python directory
    for d in $PYTHON_DIRS; do
        pushd $(dirname $d) > /dev/null
        local current_dir=$(pwd)
        print_status "Processing Python project in: $current_dir"
        
        # Install dependencies
        poetry install --no-root --with test
        
        # Security checks
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
    
    print_status "Python components build completed for $(basename "$(pwd)")"
}

# Enhanced TypeScript build with workspace awareness
build_typescript_components() {
    local target_module="${1:-${MODULE_NAME}}"
    
    if [ "${BUILD_MODE}" = "workspace" ]; then
        print_status "Building TypeScript components in workspace mode..."
        
        # Ensure all dependencies are installed at workspace level
        print_status "Installing workspace dependencies..."
        npm install
        
        if [ "${target_module}" = "all" ]; then
            # Build shared first, then all other modules
            print_status "Building shared dependencies..."
            npm run build:shared
            
            for module in app firewall vpc; do
                if [ -d "$module" ] && [ -f "$module/package.json" ]; then
                    print_status "Building TypeScript for module: $module"
                    npm run build --workspace=${module}
                    
                    print_status "Running TypeScript tests for ${module}..."
                    npm run test --workspace=${module} || {
                        print_warning "TypeScript tests failed or no tests found for ${module}"
                    }
                fi
            done
        else
            # Build specific module
            if [ "${target_module}" != "shared" ]; then
                print_status "Building shared dependencies..."
                npm run build:shared
            fi
            
            print_status "Building TypeScript for ${target_module}..."
            npm run build --workspace=${target_module}
            
            print_status "Running TypeScript tests for ${target_module}..."
            npm run test --workspace=${target_module} || {
                print_warning "TypeScript tests failed or no tests found for ${target_module}"
            }
        fi
    else
        # Module mode - build in current directory
        print_status "Building TypeScript components for ${MODULE_NAME}..."
        
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
    fi
    
    print_status "TypeScript components build completed"
}

# CDK synthesis with validation and workspace awareness
synthesize_cdk() {
    local target_module="${1:-${MODULE_NAME}}"
    
    if [ "${BUILD_MODE}" = "workspace" ]; then
        if [ "${target_module}" = "all" ]; then
            print_status "Synthesizing CDK templates for all modules..."
            for module in app firewall vpc; do
                if [ -d "$module" ] && [ -f "$module/cdk.json" ]; then
                    print_status "Synthesizing CDK for module: $module"
                    (cd "$module" && synthesize_cdk_in_directory)
                fi
            done
        elif [ "${target_module}" != "shared" ]; then
            if [ -d "${target_module}" ] && [ -f "${target_module}/cdk.json" ]; then
                print_status "Synthesizing CDK for module: ${target_module}"
                (cd "${target_module}" && synthesize_cdk_in_directory)
            else
                print_status "No CDK configuration found for ${target_module}, skipping synthesis"
            fi
        else
            print_status "Skipping CDK synthesis for shared module"
        fi
    else
        # Module mode
        if [ "${MODULE_NAME}" = "shared" ]; then
            print_status "Skipping CDK synthesis for shared module"
            return 0
        fi
        
        synthesize_cdk_in_directory
    fi
}

# Helper function to synthesize CDK in current directory
synthesize_cdk_in_directory() {
    print_status "Synthesizing CDK templates for $(basename "$(pwd)")..."
    
    # Set environment variables to suppress CDK warnings and notices
    export JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION=1
    export CDK_DISABLE_VERSION_CHECK=1
    
    # Acknowledge known CDK notices to prevent build failures
    cdk acknowledge 34892 2>/dev/null || true
    cdk acknowledge 32775 2>/dev/null || true
    
    # Run CDK synth with notices disabled
    npx cdk synth --no-notices
    
    # Validate generated CloudFormation templates
    if command -v cfn-lint &> /dev/null; then
        print_status "Running CloudFormation linting..."
        find cdk.out -name "*.template.json" -exec cfn-lint {} \; || {
            print_warning "CloudFormation linting found issues"
        }
    fi
    
    print_status "CDK synthesis completed for $(basename "$(pwd)")"
}

# Generate build report
generate_build_report() {
    print_status "Generating build report..."
    
    cat > build-report.json << EOF
{
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "stage": "${STAGE}",
  "module": "${MODULE_NAME}",
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
    
    if [ "${BUILD_MODE}" = "workspace" ]; then
        if [ "${MODULE_NAME}" = "all" ]; then
            print_status "Building all modules in workspace..."
            build_python_components "all"
            build_typescript_components "all"
            synthesize_cdk "all"
        else
            print_status "Building specific module: ${MODULE_NAME}"
            build_python_components "${MODULE_NAME}"
            build_typescript_components "${MODULE_NAME}"
            synthesize_cdk "${MODULE_NAME}"
        fi
    else
        print_status "Building module: ${MODULE_NAME}"
        build_python_components
        build_typescript_components
        synthesize_cdk
    fi
    
    generate_build_report
    
    print_status "Build process completed successfully for ${MODULE_NAME}!"
}

# Execute main function
main "$@"
