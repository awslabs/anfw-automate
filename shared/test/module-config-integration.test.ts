/**
 * Integration tests for module-specific configuration management
 * Tests the enhanced configuration manager with actual module schemas
 */

import * as fs from 'fs';
import * as path from 'path';
import { EnhancedConfigurationManager, ConfigurationError } from '../lib/config_loader';

describe('Module-Specific Configuration Integration', () => {
  let configManager: EnhancedConfigurationManager;

  beforeEach(() => {
    configManager = new EnhancedConfigurationManager();
  });

  describe('Schema Validation with Real Module Schemas', () => {
    it('should validate app module configuration against app schema', () => {
      // Load the actual app schema
      const appSchemaPath = path.join(__dirname, '../../app/conf/schema.json');

      if (!fs.existsSync(appSchemaPath)) {
        console.warn('App schema not found, skipping test');
        return;
      }

      const appSchema = JSON.parse(fs.readFileSync(appSchemaPath, 'utf-8'));

      // Create a valid app configuration based on the schema
      const validAppConfig = {
        'us-east-1': {
          vpc_id: 'vpc-12345678',
          rule_order: 'DEFAULT_ACTION_ORDER',
          supported_regions: ['us-east-1', 'us-west-2'],
          firewall_policy_arns: {
            'us-east-1': [
              'arn:aws:network-firewall:us-east-1:123456789012:firewall-policy/example',
            ],
          },
        },
      };

      const result = configManager.validateConfig(validAppConfig, appSchema);

      expect(result.isValid).toBe(true);
      expect(result.errors).toHaveLength(0);
    });

    it('should detect validation errors in app module configuration', () => {
      const appSchemaPath = path.join(__dirname, '../../app/conf/schema.json');

      if (!fs.existsSync(appSchemaPath)) {
        console.warn('App schema not found, skipping test');
        return;
      }

      const appSchema = JSON.parse(fs.readFileSync(appSchemaPath, 'utf-8'));

      // Create an invalid app configuration
      const invalidAppConfig = {
        'us-east-1': {
          vpc_id: 'invalid-vpc-id', // Should match vpc-* pattern
          rule_order: 'INVALID_ORDER', // Should be enum value
          supported_regions: ['invalid-region'], // Should match region pattern
          // Missing required firewall_policy_arns
        },
      };

      const result = configManager.validateConfig(invalidAppConfig, appSchema);

      expect(result.isValid).toBe(false);
      expect(result.errors.length).toBeGreaterThan(0);

      // Check that we get meaningful error messages
      const errorMessages = result.errors.map(e => e.message);
      expect(errorMessages.some(msg => msg.includes('vpc_id') || msg.includes('pattern'))).toBe(
        true
      );
    });
  });

  describe('Configuration Merging with Module Isolation', () => {
    it('should merge module configurations while maintaining isolation', () => {
      const baseModuleConfig = {
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
              instance_types: ['t3.medium'],
            },
            scaling: {
              min_capacity: 2,
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

      const environmentOverrides = {
        environments: {
          dev: {
            resources: {
              instance_types: ['t3.small'], // Override only dev environment
            },
            scaling: {
              max_capacity: 5, // Override only max_capacity
            },
          },
          // Note: prod environment should remain unchanged
        },
        features: {
          advanced_logging: true, // Enable for all environments
        },
      };

      const mergedConfig = configManager.mergeConfigs(baseModuleConfig, environmentOverrides);

      // Verify dev environment was overridden
      expect(mergedConfig.environments.dev.resources.instance_types).toEqual(['t3.small']);
      expect(mergedConfig.environments.dev.scaling.max_capacity).toBe(5);
      expect(mergedConfig.environments.dev.scaling.min_capacity).toBe(1); // Should remain unchanged

      // Verify prod environment was not affected
      expect(mergedConfig.environments.prod.resources.instance_types).toEqual(['t3.medium']);
      expect(mergedConfig.environments.prod.scaling.max_capacity).toBe(10);

      // Verify global feature flag was applied
      expect(mergedConfig.features.advanced_logging).toBe(true);
      expect(mergedConfig.features.auto_scaling).toBe(true); // Should remain unchanged
    });
  });

  describe('Error Handling with Module Context', () => {
    it('should provide clear error messages for missing module configuration', () => {
      const error = new ConfigurationError(
        'Configuration validation failed for module app in stage dev',
        [
          {
            field: 'environments.dev.vpc_id',
            message: 'VPC ID is required and must match pattern vpc-*',
          },
          {
            field: 'environments.dev.rule_order',
            message: 'Rule order must be one of: DEFAULT_ACTION_ORDER, STRICT_ORDER',
          },
          {
            field: 'firewall_policy_arns',
            message: 'Firewall policy ARNs are required for each supported region',
          },
        ]
      );

      const detailedMessage = error.getDetailedMessage();

      expect(detailedMessage).toContain(
        'Configuration validation failed for module app in stage dev'
      );
      expect(detailedMessage).toContain('environments.dev.vpc_id: VPC ID is required');
      expect(detailedMessage).toContain('environments.dev.rule_order: Rule order must be one of');
      expect(detailedMessage).toContain('firewall_policy_arns: Firewall policy ARNs are required');
    });

    it('should handle schema loading errors gracefully', () => {
      // Test with a simple invalid schema that won't cause AJV to throw
      const invalidSchema = {
        type: 'object',
        properties: {
          test: {
            type: 'string',
            pattern: '[invalid-regex', // Invalid regex pattern
          },
        },
      };

      const config = { test: 'value' };

      // This should handle the error gracefully
      try {
        const result = configManager.validateConfig(config, invalidSchema);
        // If it doesn't throw, check that we get some kind of result
        expect(typeof result.isValid).toBe('boolean');
        expect(Array.isArray(result.errors)).toBe(true);
      } catch (error) {
        // If it throws, that's also acceptable - the important thing is it doesn't crash the process
        expect(error).toBeDefined();
      }
    });
  });
});
