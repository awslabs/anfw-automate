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

The enhanced configuration management system provides production-ready features
for managing configuration across multiple modules (app, vpc, firewall) with
support for:

- **Multiple Configuration Sources**: SSM Parameter Store and JSON files
- **Schema Validation**: Comprehensive validation with detailed error messages
- **Environment Overrides**: Environment-specific configuration merging
- **Module Isolation**: Independent configuration management per module
- **Error Handling**: Clear, actionable error messages for troubleshooting

### Usage

#### Basic Usage

```typescript
import { createConfigurationManager } from './lib/config_loader';

const configManager = createConfigurationManager();

// Load module configuration
const moduleConfig = await configManager.loadConfig('app', 'dev');

// Validate configuration against schema
const validation = configManager.validateConfig(config, schema);
if (!validation.isValid) {
  console.error('Validation errors:', validation.errors);
}

// Merge configurations
const mergedConfig = configManager.mergeConfigs(baseConfig, overrides);

// Load secrets from SSM
const secrets = await configManager.getSecrets([
  '/anfw-automate/dev/database/password',
  '/anfw-automate/dev/api/key',
]);
```

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

#### Schema Validation

Each module has its own schema for validation:

- Global schema: `conf/schema.json`
- Module schemas: `{module}/conf/schema.json`

The system automatically validates configurations against the appropriate schema
and provides detailed error messages:

```typescript
// Example validation error output
Configuration validation failed for module 'app' in stage 'dev'
Validation errors:
  - environments.dev.vpc_id: VPC ID must match pattern vpc-* but got "invalid-vpc-id"
  - environments.dev.rule_order: Rule order must be one of: DEFAULT_ACTION_ORDER, STRICT_ORDER
  - firewall_policy_arns: Missing required property: firewall_policy_arns
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

The enhanced configuration manager is fully backward compatible. All module
entry points have been successfully migrated to use the enhanced configuration
system.

**Migration Complete**: All module entry points (`app/bin/app.ts`,
`vpc/bin/vpc.ts`, `firewall/bin/firewall.ts`) have been updated to use enhanced
configuration management with improved error handling while maintaining backward
compatibility.

**Key Improvements in Stack Entry Points**:

- ✅ Enhanced error handling with `ConfigurationError` class
- ✅ Detailed validation of required configuration fields
- ✅ Clear troubleshooting guidance when configuration fails
- ✅ Structured error messages with field-level details
- ✅ Improved logging with status indicators
- ✅ Type safety improvements (reduced use of `any` types)
- ✅ Automatic fallback from SSM to file-based configuration
- ✅ Comprehensive schema validation for all modules

**Legacy Support**: Existing code using `loadDeploymentConfig()` and
`loadDeploymentConfigSync()` will continue to work without changes, but new
development should use the enhanced configuration manager.

To migrate to the enhanced features:

```typescript
// Legacy approach
import { loadDeploymentConfig } from './lib/config_loader';
const config = await loadDeploymentConfig(configBasePath, stage, stackType);

// Enhanced approach
import { createConfigurationManager } from './lib/config_loader';
const configManager = createConfigurationManager();
const moduleConfig = await configManager.loadConfig(module, stage);
```

### Error Handling

The system provides comprehensive error handling with the `ConfigurationError`
class:

```typescript
import { ConfigurationError } from './lib/config_loader';

try {
  const config = await configManager.loadConfig('app', 'dev');
} catch (error) {
  if (error instanceof ConfigurationError) {
    console.error(error.getDetailedMessage());
    // Provides structured error information with field-level details
  }
}
```

## Examples

The `examples/` directory contains working demonstrations:

### `enhanced-config-example.ts`

Basic demonstration of enhanced configuration management features including:

- Configuration validation with detailed error messages
- Configuration merging with environment overrides
- Error handling with structured error reporting

### `module-config-demo.ts`

Advanced demonstration showing:

- Module-specific schema validation using real schemas from `app/conf`,
  `vpc/conf`, `firewall/conf`
- Environment isolation and configuration merging
- Schema path resolution and error handling
- Integration with actual module configurations

### `enhanced-stack-demo.ts`

Production demonstration showing:

- Enhanced configuration management in actual CDK stack entry points
- Improved error handling and validation in stack deployment
- Fallback behavior from SSM to file-based configuration
- Better developer experience with clear error messages and troubleshooting
  guidance

To run the examples:

```bash
cd shared
npx ts-node examples/enhanced-config-example.ts
npx ts-node examples/module-config-demo.ts
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
