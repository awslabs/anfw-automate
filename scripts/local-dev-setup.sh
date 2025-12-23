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

# Check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    # Check Node.js
    if ! command -v node &> /dev/null; then
        print_error "Node.js is not installed. Please install Node.js 18+ first."
        exit 1
    fi
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed. Please install Python 3.11+ first."
        exit 1
    fi
    
    # Check Poetry
    if ! command -v poetry &> /dev/null; then
        print_warning "Poetry is not installed. Installing Poetry..."
        curl -sSL https://install.python-poetry.org | python3 -
        export PATH="$HOME/.local/bin:$PATH"
    fi
    
    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        print_warning "AWS CLI is not installed. Please install AWS CLI for full functionality."
    fi
    
    print_status "Prerequisites check completed."
}

# Setup local environment
setup_local_env() {
    print_status "Setting up local development environment..."
    
    # Create local environment file if it doesn't exist
    if [ ! -f "deploy_vars.local.sh" ]; then
        print_status "Creating local environment configuration..."
        cat > deploy_vars.local.sh << 'EOF'
#!/bin/bash
# Local Development Configuration
export AWS_PROFILE=localstack
export STAGE=local
export AWS_REGION=us-east-1
export AWS_ENDPOINT_URL=http://localhost:4566
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test

# LocalStack specific settings
export LOCALSTACK_ENDPOINT=http://localhost:4566
export LAMBDA_EXECUTOR=docker
export DEBUG=1

# Application specific settings
export ACCOUNT_RES=000000000000
export ACCOUNT_PROD=000000000000
export ACCOUNT_DELEGATED_ADMIN=000000000000

echo "Local development environment variables loaded."
EOF
        chmod +x deploy_vars.local.sh
        print_status "Created deploy_vars.local.sh - customize as needed."
    fi
    
    # Create local configuration if it doesn't exist
    if [ ! -f "conf/local.json" ]; then
        print_status "Creating local configuration..."
        mkdir -p conf
        cat > conf/local.json << 'EOF'
{
  "account": {
    "res": "000000000000",
    "prod": "000000000000",
    "delegatedAdmin": "000000000000"
  },
  "region": "us-east-1",
  "stage": "local",
  "vpc": {
    "cidr": "10.0.0.0/16",
    "enableDnsHostnames": true,
    "enableDnsSupport": true
  },
  "firewall": {
    "name": "anfw-local",
    "deleteProtection": false
  },
  "application": {
    "bucketPrefix": "anfw-local",
    "logLevel": "DEBUG"
  }
}
EOF
        print_status "Created conf/local.json - customize as needed."
    fi
}

# Start LocalStack
start_localstack() {
    print_status "Starting LocalStack..."
    
    # Stop any existing containers
    docker-compose -f docker-compose.local.yml down
    
    # Start LocalStack
    docker-compose -f docker-compose.local.yml up -d
    
    # Wait for LocalStack to be ready
    print_status "Waiting for LocalStack to be ready..."
    timeout=60
    while [ $timeout -gt 0 ]; do
        if curl -s http://localhost:4566/_localstack/health | grep -q '"s3": "available"'; then
            print_status "LocalStack is ready!"
            break
        fi
        sleep 2
        timeout=$((timeout - 2))
    done
    
    if [ $timeout -le 0 ]; then
        print_error "LocalStack failed to start within 60 seconds."
        exit 1
    fi
}

# Install dependencies
install_dependencies() {
    print_status "Installing dependencies..."
    
    # Install root dependencies if package.json exists
    if [ -f "package.json" ]; then
        npm install
    fi
    
    # Install shared module dependencies
    if [ -d "shared" ]; then
        print_status "Installing shared module dependencies..."
        cd shared
        npm install
        npm run build
        cd ..
    fi
    
    # Install module dependencies
    for module in app firewall vpc; do
        if [ -d "$module" ]; then
            print_status "Installing $module dependencies..."
            cd "$module"
            npm install
            
            # Install Python dependencies if they exist
            if [ -d "src" ] && [ -f "src/pyproject.toml" ]; then
                cd src
                poetry install --no-root
                cd ..
            fi
            
            # Install lambda dependencies
            if [ -d "lambda" ]; then
                find lambda -name "pyproject.toml" -exec dirname {} \; | while read dir; do
                    print_status "Installing Python dependencies in $module/$dir..."
                    cd "$dir"
                    poetry install --no-root
                    cd - > /dev/null
                done
            fi
            
            cd ..
        fi
    done
}

# Setup git hooks
setup_git_hooks() {
    print_status "Setting up git hooks..."
    
    # Set commit message template
    git config commit.template .gitmessage
    
    # Install pre-commit hook
    cat > .git/hooks/pre-commit << 'EOF'
#!/bin/bash
# Run linting and tests before commit
set -e

echo "Running pre-commit checks..."

# Check for Python syntax errors
find . -name "*.py" -not -path "./node_modules/*" -not -path "./.venv/*" -not -path "./cdk.out/*" | xargs python3 -m py_compile

# Check for TypeScript compilation errors
if command -v npx &> /dev/null; then
    for module in app firewall vpc shared; do
        if [ -d "$module" ] && [ -f "$module/tsconfig.json" ]; then
            echo "Checking TypeScript in $module..."
            cd "$module"
            npx tsc --noEmit
            cd ..
        fi
    done
fi

echo "Pre-commit checks passed!"
EOF
    chmod +x .git/hooks/pre-commit
    
    print_status "Git hooks configured."
}

# Main execution
main() {
    print_status "Starting local development environment setup..."
    
    check_prerequisites
    setup_local_env
    start_localstack
    install_dependencies
    setup_git_hooks
    
    print_status "Local development environment setup completed!"
    print_status ""
    print_status "Next steps:"
    print_status "1. Source the local environment: source deploy_vars.local.sh"
    print_status "2. Customize conf/local.json as needed"
    print_status "3. Run 'make build' to build all modules"
    print_status "4. Run 'make deploy' to deploy to LocalStack"
    print_status "5. Access LocalStack at http://localhost:4566"
    print_status "6. Access DynamoDB Admin at http://localhost:8001"
}

# Run main function
main "$@"