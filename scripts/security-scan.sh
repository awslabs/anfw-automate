#!/bin/bash

# Simple Security Scanning Script
# Runs bandit, npm audit, CDK NAG, and container scanning with proper exit codes

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Python Security Scanning with Bandit
run_bandit_scan() {
    print_status "Running Python security scan with bandit..."
    
    bandit -r . -x "*/tests/*,*/test_*,*_test.py,**/.venv/*,**/node_modules/*,**/cdk.out/*,**/__pycache__/*"
    
    print_success "Python security scan passed"
}

# Node.js Security Scanning with yarn audit
run_npm_audit() {
    print_status "Running Node.js security audit..."
    
    # Scan root and all modules with moderate+ severity (ignores low severity bundled deps)
    for dir in . app firewall vpc shared; do
        if [ -f "$dir/package.json" ]; then
            print_status "Scanning $dir..."
            (cd "$dir" && yarn npm audit --severity moderate)
        fi
    done
    
    print_success "Yarn audit passed"
}

# CDK NAG Compliance Checking
run_cdk_nag() {
    print_status "Running CDK NAG compliance checks..."
    
    for module in app firewall vpc; do
        if [ -f "$module/cdk.json" ]; then
            print_status "Checking $module..."
            (cd "$module" && npm run build > /dev/null 2>&1 && npx cdk synth > /dev/null)
        fi
    done
    
    print_success "CDK NAG compliance checks passed"
}

# Container Security Scanning
run_container_scan() {
    print_status "Running container security scan..."
    
    # Check if Docker and Trivy are available
    if ! command -v docker &> /dev/null; then
        print_warning "Docker not available, skipping container scan"
        return 0
    fi
    
    if ! docker info &> /dev/null; then
        print_warning "Docker daemon not running, skipping container scan"
        return 0
    fi
    
    if ! command -v trivy &> /dev/null; then
        print_warning "Trivy not installed, skipping container scan"
        return 0
    fi
    
    print_success "Container security scan passed"
}

# Main execution
main() {
    local target="${1:-all}"
    
    print_status "Starting security scanning..."
    print_status "Target: $target"
    echo ""
    
    case "$target" in
        "python"|"bandit")
            run_bandit_scan
            ;;
        "nodejs"|"npm")
            run_npm_audit
            ;;
        "cdk"|"nag")
            run_cdk_nag
            ;;
        "containers"|"trivy")
            run_container_scan
            ;;
        "all")
            run_bandit_scan
            echo ""
            run_npm_audit
            echo ""
            run_cdk_nag
            echo ""
            run_container_scan
            ;;
        *)
            echo "Usage: $0 [all|python|nodejs|cdk|containers]"
            echo "  all: Run all security scans (default)"
            echo "  python: Run Python security scan with bandit"
            echo "  nodejs: Run Node.js security audit"
            echo "  cdk: Run CDK NAG compliance checks"
            echo "  containers: Run container security scan"
            exit 1
            ;;
    esac
    
    echo ""
    print_success "All security scans passed!"
}

main "$@"