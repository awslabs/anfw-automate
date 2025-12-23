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

# Setup local environment files
setup_local_env() {
    print_status "Setting up local development configuration..."
    
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

# Main execution
main() {
    print_status "Setting up LocalStack configuration files..."
    echo ""
    
    setup_local_env
    
    echo ""
    print_status "✅ LocalStack configuration completed!"
    print_status ""
    print_status "Configuration files created:"
    print_status "- deploy_vars.local.sh (environment variables)"
    print_status "- conf/local.json (application configuration)"
}

# Run main function
main "$@"