/**
 * Example usage of the Enhanced Configuration Manager
 *
 * This example demonstrates the key features:
 * - Configuration validation with detailed error messages
 * - Configuration merging with environment-specific overrides
 * - Module-specific configuration isolation
 * - SSM Parameter Store integration
 */

import { createConfigurationManager } from '../lib/config_loader';

async function demonstrateEnhancedConfigurationManager() {
  const configManager = createConfigurationManager();

  // Example 1: Configuration Validation
  console.log('=== Configuration Validation Example ===');

  const sampleConfig = {
    project: {
      project_name: 'anfw',
      module_name: 'app',
      aws_organziation_scope: 'org',
    },
  };

  const schema = {
    type: 'object',
    properties: {
      project: {
        type: 'object',
        properties: {
          project_name: { type: 'string', minLength: 2 },
          module_name: { type: 'string', minLength: 2 },
          aws_organziation_scope: { type: 'string', minLength: 2 },
        },
        required: ['project_name', 'module_name', 'aws_organziation_scope'],
      },
    },
    required: ['project'],
  };

  const validationResult = configManager.validateConfig(sampleConfig, schema);

  if (validationResult.isValid) {
    console.log('✅ Configuration is valid');
  } else {
    console.log('❌ Configuration validation failed:');
    validationResult.errors.forEach(error => {
      console.log(`  - ${error.field}: ${error.message}`);
    });
  }

  // Example 2: Configuration Merging
  console.log('\n=== Configuration Merging Example ===');

  const baseConfig = {
    module: {
      name: 'app',
      version: '1.0.0',
    },
    features: {
      advanced_logging: false,
      auto_scaling: true,
    },
  };

  const environmentOverrides = {
    features: {
      advanced_logging: true, // Enable advanced logging for this environment
    },
  };

  const mergedConfig = configManager.mergeConfigs(baseConfig, environmentOverrides);

  console.log('Base config advanced logging:', baseConfig.features.advanced_logging);
  console.log('Merged config advanced logging:', mergedConfig.features.advanced_logging);

  console.log('\n=== Enhanced Configuration Manager Demo Complete ===');
}

// Run the demonstration
demonstrateEnhancedConfigurationManager().catch(console.error);
