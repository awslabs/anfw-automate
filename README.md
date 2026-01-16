# Automate AWS Network Firewall Rule Management

> **⚠️ BREAKING CHANGE - Package Manager Migration**: This project has migrated
> from npm to Yarn 4.12.0. **All npm commands will no longer work.** Existing
> contributors must:
>
> 1. Install Yarn: `corepack enable` (or `npm install -g yarn`)
> 2. Remove old dependencies: `rm -rf node_modules package-lock.json`
> 3. Install with Yarn: `yarn install`
>
> See [docs/YARN_MIGRATION.md](docs/YARN_MIGRATION.md) for complete migration
> guide.

An event-based serverless application that automatically performs CRUD
operations on AWS Network Firewall rule-groups and rules based on distributed
configuration files. The application consist of three modules:

1. **VPC (Optional)** - Creates VPC based on configuration using AWS
   CodePipeline. Not required if you already have existing VPC in AWS Network
   Firewall and Application account.

2. **Firewall (Optional)** - Creates AWS Network Firewall endpoints, and updates
   the routing tables of VPCs as configured. This requires Transit Gateway to be
   configured for the account and already attached to the AWS Network Firewall
   VPC. Not required, if you have existing AWS Network Firewall Setup.

3. **Application** - Creates a event-based serverless application that updates
   the rules and rule-groups attached to the AWS Network Firewall managed by the
   application. The rules are must be maintained in application managed S3
   buckets. There is no limit on number of distributed configurations. The
   deployment is based on the configurations.

## 🚀 Quick Start

### Step 1: Install Prerequisites

**Required (install these first):**

```bash
# Check if you have the required tools
node --version    # Should be 20.8.1+
yarn --version    # Should be 4.0.0+
python3 --version # Should be 3.11+
git --version     # Any recent version
```

**Install Yarn (if not already installed):**

```bash
# Enable corepack (recommended - comes with Node.js 16.10+)
corepack enable

# Or install globally via npm
npm install -g yarn
```

**Optional (for AWS deployment):**

```bash
# Check if you have AWS CLI (optional)
aws --version
```

### Step 2: Setup Project

```bash
# Clone the repository
git clone <repository-url>
cd anfw-automate

# Install dependencies and setup commit standards
yarn install
```

### Step 3: Build and Test

**Requirements:** Just Node.js + Python

```bash
# Build and test
make build                 # Build all modules with comprehensive process (Python, TypeScript, CDK, security)
make test                  # Run all tests

# Deploy to AWS (requires AWS CLI + credentials)
make deploy
```

## 📋 Prerequisites

### Required Tools

Install these tools before starting:

#### Core Requirements (Always Needed)

- **[Node.js 20.8.1+](https://nodejs.org/)** - JavaScript runtime
- **[Yarn 4.0.0+](https://yarnpkg.com/)** - Package manager (install with
  `corepack enable`)
- **[Python 3.11+](https://www.python.org/)** - For Lambda functions
- **[Git](https://git-scm.com/)** - Version control

#### Optional Tools

- **[AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)** -
  For cloud deployment

### Auto-Installed Dependencies

These are installed automatically via `yarn install`:

- **Poetry** - Python package manager
- **Husky** - Git hooks for commit standards

### AWS Accounts (for Cloud Deployment)

- **Application Account (Dev)** - Deploy modules in development environment
- **Resource Account** - Deploy CI/CD pipeline for application deployment
- **Delegated Admin Account** (Optional) - Manage spoke accounts using StackSets
- **Spoke Account** (Optional) - Test application by mocking customer setup

## 🏗️ Project Structure

```
anfw-automate/
├── app/                    # Application module (Lambda functions)
├── firewall/              # Firewall module (Network Firewall resources)
├── vpc/                   # VPC module (VPC and networking)
├── shared/                # Shared libraries and utilities
├── scripts/               # Build and deployment scripts
├── tests/integration/     # Integration tests
├── conf/                  # Configuration files
└── DEVELOPMENT.md         # Detailed development guide
```

## 🔧 Development Workflow

### Commit Standards

Commit standards are automatically enforced both locally and on GitHub:

```bash
# Install dependencies (sets up commit hooks automatically)
yarn install

# Stage your changes
git add .

# Create conventional commits interactively
make commit
# or
yarn commit

# Validate commit messages
make validate-commit
```

**Commit Format**: `type(scope): description`

- `feat(app): add rule validation feature`
- `fix(firewall): resolve routing issue`
- `docs: update deployment guide`

**Branch Names**: `feature/*`, `hotfix/*`, `release/*`

**Automatic Setup**: Git hooks and commit validation are configured
automatically when you run `yarn install`.

See [docs/COMMIT_STANDARDS.md](docs/COMMIT_STANDARDS.md) for complete details.

### Branch Strategy

- `main` - Production-ready code
- `dev` - Development integration branch
- `feature/*` - Feature development branches
- `hotfix/*` - Critical bug fixes

### Local Development

```bash
# Install dependencies first
yarn install

# Build and test
make build            # Build all modules with comprehensive process (Python, TypeScript, CDK, security)
make test             # Run all tests
make deploy           # Deploy to AWS (requires credentials)

# Development workflow
make commit           # Create conventional commits
make lint             # Run code linting
make clean            # Clean build artifacts
```

## 🧪 Testing Strategy

### Unit Tests

- **Python**: pytest with coverage reporting
- **TypeScript**: Jest for CDK constructs
- **Location**: `test/` directories in each module

### Running Tests

```bash
# All tests
yarn test

# Module-specific tests
cd app && yarn test
```

## 🚀 Deployment Process

### Environment Progression

1. **Development** (`dev`) - AWS development account
2. **Production** (`prod`) - AWS production account

### Pipeline Architecture

Each module has its own AWS CodePipeline:

```
Source → Build → Deploy → [Manual Approval] → Production
```

#### Pipeline Features

- **Enhanced Build Process**: Comprehensive validation and testing
- **Security Scanning**: Automated security checks with bandit and pip-audit
- **Integration Testing**: Automated post-deployment validation
- **Multi-Region Support**: Deploy across multiple AWS regions
- **Rollback Capability**: Automatic rollback on deployment failures

## 📁 Configuration

### Enhanced Configuration Management

The project now uses an enhanced configuration management system that provides:

- **Multiple Configuration Sources**: SSM Parameter Store (primary) and JSON
  files (fallback)
- **Schema Validation**: Comprehensive validation with detailed error messages
- **Environment Overrides**: Environment-specific configuration merging
- **Module Isolation**: Independent configuration management per module
- **Error Handling**: Clear, actionable error messages for troubleshooting

#### Configuration Sources

The system supports multiple configuration sources with automatic fallback:

1. **SSM Parameter Store** (Primary)
   - Global: `/anfw-automate/{stage}/global/config`
   - Module: `/anfw-automate/{stage}/{module}/config`
   - Overrides: `/anfw-automate/{stage}/{module}/overrides`

2. **JSON Files** (Fallback)
   - Global: `conf/{stage}.json`
   - Module: `{module}/conf/{stage}.json`
   - Overrides: `{module}/conf/{stage}-overrides.json`

**Credential Handling**: The system gracefully handles AWS credential errors by
automatically falling back to file-based configuration. When AWS credentials are
not available or invalid, you'll see clean messages like:

```
SSM parameter '/anfw-automate/dev/global/config' not accessible (no AWS credentials), falling back to file-based config.
```

This ensures the system works seamlessly in both AWS environments (with SSM) and
local development environments (with files).

### Environment Configuration

Create `deploy_vars.sh` in the root directory:

```bash
#!/bin/bash
# Resource Account configuration
export ACCOUNT_RES=111122223333
export RES_ACCOUNT_AWS_PROFILE=deployer+res

# Application Account configuration
export ACCOUNT_PROD=222233334444
export PROD_ACCOUNT_AWS_PROFILE=deployer+app

# Deployment configuration
export AWS_PROFILE=${RES_ACCOUNT_AWS_PROFILE}
export STAGE=dev
export AWS_REGION=us-east-1
```

### Stage Configuration

Create `<STAGE>.json` in the `conf/` folder with enhanced validation:

```json
{
  "account": {
    "res": "111122223333",
    "prod": "222233334444"
  },
  "region": "us-east-1",
  "stage": "dev",
  "vpc": {
    "cidr": "10.0.0.0/16"
  },
  "firewall": {
    "name": "anfw-dev"
  }
}
```

**Schema Validation**: Each configuration file is automatically validated
against its corresponding schema (`conf/schema.json` for global config,
`{module}/conf/schema.json` for module-specific config). The system provides
detailed error messages for any validation failures:

```
Configuration validation failed for module 'app' in stage 'dev'
Validation errors:
  - environments.dev.vpc_id: VPC ID must match pattern vpc-* but got "invalid-vpc-id"
  - environments.dev.rule_order: Rule order must be one of: DEFAULT_ACTION_ORDER, STRICT_ORDER
  - firewall_policy_arns: Missing required property: firewall_policy_arns
```

**Environment Overrides**: You can create environment-specific override files
(e.g., `app/conf/dev-overrides.json`) that will be automatically merged with the
base configuration.

## 🔍 Monitoring and Observability

### Built-in Monitoring

- **CloudWatch Logs**: Centralized logging for all Lambda functions
- **X-Ray Tracing**: Distributed tracing for performance monitoring
- **CloudWatch Metrics**: Custom metrics for application performance
- **AWS Config**: Configuration compliance monitoring

### Integration Test Reports

- **Test Results**: JSON reports with detailed test outcomes
- **Performance Metrics**: Lambda execution times and resource utilization
- **Security Scan Results**: Vulnerability assessments and compliance checks

## 🛠️ Available Commands

All commands use Make as the primary interface for consistency.

### Setup Commands

```bash
make help                  # Show all available commands
make setup                 # Setup development environment
```

### Build & Test Commands

```bash
make build                 # Build all modules (shared first, then app/firewall/vpc)
make test                  # Run all tests
make lint                  # Run linting
make lint-fix              # Fix lint issues
make format                # Format code with Prettier
```

### Security Commands

```bash
make security:scan         # Run all security scans
make security:secrets      # Scan for hardcoded secrets (gitleaks)
make security:python       # Python security scan (bandit)
make security:nodejs       # Node.js dependency audit
make security:fix          # Fix vulnerable dependencies
make audit                 # Alias for security:nodejs
```

### Deployment Commands

```bash
make deploy                # Deploy all modules to AWS
make deploy:app            # Deploy app module
make deploy:firewall       # Deploy firewall module
make deploy:vpc            # Deploy vpc module
```

### Git & Commit Commands

```bash
make commit                # Create conventional commits interactively
make validate-commit       # Validate last commit message
```

### Utility Commands

```bash
make clean                 # Clean build artifacts
make update                # Update dependencies
```

### Module-Specific Commands

```bash
make build:app             # Build specific module
make test:firewall         # Test specific module
```

**Note**: Git hooks use the same `make` commands to ensure consistency between
manual runs and automated checks.

## 📚 Documentation

### Core Documentation (Root)

- **[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)** - Community code of conduct
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - How to contribute to this project
- **[LICENSE](LICENSE)** - Apache-2.0 license
- **[CHANGELOG.md](CHANGELOG.md)** - Version history and changes

### Development Guides (docs/)

- **[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)** - Comprehensive development
  guide
- **[docs/COMMANDS.md](docs/COMMANDS.md)** - Complete command reference
- **[docs/COMMIT_STANDARDS.md](docs/COMMIT_STANDARDS.md)** - Commit message
  standards
- **[docs/GLOSSARY.md](docs/GLOSSARY.md)** - Project terminology

### Configuration & Migration (docs/)

- **[docs/CONFIGURATION_MIGRATION.md](docs/CONFIGURATION_MIGRATION.md)** -
  Enhanced configuration migration guide
- **[docs/YARN_MIGRATION.md](docs/YARN_MIGRATION.md)** - npm to Yarn migration
  guide
- **[docs/SEMANTIC_VERSIONING.md](docs/SEMANTIC_VERSIONING.md)** - Versioning
  strategy
- **[docs/SECURITY_SCANNING.md](docs/SECURITY_SCANNING.md)** - Security scanning
  tools and practices

### Module Documentation

- **[app/README.md](app/README.md)** - Application module (Lambda functions)
- **[firewall/README.md](firewall/README.md)** - Firewall module (Network
  Firewall)
- **[vpc/README.md](vpc/README.md)** - VPC module (Networking)
- **[shared/README.md](shared/README.md)** - Shared libraries and utilities

## 🔒 Security

### Security Features

- **Secret Scanning**: gitleaks (npm package) scans for hardcoded credentials
- **Python Security**: bandit scans for security issues in Python code
- **Dependency Scanning**: yarn audit checks for vulnerable dependencies
- **CDK Compliance**: cdk-nag validates infrastructure against AWS best
  practices
- **IAM Least Privilege**: Minimal required permissions
- **Encryption**: All data encrypted in transit and at rest
- **Network Security**: VPC isolation and security groups

### Security Commands

```bash
make security:scan        # Run all security scans
make security:secrets     # Scan for hardcoded secrets (gitleaks)
make security:python      # Scan Python code (bandit)
make security:nodejs      # Check Node.js dependencies (yarn audit)
make security:fix         # Fix vulnerable dependencies
```

### Security Best Practices

- Never commit secrets or credentials (gitleaks prevents this)
- Use IAM roles instead of access keys
- Regular dependency updates with `make security:fix`
- Pre-commit hooks automatically scan full repository
- Security scanning runs on every push

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for
guidelines on:

- How to submit issues and pull requests
- Code standards and commit conventions
- Development workflow
- Security issue reporting

See [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) for detailed guidelines.

## 📄 License

This project is licensed under the Apache-2.0 License. See [LICENSE](LICENSE)
for details.

## 🆘 Support

### Troubleshooting

1. **Build Failures**: Check dependencies - no environment variables required
   for builds
2. **Deployment Issues**: Check AWS credentials and CloudFormation logs
3. **Configuration Issues**:
   - Check configuration file syntax and schema validation
   - Verify SSM parameter paths if using Parameter Store
   - Review detailed error messages for specific field-level issues
   - Use file-based configuration for local development when AWS credentials are
     not available

### Getting Help

1. Check existing documentation
2. Review CloudFormation stack events
3. Check pipeline execution logs
4. Create an issue in the repository

## 🔄 Migration from Previous Versions

### Enhanced Configuration Migration (Latest)

**✅ Migration Complete**: All modules now use enhanced configuration management
with improved error handling, schema validation, and multiple configuration
sources.

**Key Improvements**:

- Multiple configuration sources (SSM Parameter Store + JSON files)
- Comprehensive schema validation with detailed error messages
- Automatic fallback for local development
- Enhanced error handling and troubleshooting guidance

**No Action Required**: The migration is backward compatible. Existing
configurations continue to work without changes.

See [docs/CONFIGURATION_MIGRATION.md](docs/CONFIGURATION_MIGRATION.md) for
complete details.

### General Migration Steps

If upgrading from a previous version:

1. **Backup existing configurations**
2. **Update configuration files** to match new schema (optional - existing files
   work)
3. **Test locally** before deploying to production
4. **Follow the new commit standards** for future changes

## DEPENDENCIES

This list of dependencies are needed to build the project. These packages are
not part of the solution.

### Python dependencies

| Package               | Version  |
| --------------------- | -------- |
| aws-lambda-powertools | ^2.25.1  |
| aws-xray-sdk          | ^2.12.0  |
| jsonschema            | ^4.19.1  |
| python                | ^3.11    |
| pyyaml                | ^6.0.1   |
| requests              | ^2.32.4  |
| pytest                | ^8.0.2   |
| bandit                | ^1.7.7   |
| pip-audit             | ^2.7.2   |
| pip-licenses          | ^4.3.4   |
| boto3                 | ^1.34.52 |

### Typescript dependencies

| Package                          | Version          |
| -------------------------------- | ---------------- |
| @types/jest                      | ^29.5.12         |
| @types/node                      | 20.11.30         |
| aws-cdk                          | 2.135.0          |
| jest                             | ^29.7.0          |
| ts-jest                          | ^29.1.2          |
| ts-node                          | ^10.9.2          |
| typescript                       | ~5.4.3           |
| @aws-cdk/aws-lambda-python-alpha | ^2.135.0-alpha.0 |
| aws-cdk-lib                      | 2.206.0          |
| cdk-nag                          | ^2.37.55         |
| constructs                       | ^10.0.0          |
| source-map-support               | ^0.5.21          |
| ajv                              | ^8.12.0          |
| ajv-formats                      | ^3.0.1           |

## 📖 Appendix

Please refer to [docs/GLOSSARY.md](docs/GLOSSARY.md) before creating any
configuration files.

## Security

For security vulnerability reporting, see the [Security](../../security) tab or
[CONTRIBUTING.md](CONTRIBUTING.md#security-issue-notifications).

For security scanning tools and best practices, see
[docs/SECURITY_SCANNING.md](docs/SECURITY_SCANNING.md).

## License

This project is licensed under the Apache-2.0 License.
