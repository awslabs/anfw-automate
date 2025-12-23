#!/usr/bin/env bash
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}[SETUP]${NC} $1"
}

# Check if we're in a git repository
check_git_repo() {
    if ! git rev-parse --git-dir > /dev/null 2>&1; then
        print_error "This script must be run from within a git repository"
        exit 1
    fi
    print_status "Git repository detected"
}

# Install npm dependencies
install_dependencies() {
    print_header "Installing commit standard dependencies..."
    
    if [ ! -f "package.json" ]; then
        print_error "package.json not found. Please run this script from the project root."
        exit 1
    fi
    
    print_status "Installing npm dependencies..."
    npm install
    
    print_status "Dependencies installed successfully"
}

# Setup Husky
setup_husky() {
    print_header "Setting up Husky git hooks..."
    
    # Initialize husky
    npx husky install
    
    # Make hook files executable
    chmod +x .husky/pre-commit
    chmod +x .husky/commit-msg
    chmod +x .husky/pre-push
    chmod +x .husky/_/husky.sh
    
    print_status "Husky hooks configured successfully"
}

# Configure git settings
configure_git() {
    print_header "Configuring git settings..."
    
    # Set commit message template
    git config commit.template .gitmessage
    print_status "Commit message template configured"
    
    # Configure git to use conventional commits
    git config --local core.hooksPath .husky
    print_status "Git hooks path configured"
    
    # Set up branch protection (local recommendations)
    print_status "Git configuration completed"
}

# Create example commit
show_examples() {
    print_header "Commit Standards Examples"
    
    echo ""
    echo -e "${BLUE}Valid commit message examples:${NC}"
    echo "  feat(app): add new rule validation feature"
    echo "  fix(firewall): resolve routing table race condition"
    echo "  docs(shared): update API documentation"
    echo "  test(vpc): add integration tests for subnets"
    echo "  chore: update dependencies"
    echo ""
    
    echo -e "${BLUE}Valid branch name examples:${NC}"
    echo "  feature/add-rule-validation"
    echo "  hotfix/fix-critical-security-issue"
    echo "  release/v2.1.0"
    echo ""
    
    echo -e "${BLUE}How to make commits:${NC}"
    echo "  1. Stage your changes: git add ."
    echo "  2. Use interactive commit: npm run commit"
    echo "  3. Or commit manually: git commit (uses template)"
    echo ""
}

# Test the setup
test_setup() {
    print_header "Testing commit standards setup..."
    
    # Test commitlint configuration
    echo "test: validate setup" | npx commitlint && {
        print_status "✅ Commitlint validation works"
    } || {
        print_error "❌ Commitlint test failed"
        return 1
    }
    
    # Test commitizen
    if npx cz --help &> /dev/null; then
        print_status "✅ Commitizen is available"
    else
        print_error "❌ Commitizen test failed"
        return 1
    fi
    
    print_status "Setup test completed successfully"
}

# Create GitHub repository settings recommendations
create_github_recommendations() {
    print_header "Creating GitHub repository recommendations..."
    
    cat > .github/REPOSITORY_SETUP.md << 'EOF'
# GitHub Repository Setup Recommendations

To enforce commit standards on GitHub, configure the following repository settings:

## Branch Protection Rules

### For `main` branch:
- ✅ Require pull request reviews before merging
- ✅ Require status checks to pass before merging
  - ✅ Require branches to be up to date before merging
  - ✅ Status checks: `validate-commits`, `lint-and-format`, `security-scan`
- ✅ Require conversation resolution before merging
- ✅ Restrict pushes that create files larger than 100MB
- ✅ Do not allow bypassing the above settings

### For `dev` branch:
- ✅ Require pull request reviews before merging
- ✅ Require status checks to pass before merging
  - ✅ Status checks: `validate-commits`, `lint-and-format`
- ✅ Require conversation resolution before merging

## Repository Settings

### General
- ✅ Disable merge commits (use squash and merge or rebase)
- ✅ Automatically delete head branches

### Actions
- ✅ Allow GitHub Actions
- ✅ Allow actions created by GitHub and verified creators

### Security
- ✅ Enable vulnerability alerts
- ✅ Enable security updates
- ✅ Enable secret scanning

## Required Status Checks

The following GitHub Actions workflows must pass:
- `Commit Standards Enforcement / Validate Commit Messages`
- `Commit Standards Enforcement / Code Quality Checks`
- `Commit Standards Enforcement / Security Scan`

## Pull Request Template

Create `.github/pull_request_template.md` with:

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## Checklist
- [ ] My code follows the project's style guidelines
- [ ] I have performed a self-review of my own code
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] I have made corresponding changes to the documentation
- [ ] My changes generate no new warnings
- [ ] I have added tests that prove my fix is effective or that my feature works
- [ ] New and existing unit tests pass locally with my changes
```
EOF

    print_status "GitHub recommendations created in .github/REPOSITORY_SETUP.md"
}

# Main execution
main() {
    print_header "Setting up commit standards enforcement..."
    echo ""
    
    check_git_repo
    install_dependencies
    setup_husky
    configure_git
    create_github_recommendations
    test_setup
    
    echo ""
    print_status "✅ Commit standards setup completed successfully!"
    echo ""
    
    show_examples
    
    echo -e "${GREEN}Next steps:${NC}"
    echo "1. Configure GitHub repository settings (see .github/REPOSITORY_SETUP.md)"
    echo "2. Create your first commit using: npm run commit"
    echo "3. Push to a feature branch and create a PR to test enforcement"
    echo ""
    
    print_warning "Note: Direct pushes to main/dev branches are blocked by pre-push hook"
    print_warning "Use Pull Requests for all changes to main/dev branches"
}

# Run main function
main "$@"