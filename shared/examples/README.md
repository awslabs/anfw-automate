# Enhanced Configuration Management Examples

This directory contains working examples demonstrating the enhanced
configuration management features of the shared library.

### 3. `enhanced-stack-demo.ts`

**Purpose**: Demonstration of enhanced configuration management in actual CDK
stack entry points

**What it demonstrates**:

- How the enhanced configuration management improves the actual CDK stack entry
  points
- Enhanced error handling and validation in production stack deployment
- Fallback behavior from SSM Parameter Store to file-based configuration
- Improved logging and troubleshooting guidance
- Type safety improvements and better developer experience

**Key Features Shown**:

- Enhanced error handling with `ConfigurationError` class in stack entry points
- Detailed validation of required configuration fields before stack creation
- Clear troubleshooting guidance when configuration loading fails
- Structured error messages with field-level details for easier debugging
- Improved logging with status indicators and clear progress messages
- Backward compatibility with existing `loadDeploymentConfig` function

**Run with**:

```bash
npx ts-node examples/enhanced-stack-demo.ts
```

## Examples Overview

### 1. `enhanced-config-example.ts`

**Purpose**: Basic demonstration of core enhanced configuration management
features

**What it demonstrates**:

- Configuration validation with detailed error messages
- Configuration merging with environment-specific overrides
- Enhanced error handling with structured error reporting
- Basic usage patterns for the `EnhancedConfigurationManager`

**Key Features Shown**:

- Schema validation with meaningful error messages
- Deep object merging for configuration overrides
- Custom error handling with `ConfigurationError` class
- Configuration isolation between environments

**Run with**:

```bash
npx ts-node examples/enhanced-config-example.ts
```

### 2. `module-config-demo.ts`

**Purpose**: Advanced demonstration using real module schemas and configurations

**What it demonstrates**:

- Module-specific schema validation using actual schemas from `app/conf`,
  `vpc/conf`, `firewall/conf`
- Environment isolation and configuration merging in practice
- Schema path resolution and module-specific validation
- Integration with actual AWS Network Firewall module configurations
- Production-ready error handling and troubleshooting

**Key Features Shown**:

- Real-world validation using app module schema (VPC IDs, firewall policies,
  etc.)
- Environment-specific overrides (dev vs prod configurations)
- Module isolation (changes to dev don't affect prod)
- Comprehensive error reporting with field-level details
- Schema discovery and validation across multiple modules

**Run with**:

```bash
npx ts-node examples/module-config-demo.ts
```

## Example Output

### Enhanced Config Example Output

```
=== Configuration Validation Example ===
✅ Configuration is valid

=== Configuration Merging Example ===
Base config instance types: [ 't3.micro' ]
Merged config instance types: [ 't3.small' ]
Base config max capacity: 3
Merged config max capacity: 5
Base config advanced logging: false
Merged config advanced logging: true

=== Error Handling Example ===
❌ Configuration Error:
Configuration validation failed for module app in stage dev
Validation errors:
  - module.version: Version is required
  - environments.dev.account: Account ID must be 12 digits
```

### Module Config Demo Output

```
=== Enhanced Configuration Management with Module Schemas ===

1. App Module Configuration Validation:
✅ Valid app config: PASSED
❌ Invalid app config: CORRECTLY FAILED
   Validation errors:
   - /us-east-1: Missing required property: firewall_policy_arns
   - /us-east-1/vpc_id: Value 'invalid-vpc-id' does not match required pattern: ^vpc-[a-zA-Z0-9]+$
   - /us-east-1/rule_order: must be equal to one of the allowed values

2. Configuration Merging with Environment Isolation:
Original dev instance types: [ 't3.micro' ]
Merged dev instance types:   [ 't3.small' ]
Original prod instance types: [ 't3.large' ]
Merged prod instance types:   [ 't3.large' ]

4. Module-Specific Schema Path Resolution:
app schema: ✅ Found at /path/to/app/conf/schema.json
vpc schema: ✅ Found at /path/to/vpc/conf/schema.json
firewall schema: ✅ Found at /path/to/firewall/conf/schema.json
```

## Using These Examples

### For Learning

1. Start with `enhanced-config-example.ts` to understand basic concepts
2. Move to `module-config-demo.ts` to see real-world integration
3. Examine the source code to understand implementation patterns

### For Development

1. Copy patterns from these examples into your own code
2. Use the validation examples as templates for your own schemas
3. Adapt the error handling patterns for your specific use cases

### For Testing

1. Use these examples to verify your configuration setup
2. Test schema changes by running the validation examples
3. Verify environment-specific overrides work as expected

## Configuration Files Used

The examples work with the actual configuration structure:

```
├── conf/                    # Global configuration
│   ├── schema.json         # Global schema
│   ├── dev.json           # Dev environment config
│   └── sample.json        # Sample configuration
├── app/conf/              # App module configuration
│   ├── schema.json        # App-specific schema
│   └── dev.json          # App dev config
├── vpc/conf/              # VPC module configuration
│   ├── schema.json        # VPC-specific schema
│   └── dev.json          # VPC dev config
└── firewall/conf/         # Firewall module configuration
    ├── schema.json        # Firewall-specific schema
    └── dev.json          # Firewall dev config
```

## Next Steps

After running these examples:

1. **Integrate into your modules**: Use the `createConfigurationManager()`
   function in your CDK stacks
2. **Create environment overrides**: Add `{stage}-overrides.json` files for
   environment-specific settings
3. **Set up SSM parameters**: Migrate from file-based to SSM Parameter Store
   configuration
4. **Enhance error handling**: Use `ConfigurationError` for structured error
   reporting in your applications

## Troubleshooting

If examples fail to run:

1. **Missing schemas**: Some examples require module schemas to exist. Check
   that `app/conf/schema.json`, `vpc/conf/schema.json`, and
   `firewall/conf/schema.json` exist.

2. **TypeScript errors**: Ensure you're running from the `shared/` directory and
   that dependencies are installed:

   ```bash
   cd shared
   npm install
   npm run build
   ```

3. **Path issues**: Examples use relative paths. Run them from the `shared/`
   directory:
   ```bash
   cd shared
   npx ts-node examples/enhanced-config-example.ts
   ```
