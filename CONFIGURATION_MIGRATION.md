# Enhanced Configuration Migration Guide

This document outlines the enhanced configuration management system that has
been implemented across all modules (app, firewall, vpc) in the AWS Network
Firewall automation project.

## What Changed

### ✅ Migration Complete

All module entry points have been successfully migrated to use enhanced
configuration management:

- **App Module**: `app/bin/app.ts` ✅
- **Firewall Module**: `firewall/bin/firewall.ts` ✅
- **VPC Module**: `vpc/bin/vpc.ts` ✅

### Key Improvements

1. **Enhanced Error Handling**
   - Detailed field-level validation errors
   - Clear troubleshooting guidance
   - Structured error messages with specific paths

2. **Multiple Configuration Sources**
   - SSM Parameter Store (primary for AWS environments)
   - JSON files (fallback for local development)
   - Automatic fallback when AWS credentials are unavailable

3. **Schema Validation**
   - Comprehensive validation against JSON schemas
   - Detailed error messages for validation failures
   - Support for environment-specific overrides

4. **Improved Developer Experience**
   - Better error messages with actionable guidance
   - Seamless local development without AWS credentials
   - Consistent configuration handling across all modules

## Configuration Sources

### SSM Parameter Store (Primary)

When AWS credentials are available, the system uses SSM Parameter Store:

```
Global Configuration:
/anfw-automate/{stage}/global/config

Module Configuration:
/anfw-automate/{stage}/app/config
/anfw-automate/{stage}/firewall/config
/anfw-automate/{stage}/vpc/config

Environment Overrides:
/anfw-automate/{stage}/app/overrides
/anfw-automate/{stage}/firewall/overrides
/anfw-automate/{stage}/vpc/overrides
```

### JSON Files (Fallback)

For local development or when AWS credentials are not available:

```
Global Configuration:
conf/{stage}.json

Module Configuration:
app/conf/{stage}.json
firewall/conf/{stage}.json
vpc/conf/{stage}.json

Environment Overrides:
app/conf/{stage}-overrides.json
firewall/conf/{stage}-overrides.json
vpc/conf/{stage}-overrides.json
```

## Error Handling Examples

### Before (Legacy)

```
Error: Configuration file not found
```

### After (Enhanced)

```
❌ Configuration Error: Global configuration not found for stage 'dev'

Troubleshooting steps:
1. Check if file exists: conf/dev.json
2. Verify SSM parameter: /anfw-automate/dev/global/config
3. Ensure AWS credentials are configured for SSM access
4. Validate JSON syntax in configuration file

For local development, create conf/dev.json with required configuration.
```

### Schema Validation Example

```
❌ Configuration validation failed for module 'app' in stage 'dev'

Validation errors:
  - environments.dev.vpc_id: VPC ID must match pattern vpc-* but got "invalid-vpc-id"
  - environments.dev.rule_order: Rule order must be one of: DEFAULT_ACTION_ORDER, STRICT_ORDER
  - firewall_policy_arns: Missing required property: firewall_policy_arns

Please fix these issues in your configuration file and try again.
```

## Backward Compatibility

### ✅ Fully Backward Compatible

- Existing configuration files continue to work without changes
- Same configuration structure and format
- No breaking changes to existing deployments
- Legacy functions still available (but deprecated)

### Migration Path

**No action required** - the migration is complete and transparent to users.
However, for new development:

```typescript
// Legacy approach (still works, but deprecated)
import { loadDeploymentConfig } from './lib/config_loader';
const config = await loadDeploymentConfig(configBasePath, stage, stackType);

// Enhanced approach (recommended for new code)
import { createConfigurationManager } from './lib/config_loader';
const configManager = createConfigurationManager();
const moduleConfig = await configManager.loadConfig(module, stage);
```

## Local Development

### Seamless Local Development

The enhanced system works seamlessly in local development environments:

1. **No AWS Credentials Required**: Automatically falls back to file-based
   configuration
2. **Clear Messages**: Informative messages about fallback behavior
3. **Same Configuration**: Uses the same configuration files as before

### Expected Messages

When developing locally without AWS credentials, you'll see:

```
SSM parameter '/anfw-automate/dev/global/config' not accessible (no AWS credentials), falling back to file-based config.
✅ Global configuration loaded successfully from file: /path/to/conf/dev.json
```

This is normal and expected behavior for local development.

## Testing

### Comprehensive Test Coverage

The enhanced configuration system includes:

- **Unit Tests**: Testing individual configuration functions
- **Integration Tests**: Testing end-to-end configuration loading
- **Property-Based Tests**: Testing configuration compatibility across all
  inputs
- **Schema Validation Tests**: Testing validation with various invalid
  configurations

### Running Tests

```bash
# Run all tests
npm test

# Run specific module tests
cd shared && npm test
```

## Support

### Getting Help

1. **Configuration Issues**: Check the detailed error messages for specific
   guidance
2. **Schema Validation**: Review the schema files in `conf/schema.json` and
   `{module}/conf/schema.json`
3. **Local Development**: Ensure configuration files exist in the expected
   locations
4. **AWS Deployment**: Verify AWS credentials and SSM parameter access

### Common Issues

1. **Configuration Not Found**: Check file paths and SSM parameter names
2. **Schema Validation Errors**: Review the detailed error messages for specific
   field issues
3. **AWS Credential Issues**: Use file-based configuration for local development
4. **Permission Issues**: Ensure proper IAM permissions for SSM parameter access

## Summary

The enhanced configuration migration provides:

- ✅ **Better Error Handling**: Clear, actionable error messages
- ✅ **Multiple Sources**: SSM Parameter Store + JSON file fallback
- ✅ **Schema Validation**: Comprehensive validation with detailed feedback
- ✅ **Local Development**: Seamless experience without AWS credentials
- ✅ **Backward Compatibility**: No breaking changes to existing configurations
- ✅ **Production Ready**: Enhanced reliability and troubleshooting capabilities

The migration is complete and all modules are now using the enhanced
configuration system while maintaining full backward compatibility.
