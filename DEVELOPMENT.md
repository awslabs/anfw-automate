# Development Workflow Guide

This document outlines the improved development workflow for the AWS Network
Firewall automation project, including commit standards, local development
setup, and deployment processes.

## Table of Contents

1. [Commit Standards](#commit-standards)
2. [Local Development Setup](#local-development-setup)
3. [Development Workflow](#development-workflow)
4. [Testing Strategy](#testing-strategy)
5. [Deployment Process](#deployment-process)
6. [Integration Testing](#integration-testing)

## Commit Standards

### Commit Message Format

We follow the [Conventional Commits](https://www.conventionalcommits.org/)
specification:

```
<type>(<scope>): <subject>

<body>

<footer>
```

#### Types

- `feat`: A new feature
- `fix`: A bug fix
- `docs`: Documentation only changes
- `style`: Changes that do not affect the meaning of the code
- `refactor`: A code change that neither fixes a bug nor adds a feature
- `perf`: A code change that improves performance
- `test`: Adding missing tests or correcting existing tests
- `build`: Changes that affect the build system or external dependencies
- `ci`: Changes to our CI configuration files and scripts
- `chore`: Other changes that don't modify src or test files
- `revert`: Reverts a previous commit

#### Scopes

- `app`: Application module changes
- `firewall`: Firewall module changes
- `vpc`: VPC module changes
- `shared`: Shared library changes
- `scripts`: Build/deployment script changes
- `docs`: Documentation changes
- `config`: Configuration changes
- `ci`: CI/CD pipeline changes

#### Examples

```bash
feat(app): add rule validation for network firewall policies
fix(firewall): resolve routing table update race condition
docs(shared): update API documentation for config loader
test(app): add integration tests for lambda functions
```

### Setting Up Commit Standards

1. Configure git to use the commit message template:

```bash
git config commit.template .gitmessage
```

2. Install commitlint (optional but recommended):

```bash
yarn global add @commitlint/cli @commitlint/config-conventional
```

## Local Development Setup

### Prerequisites

- Node.js 20.8.1+
- Yarn 4.0.0+ (install with `corepack enable`)
- Python 3.11+
- Poetry (Python package manager)
- AWS CLI (for AWS deployment)

### Quick Setup

```bash
# Install all project dependencies and setup commit standards
yarn install
```

This single command:

- Installs all project dependencies
- Sets up commit standards and git hooks automatically
- Configures the development environment

### Building the Project

After installation, build all modules:

```bash
# Build all modules using yarn workspaces
make build

# Or build individual modules
cd app && make build
cd firewall && make build
cd vpc && make build
```

### Enhanced Configuration Management

The project uses an enhanced configuration management system that provides:

- **Multiple Configuration Sources**: SSM Parameter Store (primary) and JSON
  files (fallback)
- **Schema Validation**: Comprehensive validation with detailed error messages
- **Environment Overrides**: Environment-specific configuration merging
- **Error Handling**: Clear, actionable error messages for troubleshooting

#### Configuration Sources

1. **SSM Parameter Store** (Primary - for AWS environments)
   - Global: `/anfw-automate/{stage}/global/config`
   - Module: `/anfw-automate/{stage}/{module}/config`
   - Overrides: `/anfw-automate/{stage}/{module}/overrides`

2. **JSON Files** (Fallback)
   - Global: `conf/{stage}.json`
   - Module: `{module}/conf/{stage}.json`
   - Overrides: `{module}/conf/{stage}-overrides.json`

#### Development Configuration

The system automatically falls back to file-based configuration when AWS
credentials are not available. This allows you to build and test code locally
without AWS credentials. You'll see messages like:

```
SSM parameter '/anfw-automate/dev/global/config' not accessible (no AWS credentials), falling back to file-based config.
```

This is expected behavior and allows seamless development without AWS
credentials.

## Development Workflow

### Branch Strategy

- `main`: Production-ready code
- `dev`: Development integration branch
- `feature/*`: Feature development branches
- `hotfix/*`: Critical bug fixes

### Development Process

1. **Initial setup** (first time only):

```bash
git clone <repository-url>
cd anfw-automate
yarn install  # Install dependencies and setup commit standards
make build    # Build all modules
```

2. **Create feature branch**:

```bash
git checkout dev
git pull origin dev
git checkout -b feature/your-feature-name
```

3. **Make changes and test locally**:

```bash
# Build and test
make build                 # Build all modules using yarn workspaces
make test                  # Run all tests

# For AWS deployment (requires AWS credentials)
# Configure deploy_vars.sh with your AWS settings
source deploy_vars.sh
make deploy
```

4. **Commit with proper format**:

```bash
git add .
make commit  # Interactive conventional commit helper
```

5. **Push and create PR**:

```bash
git push origin feature/your-feature-name
# Create PR to dev branch
```

### Code Quality Checks

Pre-commit hooks automatically run:

- Branch name validation
- Python syntax validation
- TypeScript compilation check
- ESLint and Prettier formatting
- Commit message validation

## Testing Strategy

### Unit Tests

- **Python**: pytest with coverage reporting
- **TypeScript**: Jest for CDK constructs
- **Location**: `test/` directories in each module

### Running Tests

```bash
# Unit tests
yarn test                    # All modules
cd app && yarn test         # Specific module
```

## Deployment Process

### Environment Progression

1. **Development** (`dev`): AWS development account
2. **Production** (`prod`): AWS production account

### Deployment Commands

```bash
# Manual deployment to AWS (requires AWS credentials)
source deploy_vars.sh
make deploy

# Automated deployment (via CodePipeline)
# Triggered automatically on branch push:
# - dev branch → dev environment
# - main branch → prod environment
```

### Pipeline Structure

Each module (app, firewall, vpc) has its own CodePipeline:

1. **Source**: CodeCommit/GitHub repository
2. **Build**: Enhanced build with validation
3. **Deploy**: Multi-region deployment
4. **Approval**: Manual approval for production

## Best Practices

### Code Quality

1. **Follow TypeScript/Python style guides**
2. **Write comprehensive tests**
3. **Use meaningful variable names**
4. **Add proper error handling**
5. **Document complex logic**

### Security

1. **Never commit secrets**
2. **Use IAM roles with least privilege**
3. **Enable security scanning in pipelines**
4. **Regular dependency updates**

### Performance

1. **Optimize Lambda cold starts**
2. **Use appropriate timeout values**
3. **Monitor resource utilization**
4. **Implement proper retry logic**

## Troubleshooting

### Common Issues

1. **Build failures**:
   - Verify all dependencies are installed with `yarn install`
   - Check Python virtual environment
   - No environment variables required for builds (STACK_NAME auto-detected)
   - Validate TypeScript compilation with `make build`

2. **Test failures**:
   - Ensure all modules are built before running tests
   - Check Python dependencies are installed with Poetry
   - Review test output for specific error messages

3. **Deployment issues**:
   - Verify AWS credentials are configured
   - Check CloudFormation stack status
   - Review pipeline logs in AWS CodePipeline

### Getting Help

1. Check existing documentation
2. Review CloudFormation stack events
3. Check pipeline execution logs
4. Consult team members

## Useful Commands

```bash
# Development
make build                 # Build all modules using yarn workspaces
make build-make           # Alternative: build using individual Makefiles
make test                  # Run all tests
make clean                 # Clean build artifacts
make update                # Update dependencies

# Module-specific development
cd app && make build       # Build specific module
cd app && make test        # Test specific module

# Git workflow
git config commit.template .gitmessage              # Set commit template
make commit                                         # Interactive commit helper
git log --oneline --graph                           # View commit history

# AWS operations (requires AWS credentials)
aws cloudformation describe-stacks                   # Check stack status
aws logs tail /aws/lambda/function-name --follow    # View Lambda logs
```
