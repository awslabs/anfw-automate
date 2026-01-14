# Commit Standards Enforcement Guide

This document explains how commit standards are enforced both locally and on
GitHub for the AWS Network Firewall automation project.

## 🎯 Overview

We enforce commit standards at multiple levels:

- **Local enforcement**: Pre-commit hooks, commit message validation, and branch
  name validation
- **GitHub enforcement**: PR title validation, commit message validation, and
  automated checks
- **CI/CD integration**: Automated testing and security scanning

## 🚀 Quick Setup

### **Automatic Setup (Recommended)**

```bash
yarn install
```

This automatically:

- Installs all dependencies including commitlint
- Sets up husky git hooks via the `prepare` script
- Makes hook files executable
- Configures git commit template

### **Manual Setup (if needed)**

```bash
make setup-commits
```

### **Verify Setup**

```bash
# Test our custom commit validator
echo "feat(app): test message" > test-msg && node scripts/commit-validator.js test-msg && rm test-msg

# Test commitlint
echo "feat: test message" | npx commitlint
```

## 📝 Commit Message Format

We follow the [Conventional Commits](https://www.conventionalcommits.org/)
specification:

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `perf`: Performance improvements
- `test`: Adding or updating tests
- `build`: Build system changes
- `ci`: CI/CD changes
- `chore`: Maintenance tasks
- `revert`: Reverting previous commits

### Scopes

- `app`: Application module
- `firewall`: Firewall module
- `vpc`: VPC module
- `shared`: Shared libraries
- `scripts`: Build/deployment scripts
- `docs`: Documentation
- `config`: Configuration files
- `ci`: CI/CD configuration

### Examples

```bash
feat(app): add rule validation for network firewall policies
fix(firewall): resolve routing table update race condition
docs(shared): update API documentation for config loader
test(vpc): add integration tests for subnet creation
chore: update dependencies to latest versions
```

## 🌿 Branch Naming Convention

Branch names must follow this pattern:

- `feature/*` - New features
- `hotfix/*` - Critical bug fixes
- `release/*` - Release preparation

### Examples

```bash
feature/add-rule-validation
feature/improve-error-handling
hotfix/fix-critical-security-issue
hotfix/resolve-memory-leak
release/v2.1.0
release/v2.1.1-hotfix
```

## 🔧 Local Enforcement

### Pre-commit Hooks

Automatically run before each commit:

- **Branch name validation**: Ensures branch follows naming convention
- **Code linting**: ESLint for TypeScript/JavaScript
- **Code formatting**: Prettier for consistent formatting
- **Python syntax check**: Validates Python code syntax
- **TypeScript compilation**: Ensures TypeScript compiles without errors

### Commit Message Hook

- **Commitlint validation**: Validates commit message format
- **Interactive feedback**: Shows specific errors and suggestions

### Pre-push Hook

- **Test execution**: Runs all tests before push
- **Branch protection**: Prevents direct pushes to main/dev branches

### Making Commits

#### Interactive Commit (Recommended)

```bash
# Stage your changes
git add .

# Use our custom interactive commit helper
yarn commit
```

#### Manual Commit

```bash
# Stage your changes
git add .

# Commit with template (opens editor)
git commit

# Or commit directly
git commit -m "feat(app): add new validation feature"
```

#### Validating Commits

```bash
# Validate the last commit
make validate-commit

# Validate specific commit message
echo "feat(app): add validation" | npx commitlint
```

## 🐙 GitHub Enforcement

### Automated Checks

Every PR and push triggers:

- **Commit message validation**: All commits must follow conventional format
- **Branch name validation**: Feature branches must follow naming convention
- **PR title validation**: PR titles must follow conventional format
- **Code quality checks**: Linting, formatting, and compilation
- **Security scanning**: Dependency vulnerabilities and code security

### Branch Protection Rules

#### Main Branch

- ✅ Require PR reviews
- ✅ Require status checks to pass
- ✅ Require up-to-date branches
- ✅ Require conversation resolution
- ✅ Restrict direct pushes

#### Dev Branch

- ✅ Require PR reviews
- ✅ Require status checks to pass
- ✅ Require conversation resolution

### Required Status Checks

- `Commit Standards Enforcement / Validate Commit Messages`
- `Commit Standards Enforcement / Code Quality Checks`
- `Commit Standards Enforcement / Security Scan`
- `Commit Standards Enforcement / Enforce PR Title Format`

## 🛠️ Troubleshooting

### Common Issues

#### Commit Message Rejected

```bash
# Error: Commit message doesn't follow conventional format
# Solution: Use our interactive commit helper
yarn commit
```

#### Branch Name Invalid

```bash
# Error: Branch name doesn't follow pattern
# Solution: Rename your branch
git branch -m feature/your-feature-name
```

#### Pre-commit Hook Fails

```bash
# Error: Linting or formatting issues
# Solution: Fix issues automatically
yarn lint-fix
yarn prettier --write .
```

#### Tests Fail on Push

```bash
# Error: Tests fail in pre-push hook
# Solution: Fix tests or skip hook (emergency only)
git push --no-verify  # Use sparingly!
```

### Bypassing Hooks (Emergency Only)

```bash
# Skip pre-commit hooks
git commit --no-verify -m "emergency fix"

# Skip pre-push hooks
git push --no-verify
```

**⚠️ Warning**: Only use `--no-verify` in genuine emergencies. The hooks exist
to maintain code quality.

### Fixing Commit History

```bash
# Fix the last commit message
git commit --amend

# Interactive rebase to fix multiple commits
git rebase -i HEAD~3
```

## 📊 Monitoring and Reporting

### Local Reports

- **Build reports**: Generated during build process
- **Test reports**: Created during test execution
- **Security reports**: Generated by security scans

### GitHub Reports

- **PR checks**: Visible in PR status checks
- **Action logs**: Detailed logs in GitHub Actions
- **Security alerts**: Automated vulnerability notifications

## 🔄 Workflow Examples

### Feature Development

```bash
# 1. Clone and setup (first time only)
git clone <repository-url>
cd anfw-automate
yarn install  # Automatically sets up commit standards

# 2. Create feature branch
git checkout dev
git pull origin dev
git checkout -b feature/add-validation

# 3. Make changes and commit
git add .
yarn commit  # Our custom interactive commit helper

# 4. Push and create PR
git push origin feature/add-validation
# Create PR on GitHub

# 5. Address review feedback
git add .
yarn commit  # Use our interactive commit helper for consistency
git push origin feature/add-validation
```

### Hotfix Process

```bash
# 1. Create hotfix branch from main
git checkout main
git pull origin main
git checkout -b hotfix/fix-critical-issue

# 2. Make fix and commit
git add .
git commit -m "fix(app): resolve critical security issue"

# 3. Push and create PR to main
git push origin hotfix/fix-critical-issue
# Create PR targeting main branch
```

## 🎓 Best Practices

### Commit Messages

- **Be descriptive**: Explain what and why, not just what
- **Use imperative mood**: "add feature" not "added feature"
- **Keep subject under 50 characters**
- **Use body for detailed explanations**

### Branch Management

- **Keep branches focused**: One feature/fix per branch
- **Use descriptive names**: Clear indication of purpose
- **Delete merged branches**: Keep repository clean

### Code Quality

- **Run tests locally**: Before pushing changes
- **Fix linting issues**: Don't ignore warnings
- **Write meaningful tests**: Cover new functionality

## 📚 Additional Resources

- [Conventional Commits Specification](https://www.conventionalcommits.org/)
- [Semantic Versioning](https://semver.org/)
- [Git Best Practices](https://git-scm.com/book/en/v2)
- [GitHub Flow](https://guides.github.com/introduction/flow/)

## 🆘 Getting Help

If you encounter issues with commit standards:

1. **Check this documentation** for common solutions
2. **Run the setup script** again: `make setup-commits`
3. **Validate your setup**: `make validate-commit`
4. **Ask for help**: Create an issue or ask team members

Remember: These standards exist to maintain code quality and make collaboration
easier. When in doubt, err on the side of following the standards!
