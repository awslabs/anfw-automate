/**
 * Demonstration of Enhanced Configuration Management with Module-Specific Schemas
 *
 * This example shows how the enhanced configuration manager works with
 * actual module schemas from app/conf, vpc/conf, and firewall/conf directories.
 */

import * as fs from 'fs';
import * as path from 'path';
import { createConfigurationManager, ConfigurationError } from '../lib/config_loader';

async function demonstrateModuleSpecificConfiguration() {
  const configManager = createConfigurationManager();

  console.log('=== Enhanced Configuration Management with Module Schemas ===\n');

  // Example 1: Validate App Module Configuration
  console.log('1. App Module Configuration Validation:');

  const appSchemaPath = path.join(__dirname, '../../app/conf/schema.json');

  if (fs.existsSync(appSchemaPath)) {
    const appSchema = JSON.parse(fs.readFileSync(appSchemaPath, 'utf-8'));

    // Valid app configuration
    const validAppConfig = {
      'us-east-1': {
        vpc_id: 'vpc-12345678',
        rule_order: 'DEFAULT_ACTION_ORDER',
        supported_regions: ['us-east-1', 'us-west-2'],
        firewall_policy_arns: {
          'us-east-1': ['arn:aws:network-firewall:us-east-1:123456789012:firewall-policy/example'],
        },
      },
    };

    const validResult = configManager.validateConfig(validAppConfig, appSchema);
    console.log(`✅ Valid app config: ${validResult.isValid ? 'PASSED' : 'FAILED'}`);

    // Invalid app configuration
    const invalidAppConfig = {
      'us-east-1': {
        vpc_id: 'invalid-vpc-id', // Should match vpc-* pattern
        rule_order: 'INVALID_ORDER', // Should be enum value
        supported_regions: ['invalid-region'], // Should match region pattern
        // Missing required firewall_policy_arns
      },
    };

    const invalidResult = configManager.validateConfig(invalidAppConfig, appSchema);
    console.log(
      `❌ Invalid app config: ${invalidResult.isValid ? 'UNEXPECTEDLY PASSED' : 'CORRECTLY FAILED'}`
    );

    if (!invalidResult.isValid) {
      console.log('   Validation errors:');
      invalidResult.errors.slice(0, 3).forEach(error => {
        console.log(`   - ${error.field}: ${error.message}`);
      });
      if (invalidResult.errors.length > 3) {
        console.log(`   ... and ${invalidResult.errors.length - 3} more errors`);
      }
    }
  } else {
    console.log('⚠️  App schema not found, skipping app validation demo');
  }

  // Example 2: Configuration Merging with Environment Isolation
  console.log('\n2. Configuration Merging with Environment Isolation:');

  const baseConfig = {
    module: {
      name: 'app',
      version: '1.0.0',
      type: 'app' as const,
    },
    environments: {
      dev: {
        region: 'us-east-1',
        account: '123456789012',
        resources: {
          instance_types: ['t3.micro'],
        },
        scaling: {
          min_capacity: 1,
          max_capacity: 3,
          target_utilization: 70,
        },
        monitoring: {},
      },
      prod: {
        region: 'us-east-1',
        account: '987654321098',
        resources: {
          instance_types: ['t3.large'],
        },
        scaling: {
          min_capacity: 3,
          max_capacity: 10,
          target_utilization: 80,
        },
        monitoring: {},
      },
    },
    features: {
      advanced_logging: false,
      auto_scaling: true,
    },
    dependencies: {
      shared_library_version: '2.1.0',
      external_dependencies: {},
    },
  };

  const devOverrides = {
    environments: {
      dev: {
        resources: {
          instance_types: ['t3.small'], // Upgrade dev instances
        },
        scaling: {
          max_capacity: 5, // Allow more scaling in dev
        },
      },
      // Note: prod environment remains unchanged
    },
    features: {
      advanced_logging: true, // Enable advanced logging
    },
  };

  const mergedConfig = configManager.mergeConfigs(baseConfig, devOverrides);

  console.log('Original dev instance types:', baseConfig.environments.dev.resources.instance_types);
  console.log(
    'Merged dev instance types:  ',
    mergedConfig.environments.dev.resources.instance_types
  );
  console.log(
    'Original prod instance types:',
    baseConfig.environments.prod.resources.instance_types
  );
  console.log(
    'Merged prod instance types:  ',
    mergedConfig.environments.prod.resources.instance_types
  );
  console.log('Original advanced logging:', baseConfig.features.advanced_logging);
  console.log('Merged advanced logging:  ', mergedConfig.features.advanced_logging);

  // Example 3: Error Handling with Detailed Messages
  console.log('\n3. Enhanced Error Handling:');

  try {
    throw new ConfigurationError('Module configuration validation failed', [
      {
        field: 'environments.dev.vpc_id',
        message: 'VPC ID must match pattern vpc-* but got "invalid-vpc-id"',
      },
      {
        field: 'environments.dev.rule_order',
        message: 'Rule order must be one of: DEFAULT_ACTION_ORDER, STRICT_ORDER',
      },
      {
        field: 'firewall_policy_arns',
        message: 'Missing required property: firewall_policy_arns',
      },
    ]);
  } catch (error) {
    if (error instanceof ConfigurationError) {
      console.log('Configuration Error Details:');
      console.log(error.getDetailedMessage());
    }
  }

  // Example 4: Schema Path Resolution
  console.log('\n4. Module-Specific Schema Path Resolution:');

  const modules = ['app', 'vpc', 'firewall'];
  modules.forEach(module => {
    const schemaPath = path.join(__dirname, `../../${module}/conf/schema.json`);
    const exists = fs.existsSync(schemaPath);
    console.log(`${module} schema: ${exists ? '✅ Found' : '❌ Not found'} at ${schemaPath}`);
  });

  console.log('\n=== Enhanced Configuration Management Demo Complete ===');
}

// Run the demonstration if this file is executed directly
if (require.main === module) {
  demonstrateModuleSpecificConfiguration().catch(console.error);
}

export { demonstrateModuleSpecificConfiguration };
