# Shared Libraries

This section contains common libraries used by all modules, including enhanced
configuration management, shared constructs, and utility functions for
production-ready AWS infrastructure deployment.

## Overview

The shared library provides:

- **Enhanced Configuration Management**: Production-ready configuration loading
  with validation, merging, and error handling
- **Tagged Stack Constructs**: Common CDK constructs with standardized tagging
  and monitoring
- **Utility Functions**: Helper functions for consistent infrastructure patterns

## Enhanced Configuration Management

### Features

Production-ready configuration loading with:

- **Multiple Configuration Sources**: SSM Parameter Store (primary) with JSON
  file fallback
- **Schema Validation**: Automatic validation with detailed error messages
- **Environment Overrides**: Environment-specific configuration merging
- **Module Isolation**: Independent configuration per module
- **Error Handling**: Clear, actionable error messages

### Usage

#### For Developers (Simple)

In your CDK stack entry point (e.g., `app/bin/app.ts`):

```typescript
import { loadDeploymentConfig } from '../../shared/lib/config_loader';

// Load configuration - that's it!
const config = await loadDeploymentConfig(__dirname, 'dev', 'app');
// Returns: { stage, globalConfig, appConfig }
```

The function automatically:

- Tries SSM Parameter Store first (`/anfw-automate/{stage}/{module}/config`)
- Falls back to JSON files (`{module}/conf/{stage}.json`)
- Validates against schemas (`conf/schema.json`, `{module}/conf/schema.json`)
- Exits with clear error messages if configuration is invalid

#### Advanced Usage (Optional)

For custom configuration logic, use the `ConfigurationManager`:

```typescript
import { createConfigurationManager } from '../../shared/lib/config_loader';

const configManager = createConfigurationManager();

// Load module configuration
const moduleConfig = await configManager.loadConfig('app', 'dev');

// Validate configuration against schema
const validation = configManager.validateConfig(config, schema);

// Merge configurations
const mergedConfig = configManager.mergeConfigs(baseConfig, overrides);

// Load secrets from SSM
const secrets = await configManager.getSecrets(['/anfw-automate/dev/api/key']);
```

#### Configuration Sources

The system tries sources in this order:

1. **SSM Parameter Store** (Primary)
   - Global: `/anfw-automate/{stage}/global/config`
   - Module: `/anfw-automate/{stage}/{module}/config`

2. **JSON Files** (Fallback)
   - Global: `conf/{stage}.json`
   - Module: `{module}/conf/{stage}.json`

**No AWS Credentials?** The system automatically falls back to file-based
configuration when AWS credentials are unavailable, making local development
seamless.

#### Schema Validation

Each module has its own schema:

- Global: `conf/schema.json`
- Module: `{module}/conf/schema.json`

Validation errors are detailed and actionable:

```
Configuration validation failed for module 'app' in stage 'dev'
Validation errors:
  - environments.dev.vpc_id: VPC ID must match pattern vpc-*
  - firewall_policy_arns: Missing required property
```

#### Environment Overrides

Support for environment-specific configuration overrides:

```typescript
// Base configuration
const baseConfig = {
  environments: {
    dev: {
      resources: { instance_types: ['t3.micro'] },
      scaling: { max_capacity: 3 },
    },
  },
  features: { advanced_logging: false },
};

// Environment-specific overrides
const overrides = {
  environments: {
    dev: {
      resources: { instance_types: ['t3.small'] }, // Override instance type
      scaling: { max_capacity: 5 }, // Override scaling
    },
  },
  features: { advanced_logging: true }, // Enable feature
};

const merged = configManager.mergeConfigs(baseConfig, overrides);
// Result: dev environment uses t3.small instances with max_capacity 5 and advanced_logging enabled
```

### Migration from Legacy Configuration

The enhanced configuration manager is fully backward compatible.

**For most developers**: Just use `loadDeploymentConfig()` - it handles
everything automatically.

**Legacy code** using `loadDeploymentConfigSync()` will continue to work but
should migrate to the async version:

```typescript
// Old (deprecated)
const config = loadDeploymentConfigSync(configBasePath, stage, stackType);

// New (recommended)
const config = await loadDeploymentConfig(configBasePath, stage, stackType);
```

### Error Handling

Configuration errors provide clear troubleshooting guidance:

```typescript
import { ConfigurationError } from '../../shared/lib/config_loader';

try {
  const config = await configManager.loadConfig('app', 'dev');
} catch (error) {
  if (error instanceof ConfigurationError) {
    console.error(error.getDetailedMessage());
    // Shows field-level details and next steps
  }
}
```

## Testing

The shared library includes comprehensive test coverage:

- `test/config_loader.test.ts`: Unit tests for enhanced configuration management
- `test/module-config-integration.test.ts`: Integration tests with real module
  schemas
- `test/shared.test.ts`: General shared library tests

Run tests:

```bash
cd shared
yarn test
```

## Configuration Schema Structure

### Global Configuration Schema (`conf/schema.json`)

```json
{
  "project": { "project_name": "string", "module_name": "string" },
  "base": { "primary_region": "string", "target_account_id": "string" },
  "pipeline": { "repo_name": "string", "repo_branch_name": "string" }
}
```

### Module-Specific Schemas

Each module (`app`, `vpc`, `firewall`) has its own schema in
`{module}/conf/schema.json` defining module-specific configuration requirements.

## DEPENDENCIES

This list of dependencies are needed to build the project. These packages are
not part of the solution.

### Typescript dependencies

| Package     | Version  | Purpose                       |
| ----------- | -------- | ----------------------------- |
| @types/jest | ^29.5.12 | Jest type definitions         |
| @types/node | 20.11.30 | Node.js type definitions      |
| aws-cdk-lib | 2.206.0  | AWS CDK library               |
| constructs  | ^10.0.0  | CDK constructs                |
| jest        | ^29.7.0  | Testing framework             |
| ts-jest     | ^29.1.2  | TypeScript Jest transformer   |
| typescript  | ~5.4.3   | TypeScript compiler           |
| ajv         | ^8.12.0  | JSON schema validation        |
| ajv-formats | ^3.0.1   | Additional validation formats |

### Runtime Dependencies

| Package             | Version | Purpose                         |
| ------------------- | ------- | ------------------------------- |
| @aws-sdk/client-ssm | Latest  | SSM Parameter Store integration |

## APPENDIX

Please refer the [GLOSSARY](../GLOSSARY.md) before creating any configuration
files

## Security

See [CONTRIBUTING](../CONTRIBUTING.md#security-issue-notifications) for more
information.

## License

This project is licensed under the Apache-2.0 License.
