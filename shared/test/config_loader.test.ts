import {
  EnhancedConfigurationManager,
  createConfigurationManager,
  ConfigurationError,
  ValidationResult,
} from '../lib/config_loader';

describe('EnhancedConfigurationManager', () => {
  let configManager: EnhancedConfigurationManager;

  beforeEach(() => {
    configManager = new EnhancedConfigurationManager();
  });

  describe('validateConfig', () => {
    it('should validate a simple valid configuration', () => {
      const config = {
        name: 'test',
        version: '1.0.0',
      };

      const schema = {
        type: 'object',
        properties: {
          name: { type: 'string' },
          version: { type: 'string' },
        },
        required: ['name', 'version'],
      };

      const result: ValidationResult = configManager.validateConfig(config, schema);

      expect(result.isValid).toBe(true);
      expect(result.errors).toHaveLength(0);
    });

    it('should detect missing required properties', () => {
      const config = {
        name: 'test',
        // missing version
      };

      const schema = {
        type: 'object',
        properties: {
          name: { type: 'string' },
          version: { type: 'string' },
        },
        required: ['name', 'version'],
      };

      const result: ValidationResult = configManager.validateConfig(config, schema);

      expect(result.isValid).toBe(false);
      expect(result.errors).toHaveLength(1);
      expect(result.errors[0].message).toContain('version');
    });

    it('should detect type mismatches', () => {
      const config = {
        name: 'test',
        version: 123, // should be string
      };

      const schema = {
        type: 'object',
        properties: {
          name: { type: 'string' },
          version: { type: 'string' },
        },
        required: ['name', 'version'],
      };

      const result: ValidationResult = configManager.validateConfig(config, schema);

      expect(result.isValid).toBe(false);
      expect(result.errors).toHaveLength(1);
      expect(result.errors[0].message).toContain('string');
    });
  });

  describe('mergeConfigs', () => {
    it('should merge simple objects', () => {
      const base = {
        name: 'test',
        version: '1.0.0',
        settings: {
          debug: false,
          timeout: 30,
        },
      };

      const override = {
        version: '2.0.0',
        settings: {
          debug: true,
        },
      };

      const result = configManager.mergeConfigs(base, override);

      expect(result).toEqual({
        name: 'test',
        version: '2.0.0',
        settings: {
          debug: true,
          timeout: 30,
        },
      });
    });

    it('should handle null and undefined values', () => {
      const base = {
        name: 'test',
        version: '1.0.0',
      };

      const override = {
        version: null,
        description: 'new description',
      };

      const result = configManager.mergeConfigs(base, override);

      expect(result).toEqual({
        name: 'test',
        version: '1.0.0', // null values don't override
        description: 'new description',
      });
    });

    it('should handle array overrides', () => {
      const base = {
        tags: ['tag1', 'tag2'],
        settings: {
          features: ['feature1'],
        },
      };

      const override = {
        tags: ['tag3', 'tag4'],
        settings: {
          features: ['feature2', 'feature3'],
        },
      };

      const result = configManager.mergeConfigs(base, override);

      expect(result).toEqual({
        tags: ['tag3', 'tag4'], // arrays are replaced, not merged
        settings: {
          features: ['feature2', 'feature3'],
        },
      });
    });
  });

  describe('ConfigurationError', () => {
    it('should create error with validation details', () => {
      const validationErrors = [
        { field: 'name', message: 'Name is required' },
        { field: 'version', message: 'Version must be a string' },
      ];

      const error = new ConfigurationError('Configuration invalid', validationErrors);

      expect(error.message).toBe('Configuration invalid');
      expect(error.validationErrors).toEqual(validationErrors);
      expect(error.name).toBe('ConfigurationError');
    });

    it('should format detailed error message', () => {
      const validationErrors = [
        { field: 'name', message: 'Name is required' },
        { field: 'version', message: 'Version must be a string' },
      ];

      const error = new ConfigurationError('Configuration invalid', validationErrors);
      const detailedMessage = error.getDetailedMessage();

      expect(detailedMessage).toContain('Configuration invalid');
      expect(detailedMessage).toContain('name: Name is required');
      expect(detailedMessage).toContain('version: Version must be a string');
    });
  });

  describe('createConfigurationManager', () => {
    it('should create an instance of EnhancedConfigurationManager', () => {
      const manager = createConfigurationManager();
      expect(manager).toBeInstanceOf(EnhancedConfigurationManager);
    });
  });
});
