# Command Reference

This document provides a comprehensive reference for all available commands in
the project.

## Command Philosophy

**Make is the primary interface** - All user-facing commands use `make` to
ensure consistency between:

- Manual developer runs
- Git hook automation
- CI/CD pipelines

This approach guarantees that security scans, tests, and builds use identical
configurations and behavior regardless of how they're invoked.

## Quick Reference

### Essential Commands

```bash
make help                  # Show all available commands
make setup                 # First-time setup (install dependencies + git hooks)
make build                 # Build all modules
make test                  # Run all tests
make commit                # Create conventional commits interactively
```

### Security Commands

```bash
make security:scan         # Run all security scans
make security:secrets      # Scan for secrets (gitleaks)
make security:python       # Python security (bandit)
make security:nodejs       # Node.js audit
make security:fix          # Fix vulnerabilities
make security:fix-force    # Force fix (may break compatibility)

# Note: CDK NAG compliance checks run automatically during 'make build'
```

### Development Commands

```bash
make lint                  # Run linting
make lint-fix              # Fix lint issues
make format                # Format code with Prettier
make clean                 # Clean build artifacts
make update                # Update dependencies
```

### Deployment Commands

```bash
make deploy                # Deploy all modules
make deploy:app            # Deploy app module
make deploy:firewall       # Deploy firewall module
make deploy:vpc            # Deploy vpc module
```

### Module-Specific Commands

```bash
make build:app             # Build app module
make build:firewall        # Build firewall module
make build:vpc             # Build vpc module
make build:shared          # Build shared module

make test:app              # Test app module
make test:firewall         # Test firewall module
make test:vpc              # Test vpc module
make test:shared           # Test shared module
```

## Command Details

### Setup & Installation

#### `make setup`

Sets up the development environment:

- Installs all dependencies via `yarn install`
- Configures git hooks via `yarn prepare`
- Installs security tools (gitleaks, bandit)

**When to use**: First time setup or after pulling major changes

```bash
make setup
```

#### `make help`

Displays all available make commands with descriptions.

```bash
make help
```

### Build Commands

#### `make build`

Builds all modules in the correct order:

1. Builds shared module first (required by others)
2. Builds app, firewall, and vpc modules in parallel

**What it does**:

- Compiles TypeScript to JavaScript
- Packages Python Lambda functions
- Validates CDK constructs
- Runs pre-synth scripts

```bash
make build
```

#### `make build:<module>`

Builds a specific module (app, firewall, vpc, or shared).

```bash
make build:app
make build:shared
```

### Test Commands

#### `make test`

Runs all tests across all modules:

- TypeScript/CDK tests (Jest)
- Python tests (pytest)

```bash
make test
```

#### `make test:<module>`

Runs tests for a specific module.

```bash
make test:app
make test:firewall
```

### Code Quality Commands

#### `make lint`

Runs ESLint on all TypeScript/JavaScript files across all modules.

```bash
make lint
```

#### `make lint-fix`

Automatically fixes linting issues where possible.

```bash
make lint-fix
```

#### `make format`

Formats all code files using Prettier:

- TypeScript/JavaScript
- JSON
- Markdown
- YAML

```bash
make format
```

### Security Commands

All security commands use the same configurations as git hooks, ensuring
consistency.

#### `make security:scan`

Runs comprehensive security scanning:

- Secret scanning (gitleaks)
- Python security (bandit)
- Node.js audit (yarn audit)
- CDK compliance (cdk-nag)

**Configuration files**:

- `.gitleaks.toml` - Secret scanning rules
- `bandit.yaml` - Python security rules

```bash
make security:scan
```

#### `make security:secrets`

Scans for hardcoded secrets and credentials using gitleaks.

**Uses**: `.gitleaks.toml` configuration

```bash
make security:secrets
```

#### `make security:python`

Scans Python code for security issues using bandit.

**Uses**: `bandit.yaml` configuration

```bash
make security:python
```

#### `make security:nodejs`

Audits Node.js dependencies for known vulnerabilities.

```bash
make security:nodejs
```

#### `make security:fix`

Attempts to fix vulnerable dependencies by updating them.

```bash
make security:fix
```

#### `make security:fix-force`

Force updates all dependencies (may introduce breaking changes).

**⚠️ Warning**: Use with caution - may break compatibility.

```bash
make security:fix-force
```

### Git & Commit Commands

#### `make commit`

Interactive conventional commit helper:

- Prompts for commit type (feat, fix, docs, etc.)
- Prompts for scope (app, firewall, vpc, etc.)
- Prompts for description
- Validates commit message format
- Triggers git hooks (linting, security scans)

```bash
make commit
```

#### `make validate-commit`

Validates the last commit message against conventional commit standards.

```bash
make validate-commit
```

### Deployment Commands

#### `make deploy`

Deploys all modules to AWS:

1. Builds all modules
2. Deploys app module
3. Deploys firewall module
4. Deploys vpc module

**Requires**: AWS credentials configured

```bash
make deploy
```

#### `make deploy:<module>`

Deploys a specific module to AWS.

```bash
make deploy:app
make deploy:firewall
make deploy:vpc
```

### Utility Commands

#### `make clean`

Cleans all build artifacts:

- Removes compiled JavaScript files
- Removes CDK output directories
- Removes Python build artifacts
- Removes build reports

```bash
make clean
```

#### `make update`

Updates all dependencies to their latest versions.

```bash
make update
```

## Git Hooks

Git hooks automatically run make commands to ensure consistency:

### Pre-commit Hook

Runs before each commit:

- `yarn validate:branch` - Validates branch name
- `yarn exec lint-staged` - Formats staged files
- `make security:secrets` - Scans for secrets
- `make security:python` - Scans Python code

### Pre-push Hook

Runs before each push:

- `make lint` - Runs linting
- `make security:scan` - Comprehensive security scan
- `make test` - Runs all tests

### Commit-msg Hook

Runs when creating commits:

- Validates commit message format
- Ensures conventional commit standards

## Yarn Scripts (Internal Use)

These scripts are used internally by Make commands and git hooks. Users should
use Make commands instead.

### Build Scripts

- `yarn build` - Orchestrates workspace builds
- `yarn build:shared` - Builds shared module
- `yarn build:modules` - Builds app/firewall/vpc modules

### Utility Scripts

- `yarn clean` - Cleans workspace artifacts
- `yarn prepare` - Sets up git hooks (called by yarn install)
- `yarn commit` - Interactive commit helper (called by make commit)
- `yarn validate:branch` - Branch name validation (called by git hooks)

### Release Scripts

- `yarn changelog:unreleased` - Show unreleased changes
- `yarn changelog:preview` - Preview next release
- `yarn changelog:release` - Generate release changelog
- `yarn release` - Create semantic release
- `yarn version:sync` - Synchronize versions across modules

## Troubleshooting

### Command Not Found

If you get "command not found" errors:

```bash
# Ensure dependencies are installed
make setup

# Or manually
yarn install
```

### Permission Denied

If git hooks fail with permission errors:

```bash
# Fix hook permissions
chmod +x .husky/*
```

### Security Scan Failures

If security scans fail:

```bash
# Check specific scan
make security:secrets
make security:python
make security:nodejs

# Attempt to fix
make security:fix
```

### Build Failures

If builds fail:

```bash
# Clean and rebuild
make clean
make build

# Build specific module
make build:shared  # Build shared first
make build:app     # Then build app
```

## Best Practices

1. **Always use Make commands** - Don't call yarn scripts directly
2. **Run `make setup` first** - On initial clone or after major updates
3. **Use `make commit`** - For conventional commits with validation
4. **Check `make help`** - When unsure about available commands
5. **Run `make security:scan`** - Before pushing changes
6. **Use module-specific commands** - When working on a single module

## See Also

- [DEVELOPMENT.md](DEVELOPMENT.md) - Development workflow guide
- [CONTRIBUTING.md](CONTRIBUTING.md) - Contribution guidelines
- [COMMIT_STANDARDS.md](COMMIT_STANDARDS.md) - Commit message standards
