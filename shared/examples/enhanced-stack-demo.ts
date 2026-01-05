/**
 * Demonstration of Enhanced Configuration Management in Stack Entry Points
 *
 * This example shows how the enhanced configuration management improves
 * error handling and validation in the actual CDK stack entry points.
 */

import * as path from 'path';
import { loadDeploymentConfig, ConfigurationError } from '../lib/config_loader';

async function demonstrateEnhancedStackConfiguration() {
  console.log('=== Enhanced Stack Configuration Management Demo ===\n');

  const STAGE = 'dev';
  const modules = ['app', 'vpc', 'firewall'];

  for (const module of modules) {
    console.log(`🔧 Testing ${module.toUpperCase()} Module Configuration:`);

    try {
      // Simulate loading configuration like the actual stack entry points do
      const configBasePath = path.join(__dirname, `../../${module}/bin`);
      const loadedConfig = await loadDeploymentConfig(configBasePath, STAGE, module);

      if (!loadedConfig) {
        throw new ConfigurationError(
          `Failed to load configuration for ${module} module in stage '${STAGE}'`,
          [{ field: 'configuration', message: 'Configuration loading returned null' }]
        );
      }

      // Validate required configuration fields (like the updated stack entry points do)
      if (!loadedConfig.globalConfig?.project) {
        throw new ConfigurationError('Missing required project configuration', [
          { field: 'globalConfig.project', message: 'Project configuration is required' },
        ]);
      }

      if (!loadedConfig.globalConfig?.base) {
        throw new ConfigurationError('Missing required base configuration', [
          { field: 'globalConfig.base', message: 'Base configuration is required' },
        ]);
      }

      const namePrefix = `${loadedConfig.globalConfig.project.aws_organziation_scope}-${loadedConfig.globalConfig.project.project_name}-${loadedConfig.globalConfig.project.module_name}`;

      console.log(`   ✅ Configuration loaded successfully`);
      console.log(`   📋 Name prefix: ${namePrefix}`);
      console.log(`   🌍 Region: ${loadedConfig.globalConfig.base.primary_region}`);
      console.log(`   🏢 Account: ${loadedConfig.globalConfig.base.resource_account_id}`);

      // Show module-specific config
      const moduleConfigKey = module === 'firewall' ? 'fwConfig' : `${module}Config`;
      const moduleConfig = (loadedConfig as any)[moduleConfigKey];
      if (moduleConfig) {
        const configKeys = Object.keys(moduleConfig);
        console.log(`   🔧 Module config regions: ${configKeys.join(', ')}`);
      }
    } catch (error) {
      if (error instanceof ConfigurationError) {
        console.log(`   ❌ Configuration Error for ${module}:`);
        console.log(`   ${error.getDetailedMessage().replace(/\n/g, '\n   ')}`);
        console.log(`   💡 Troubleshooting:`);
        console.log(`      - Check that configuration exists for stage '${STAGE}'`);
        console.log(`      - Verify SSM parameter: /anfw-automate/${STAGE}/global/config`);
        console.log(`      - Verify SSM parameter: /anfw-automate/${STAGE}/${module}/config`);
        console.log(`      - Or check files: conf/${STAGE}.json and ${module}/conf/${STAGE}.json`);
      } else {
        console.log(
          `   ❌ Unexpected error for ${module}:`,
          error instanceof Error ? error.message : String(error)
        );
      }
    }

    console.log(''); // Empty line for readability
  }

  console.log('=== Key Improvements in Stack Entry Points ===');
  console.log('✅ Enhanced error handling with ConfigurationError class');
  console.log('✅ Detailed validation of required configuration fields');
  console.log('✅ Clear troubleshooting guidance when configuration fails');
  console.log('✅ Structured error messages with field-level details');
  console.log('✅ Improved logging with emojis and clear status messages');
  console.log('✅ Backward compatibility with existing loadDeploymentConfig');
  console.log('✅ Type safety improvements (removed "as any" casts where possible)');

  console.log('\n=== Migration Benefits ===');
  console.log('🔧 Better developer experience with clear error messages');
  console.log('🔧 Easier troubleshooting in CI/CD pipelines');
  console.log('🔧 Consistent error handling across all modules');
  console.log('🔧 Preparation for future migration to full enhanced config manager');

  console.log('\n=== Enhanced Stack Configuration Demo Complete ===');
}

// Run the demonstration if this file is executed directly
if (require.main === module) {
  demonstrateEnhancedStackConfiguration().catch(console.error);
}

export { demonstrateEnhancedStackConfiguration };
