#!/bin/bash

# Security Scanning Script
# Runs gitleaks, bandit, yarn audit, and CDK NAG

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
    
    # Use bandit.yaml config file for consistent exclusions
    bandit -r . -c bandit.yaml -ll
    
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

# Secret Scanning with gitleaks
run_secret_scan() {
    print_status "Scanning for hardcoded secrets with gitleaks..."
    
    # Check if yarn is available
    if ! command -v yarn &> /dev/null; then
        print_error "yarn not found - ensure Node.js and Yarn are installed"
        exit 1
    fi
    
    # Enable corepack for Yarn 4
    corepack enable
    
    # Run gitleaks on the repository
    # --no-git: scan files without git history
    # --config: use custom config with path exclusions
    yarn exec gitleaks detect --source . --no-git --config .gitleaks.toml --verbose
    
    print_success "Secret scan passed - no secrets detected"
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
        "nodejs"|"npm"|"yarn")
            run_npm_audit
            ;;
        "secrets"|"git-secrets")
            print_error "Secret scanning with gitleaks is no longer supported via this script"
            print_error "Gitleaks runs automatically:"
            print_error "  - Pre-commit: Docker container (no installation needed)"
            print_error "  - CI: GitHub Actions workflow"
            print_error "  - Manual: docker run --rm -v \"\$(pwd):/path\" zricethezav/gitleaks:latest detect --source /path --no-git --config /path/.gitleaks.toml"
            exit 1
            ;;
        "all")
            run_bandit_scan
            echo ""
            run_npm_audit
            ;;
        *)
            echo "Usage: $0 [all|python|nodejs]"
            echo "  all:     Run all security scans (default)"
            echo "  python:  Run Python security scan with bandit"
            echo "  nodejs:  Run Node.js security audit"
            echo ""
            echo "Note: Secret scanning (gitleaks) is handled by pre-commit hook"
            echo "Note: CDK NAG compliance checks run automatically during 'make build'"
            exit 1
            ;;
    esac
    
    echo ""
    print_success "All security scans passed!"
}

main "$@"