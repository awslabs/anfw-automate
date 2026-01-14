# Security Scanning

## Overview

Security scanning is automated using npm/pip dev dependencies:

- **gitleaks** - Secret scanning (npm package)
- **bandit** - Python security scanning (pip package)
- **yarn audit** - Node.js dependency scanning (built-in)
- **cdk-nag** - CDK compliance checks (npm package)

## Quick Start

```bash
# Install all security tools
yarn install

# Run all security scans
make security:scan

# Run individual scans
make security:secrets    # gitleaks
make security:python     # bandit
make security:nodejs     # yarn audit
make security:cdk        # cdk-nag
```

## Automated Scanning

### Pre-Commit Hook

Automatically scans before each commit:

- Secret scanning (gitleaks)
- Python security (bandit)

### Pre-Push Hook

Comprehensive validation before push:

- All security scans
- Linting
- Tests

## Manual Scanning

```bash
# Scan for secrets
npx gitleaks detect --source . --verbose

# Scan Python code
bandit -r . -x "*/tests/*,**/node_modules/*,**/cdk.out/*"

# Check dependencies
yarn npm audit

# Validate CDK
cd app && npx cdk synth
```

## Fixing Issues

### Secrets Detected

1. Remove the secret from code
2. Use environment variables or AWS Secrets Manager
3. Add to `.gitleaksignore` if false positive

### Python Security Issues

1. Review bandit output
2. Fix the code issue
3. Add `# nosec` comment if false positive (use sparingly)

### Vulnerable Dependencies

```bash
make security:fix        # Update dependencies
make security:status     # Check status
```

## Configuration

- `.gitleaks.toml` - Path exclusions (build artifacts, dependencies)
- `.gitleaksignore` - Fingerprint-based ignores for specific false positives
- `bandit.yaml` - Bandit configuration
- Pre-commit hooks in `.husky/pre-commit`

## Best Practices

1. Never bypass security checks without review
2. Run `make security:scan` before creating PRs
3. Keep dependencies updated with `make security:fix`
4. Use AWS Secrets Manager for sensitive data
5. Review security warnings, don't just ignore them
