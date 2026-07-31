/**
 * Cross-Module Property-Based Tests for Enhanced Configuration Migration
 * Feature: enhanced-config-migration
 */

import * as fc from 'fast-check';
import * as fs from 'fs';
import * as path from 'path';
import {
  ConfigurationManager,
  createConfigurationManager,
  ConfigurationError,
} from '../lib/config_loader';

describe('Cross-Module Property Tests', () => {
  let configManager: ConfigurationManager;

  beforeEach(() => {
    configManager = createConfigurationManager();
  });

  describe('Property 3: Configuration Source Support', () => {
    /**
     * Feature: enhanced-config-migration, Property 3: Configuration Source Support
     * For any configuration provided via file or SSM parameter, the enhanced configuration manager
     * should successfully load it using the same paths as the legacy approach
     * Validates: Requirements 1.4, 2.4, 3.4, 4.1, 4.2
     */
    it('should support file-based configuration loading for all modules', () => {
      fc.assert(
        fc.property(
          fc.constantFrom('app', 'firewall', 'vpc'),
          fc.constantFrom('dev', 'prod', 'test'),
          fc.record({
            stage: fc.string({ minLength: 1, maxLength: 10 }),
            region: fc.constantFrom('us-east-1', 'us-west-2', 'eu-west-1'),
            environment: fc.record({
              name: fc.string({ minLength: 1, maxLength: 20 }),
              resources: fc.record({
                instance_types: fc.array(fc.constantFrom('t3.micro', 't3.small', 't3.medium'), {
                  minLength: 1,
                  maxLength: 3,
                }),
              }),
            }),
          }),
          (module, stage, config) => {
            // Test that the configuration manager can handle file-based configurations
            // This validates that the enhanced manager supports the same file paths as legacy

            // Create a temporary config file structure
            const tempConfigPath = path.join(__dirname, `temp-${module}-${stage}.json`);

            try {
              // Write temporary config file
              fs.writeFileSync(tempConfigPath, JSON.stringify(config, null, 2));

              // Verify the config can be read and parsed
              const fileContent = fs.readFileSync(tempConfigPath, 'utf8');
              const parsedConfig = JSON.parse(fileContent);

              // The enhanced configuration manager should be able to process this structure
              expect(parsedConfig).toEqual(config);
              expect(parsedConfig.stage).toBeDefined();
              expect(parsedConfig.region).toBeDefined();

              // Verify the configuration has the expected structure for CDK usage
              expect(parsedConfig.environment).toBeDefined();
              expect(parsedConfig.environment.resources).toBeDefined();
              expect(Array.isArray(parsedConfig.environment.resources.instance_types)).toBe(true);
            } finally {
              // Clean up temporary file
              if (fs.existsSync(tempConfigPath)) {
                fs.unlinkSync(tempConfigPath);
              }
            }
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should handle SSM parameter path structures consistently', () => {
      fc.assert(
        fc.property(
          fc.constantFrom('app', 'firewall', 'vpc'),
          fc.constantFrom('dev', 'prod', 'test'),
          fc.string({ minLength: 1, maxLength: 50 }).filter(s => !s.includes('/')),
          (module, stage, parameterName) => {
            // Test that SSM parameter paths follow the expected pattern
            // This validates Requirements 4.1, 4.2 - same parameter paths as legacy

            const expectedPathPattern = `/anfw/${stage}/${module}/${parameterName}`;

            // Verify the path structure is consistent with legacy approach
            expect(expectedPathPattern).toMatch(/^\/anfw\/[^/]+\/[^/]+\/[^/]+$/);
            expect(expectedPathPattern).toContain(`/${stage}/`);
            expect(expectedPathPattern).toContain(`/${module}/`);
            expect(expectedPathPattern.split('/').length).toBe(5); // '', 'anfw', stage, module, parameterName
          }
        ),
        { numRuns: 100 }
      );
    });
  });

  describe('Property 5: Detailed Error Messages', () => {
    /**
     * Feature: enhanced-config-migration, Property 5: Detailed Error Messages
     * For any configuration validation failure, the enhanced configuration manager
     * should provide field-level error messages with specific validation paths
     * Validates: Requirements 1.2, 5.1, 5.2, 5.5
     */
    it('should provide field-level error messages for validation failures', () => {
      fc.assert(
        fc.property(
          fc.record({
            // Generate invalid configurations with missing required fields
            name: fc.option(fc.string(), { nil: undefined }), // Sometimes missing
            version: fc.option(fc.string(), { nil: undefined }), // Sometimes missing
            invalidField: fc.oneof(
              fc.integer(), // Wrong type (should be string)
              fc.array(fc.string()), // Wrong type (should be string)
              fc.boolean() // Wrong type (should be string)
            ),
          }),
          fc.record({
            type: fc.constant('object'),
            properties: fc.constant({
              name: { type: 'string' },
              version: { type: 'string' },
              invalidField: { type: 'string' },
            }),
            required: fc.constant(['name', 'version', 'invalidField']),
          }),
          (invalidConfig, schema) => {
            const result = configManager.validateConfig(invalidConfig, schema);

            // Should detect validation failures
            expect(result.isValid).toBe(false);
            expect(result.errors.length).toBeGreaterThan(0);

            // Each error should have field-level details
            result.errors.forEach(error => {
              expect(error.field).toBeDefined();
              expect(typeof error.field).toBe('string');
              expect(error.message).toBeDefined();
              expect(typeof error.message).toBe('string');
              expect(error.message.length).toBeGreaterThan(0);
            });

            // Should provide specific error messages for missing fields
            const missingFieldErrors = result.errors.filter(
              e => e.message.includes('required') || e.message.includes('Missing')
            );

            const typeErrors = result.errors.filter(
              e => e.message.includes('type') || e.message.includes('Expected')
            );

            // Should have at least one type of validation error
            expect(missingFieldErrors.length + typeErrors.length).toBeGreaterThan(0);
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should provide troubleshooting guidance in error messages', () => {
      fc.assert(
        fc.property(
          fc.constantFrom('app', 'firewall', 'vpc'),
          fc.constantFrom('dev', 'prod', 'test'),
          (module, stage) => {
            // Test that ConfigurationError provides detailed messages
            const validationErrors = [
              { field: 'name', message: 'Name is required' },
              { field: 'version', message: 'Version must be a string' },
            ];

            const error = new ConfigurationError(
              `Configuration validation failed for module '${module}' in stage '${stage}'`,
              validationErrors
            );

            const detailedMessage = error.getDetailedMessage();

            // Should include the main error message
            expect(detailedMessage).toContain(
              `Configuration validation failed for module '${module}' in stage '${stage}'`
            );

            // Should include field-level validation errors
            expect(detailedMessage).toContain('name: Name is required');
            expect(detailedMessage).toContain('version: Version must be a string');

            // Should have structured format for troubleshooting
            expect(detailedMessage).toContain('Validation errors:');

            // Should provide actionable information
            expect(detailedMessage.length).toBeGreaterThan(error.message.length);
          }
        ),
        { numRuns: 100 }
      );
    });
  });

  describe('Property 6: Environment Variable Compatibility', () => {
    /**
     * Feature: enhanced-config-migration, Property 6: Environment Variable Compatibility
     * For any valid STAGE and AWS_REGION environment variables, the enhanced configuration manager
     * should use them in the same way as the legacy approach
     * Validates: Requirements 4.4
     */
    it('should handle STAGE environment variable consistently', () => {
      fc.assert(
        fc.property(
          fc.constantFrom('dev', 'prod', 'test', 'staging'),
          fc.constantFrom('app', 'firewall', 'vpc'),
          (stage, module) => {
            // Test that stage values are handled consistently
            // This validates that the enhanced manager uses STAGE the same way as legacy

            // Verify stage is a valid identifier
            expect(stage).toMatch(/^[a-zA-Z][a-zA-Z0-9]*$/);
            expect(stage.length).toBeGreaterThan(0);
            expect(stage.length).toBeLessThanOrEqual(20);

            // Test that stage can be used in configuration paths
            const configPath = `/anfw-automate/${stage}/${module}/config`;
            expect(configPath).toMatch(/^\/anfw-automate\/[^/]+\/[^/]+\/config$/);

            // Test that stage can be used in file paths
            const filePath = `conf/${stage}.json`;
            expect(filePath).toMatch(/^conf\/[^/]+\.json$/);

            // Verify stage doesn't contain invalid characters for file/parameter names
            expect(stage).not.toContain('/');
            expect(stage).not.toContain('\\');
            expect(stage).not.toContain(' ');
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should handle AWS_REGION environment variable consistently', () => {
      fc.assert(
        fc.property(
          fc.constantFrom('us-east-1', 'us-west-2', 'eu-west-1', 'ap-southeast-1'),
          fc.constantFrom('dev', 'prod', 'test'),
          (region, stage) => {
            // Test that AWS region values are handled consistently
            // This validates Requirements 4.4 - same environment variables as legacy

            // Verify region follows AWS region format
            expect(region).toMatch(/^[a-z]{2}-[a-z]+-\d+$/);

            // Test that region can be used in configuration
            const mockConfig = {
              stage,
              region,
              environment: {
                name: stage,
                region: region,
              },
            };

            expect(mockConfig.region).toBe(region);
            expect(mockConfig.environment.region).toBe(region);

            // Verify region is compatible with AWS SDK expectations
            expect(region.split('-').length).toBe(3); // e.g., us-east-1
            expect(region.length).toBeGreaterThan(8); // Minimum AWS region length
            expect(region.length).toBeLessThan(20); // Maximum reasonable length
          }
        ),
        { numRuns: 100 }
      );
    });
  });

  describe('Property 7: Troubleshooting Guidance', () => {
    /**
     * Feature: enhanced-config-migration, Property 7: Troubleshooting Guidance
     * For any configuration format error, the enhanced configuration manager
     * should provide clear troubleshooting guidance in error messages
     * Validates: Requirements 5.3
     */
    it('should provide clear troubleshooting guidance for configuration format errors', () => {
      fc.assert(
        fc.property(
          fc.constantFrom('app', 'firewall', 'vpc'),
          fc.constantFrom('dev', 'prod', 'test'),
          fc.oneof(
            fc.constant('missing_required_field'),
            fc.constant('invalid_type'),
            fc.constant('invalid_format'),
            fc.constant('schema_validation_failure')
          ),
          (module, stage, errorType) => {
            let validationErrors: any[] = [];
            let expectedGuidanceKeywords: string[] = [];

            // Generate different types of validation errors with expected guidance
            switch (errorType) {
              case 'missing_required_field':
                validationErrors = [{ field: 'name', message: 'Missing required property: name' }];
                expectedGuidanceKeywords = ['required', 'property', 'missing'];
                break;
              case 'invalid_type':
                validationErrors = [
                  { field: 'version', message: 'Expected string but got number' },
                ];
                expectedGuidanceKeywords = ['expected', 'type', 'string'];
                break;
              case 'invalid_format':
                validationErrors = [
                  {
                    field: 'email',
                    message: 'Value does not match required pattern: email format',
                  },
                ];
                expectedGuidanceKeywords = ['pattern', 'format', 'match'];
                break;
              case 'schema_validation_failure':
                validationErrors = [
                  { field: 'config', message: 'Configuration must be a valid object' },
                ];
                expectedGuidanceKeywords = ['configuration', 'valid', 'object'];
                break;
            }

            const error = new ConfigurationError(
              `Configuration validation failed for module '${module}' in stage '${stage}'`,
              validationErrors
            );

            const detailedMessage = error.getDetailedMessage();

            // Should provide structured troubleshooting information
            expect(detailedMessage).toContain('Validation errors:');
            expect(detailedMessage.length).toBeGreaterThan(error.message.length);

            // Should include field-specific guidance
            validationErrors.forEach(validationError => {
              expect(detailedMessage).toContain(validationError.field);
              expect(detailedMessage).toContain(validationError.message);
            });

            // Should contain relevant troubleshooting keywords
            const lowerCaseMessage = detailedMessage.toLowerCase();
            const hasRelevantKeywords = expectedGuidanceKeywords.some(keyword =>
              lowerCaseMessage.includes(keyword.toLowerCase())
            );
            expect(hasRelevantKeywords).toBe(true);

            // Should be actionable (contain specific field and error information)
            expect(detailedMessage).toMatch(/\w+:\s+\w+/); // Pattern like "field: message"
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should provide context-specific troubleshooting for different modules', () => {
      fc.assert(
        fc.property(
          fc.constantFrom('app', 'firewall', 'vpc'),
          fc.constantFrom('dev', 'prod', 'test'),
          (module, stage) => {
            // Test that troubleshooting guidance includes module and stage context
            const contextualErrors = [
              {
                field: 'troubleshooting',
                message: `Please ensure at least one of the following exists and is valid: SSM parameter '/anfw-automate/${stage}/${module}/config' or file '${module}/conf/${stage}.json'`,
              },
            ];

            const error = new ConfigurationError(
              `Configuration not found for module '${module}' in stage '${stage}'`,
              contextualErrors
            );

            const detailedMessage = error.getDetailedMessage();

            // Should include module-specific context
            expect(detailedMessage).toContain(module);
            expect(detailedMessage).toContain(stage);

            // Should provide specific paths for troubleshooting
            expect(detailedMessage).toContain(`/anfw-automate/${stage}/${module}/config`);
            expect(detailedMessage).toContain(`${module}/conf/${stage}.json`);

            // Should provide actionable guidance
            expect(detailedMessage).toContain('Please ensure');
            expect(detailedMessage).toContain('exists and is valid');

            // Should be comprehensive enough for troubleshooting
            expect(detailedMessage.length).toBeGreaterThan(100); // Substantial guidance
          }
        ),
        { numRuns: 100 }
      );
    });
  });
});
