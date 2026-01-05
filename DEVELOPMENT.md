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
npm install -g @commitlint/cli @commitlint/config-conventional
```

## Local Development Setup

### Prerequisites

- Docker and Docker Compose
- Node.js 18+
- Python 3.11+
- Poetry (Python package manager)
- AWS CLI (optional, for cloud testing)

### Quick Setup

```bash
# Complete local development setup (one command!)
make local
```

This single command:

- Installs all project dependencies
- Sets up commit standards and git hooks automatically
- Configures LocalStack for local AWS simulation
- Creates local configuration files
- Starts LocalStack containers
- Provides helpful next steps

### Manual Setup (if needed)

If you prefer step-by-step setup:

```bash
# 1. Install dependencies (sets up commit standards)
npm install

# 2. Setup local environment
make local-setup

# 3. Start LocalStack
make local-start
```

### Manual Setup

1. **Start LocalStack**:

```bash
docker-compose -f docker-compose.local.yml up -d
```

2. **Source local environment**:

```bash
source deploy_vars.local.sh
```

3. **Install dependencies**:

```bash
# Install shared module
cd shared && npm install && npm run build && cd ..

# Install module dependencies
for module in app firewall vpc; do
    cd $module
    npm install
    # Install Python dependencies if they exist
    if [ -d "src" ]; then
        cd src && poetry install --no-root && cd ..
    fi
    cd ..
done
```

### Local Configuration

#### Environment Variables (`deploy_vars.local.sh`)

```bash
export AWS_PROFILE=localstack
export STAGE=local
export AWS_REGION=us-east-1
export AWS_ENDPOINT_URL=http://localhost:4566
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
```

#### Application Configuration (`conf/local.json`)

```json
{
  "account": {
    "res": "000000000000",
    "prod": "000000000000"
  },
  "region": "us-east-1",
  "stage": "local",
  "vpc": {
    "cidr": "10.0.0.0/16"
  },
  "firewall": {
    "name": "anfw-local"
  }
}
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

2. **JSON Files** (Fallback - for local development)
   - Global: `conf/{stage}.json`
   - Module: `{module}/conf/{stage}.json`
   - Overrides: `{module}/conf/{stage}-overrides.json`

#### Local Development Configuration

For local development, the system automatically falls back to file-based
configuration when AWS credentials are not available. You'll see messages like:

```
SSM parameter '/anfw-automate/local/global/config' not accessible (no AWS credentials), falling back to file-based config.
```

This is expected behavior and allows seamless local development without AWS
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
make local  # Complete setup: dependencies + LocalStack + commit standards
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
make build                 # Build all modules using npm workspaces
make build-make           # Alternative: build using individual Makefiles

# Deploy to LocalStack
make local-deploy

# Run integration tests
make integration-test
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
npm test                    # All modules
cd app && npm test         # Specific module
```

## Deployment Process

### Environment Progression

1. **Local** (`local`): LocalStack development
2. **Development** (`dev`): AWS development account
3. **Production** (`prod`): AWS production account

### Deployment Commands

```bash
# Local deployment
source deploy_vars.local.sh
make deploy

# Environment deployment (via CodePipeline)
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

1. **LocalStack not starting**:
   - Check Docker daemon is running
   - Verify port 4566 is available
   - Check Docker Compose logs

2. **Build failures**:
   - Verify all dependencies are installed
   - Check Python virtual environment
   - No environment variables required for builds (STACK_NAME auto-detected)
   - Validate TypeScript compilation

3. **Deployment issues**:
   - Verify AWS credentials
   - Check CloudFormation stack status
   - Review pipeline logs

### Getting Help

1. Check existing documentation
2. Review CloudFormation stack events
3. Check pipeline execution logs
4. Consult team members

## Useful Commands

```bash
# Development
make build                 # Build all modules using npm workspaces
make build-make           # Alternative: build using individual Makefiles
make clean                 # Clean build artifacts
make update                # Update dependencies

# Module-specific development
cd app && make build       # Build specific module
cd app && make test        # Test specific module

# Local testing
docker-compose -f docker-compose.local.yml up -d    # Start LocalStack
docker-compose -f docker-compose.local.yml down     # Stop LocalStack

# Git workflow
git config commit.template .gitmessage              # Set commit template
git log --oneline --graph                           # View commit history

# AWS operations
aws --endpoint-url=http://localhost:4566 s3 ls      # LocalStack S3
aws cloudformation describe-stacks                   # Check stack status
```
