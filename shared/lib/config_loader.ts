/**
 * Configuration Loader with SSM Parameter Store Support
 *
 * This module provides backward-compatible configuration loading that supports both:
 * 1. JSON files committed to the repository (original behavior)
 * 2. AWS SSM Parameter Store parameters in the format:
 *    - Global config: /anfw-automate/{env}/global/config
 *    - Module config: /anfw-automate/{env}/{module}/config
 *
 * The loader tries SSM parameters first, then falls back to JSON files if parameters
 * are not found. This allows for seamless migration from file-based to SSM-based
 * configuration management.
 *
 * Usage:
 * - Use loadDeploymentConfig() for new async implementations
 * - loadDeploymentConfigSync() is deprecated but maintained for backward compatibility
 */

import * as fs from 'fs';
import * as path from 'path';
import Ajv from 'ajv';
import addFormats from 'ajv-formats';
import { SSMClient, GetParameterCommand } from '@aws-sdk/client-ssm';

export interface StackConfig {
  [key: string]: any;
}

interface ConfigSource {
  type: 'file' | 'ssm';
  path?: string;
  parameterName?: string;
}

// Initialize SSM client
const ssmClient = new SSMClient({});

async function loadConfigFromSSM(parameterName: string): Promise<StackConfig | null> {
  try {
    const command = new GetParameterCommand({
      Name: parameterName,
      WithDecryption: true,
    });

    const response = await ssmClient.send(command);

    if (!response.Parameter?.Value) {
      console.error(`SSM parameter '${parameterName}' has no value.`);
      return null;
    }

    return JSON.parse(response.Parameter.Value) as StackConfig;
  } catch (err: any) {
    if (err.name === 'ParameterNotFound') {
      console.log(`SSM parameter '${parameterName}' not found, falling back to file-based config.`);
      return null;
    }
    console.error(`Error loading SSM parameter '${parameterName}':`, err);
    return null;
  }
}

function loadConfigFromFile(configPath: string, schemaPath: string): StackConfig | null {
  if (!fs.existsSync(configPath)) {
    // eslint-disable-next-line no-console
    console.error(`JSON file does not exist at path '${configPath}'.`);
    return null;
  }

  // Read the JSON schema
  let schema;
  try {
    schema = JSON.parse(fs.readFileSync(schemaPath, 'utf-8'));
  } catch (err) {
    // eslint-disable-next-line no-console
    console.error(`Error reading/parsing JSON schema at path '${schemaPath}':`, err);
    return null;
  }

  // Read the JSON data
  let data;
  try {
    data = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
  } catch (err) {
    // eslint-disable-next-line no-console
    console.error(`Error reading/parsing JSON at path '${configPath}':`, err);
    return null;
  }

  return validateConfig(data, schema, configPath);
}

async function loadConfigFromSource(
  source: ConfigSource,
  schemaPath: string
): Promise<StackConfig | null> {
  let data: StackConfig;
  let sourceName: string;

  if (source.type === 'ssm' && source.parameterName) {
    const ssmData = await loadConfigFromSSM(source.parameterName);
    sourceName = source.parameterName;
    if (ssmData === null) {
      return null;
    }
    data = ssmData;
  } else if (source.type === 'file' && source.path) {
    if (!fs.existsSync(source.path)) {
      console.error(`JSON file does not exist at path '${source.path}'.`);
      return null;
    }
    try {
      data = JSON.parse(fs.readFileSync(source.path, 'utf-8')) as StackConfig;
      sourceName = source.path;
    } catch (err) {
      console.error(`Error reading/parsing JSON at path '${source.path}':`, err);
      return null;
    }
  } else {
    console.error('Invalid config source provided');
    return null;
  }

  // Read the JSON schema
  let schema;
  try {
    schema = JSON.parse(fs.readFileSync(schemaPath, 'utf-8'));
  } catch (err) {
    console.error(`Error reading/parsing JSON schema at path '${schemaPath}':`, err);
    return null;
  }

  return validateConfig(data, schema, sourceName);
}

function validateConfig(data: StackConfig, schema: any, sourceName: string): StackConfig | null {
  const ajv = new Ajv({ allErrors: true }); // Initialize Ajv
  addFormats(ajv); // Add format validation
  const validate = ajv.compile(schema); // Compile the schema
  const valid = validate(data); // Validate the data

  if (!valid) {
    // eslint-disable-next-line no-console
    console.error(`Validation errors in ${sourceName}:`, validate.errors);
    return null;
  } else {
    // eslint-disable-next-line no-console
    console.log(`Validation successful for ${sourceName}`);
    return data;
  }
}

export async function loadDeploymentConfig(
  configBasePath: string,
  stage: string,
  stackType: string
): Promise<StackConfig | null> {
  // Define config sources with SSM fallback
  const globalConfigSources: ConfigSource[] = [
    {
      type: 'ssm',
      parameterName: `/anfw-automate/${stage}/global/config`,
    },
    {
      type: 'file',
      path: path.join(__dirname, '../../conf', `${stage}.json`),
    },
  ];

  const moduleConfigSources: ConfigSource[] = [
    {
      type: 'ssm',
      parameterName: `/anfw-automate/${stage}/${stackType}/config`,
    },
    {
      type: 'file',
      path: path.join(configBasePath, '../conf', `${stage}.json`),
    },
  ];

  // Load global config with fallback
  let globalConfig: StackConfig | null = null;
  for (const source of globalConfigSources) {
    globalConfig = await loadConfigFromSource(
      source,
      path.join(__dirname, '../../conf', 'schema.json')
    );
    if (globalConfig !== null) {
      break;
    }
  }

  if (globalConfig === null) {
    // eslint-disable-next-line no-console
    console.error('Error loading global configuration from all sources.');
    process.exit(1);
  }

  // Declare commonConfigs with default values
  const commonConfigs: StackConfig = { stage, globalConfig };

  // Load module-specific config with fallback
  let loadedConfig: StackConfig | null = null;
  for (const source of moduleConfigSources) {
    loadedConfig = await loadConfigFromSource(
      source,
      path.join(configBasePath, '../conf', 'schema.json')
    );
    if (loadedConfig !== null) {
      break;
    }
  }

  if (loadedConfig === null) {
    // eslint-disable-next-line no-console
    console.error(`Error loading ${stackType} configuration from all sources.`);
    process.exit(1);
  }

  // Return stack-specific configurations based on stackType
  switch (stackType) {
    case 'app':
      return {
        ...commonConfigs,
        appConfig: loadedConfig,
      };

    case 'firewall':
      return {
        ...commonConfigs,
        fwConfig: loadedConfig,
      };

    case 'vpc':
      return {
        ...commonConfigs,
        vpcConfig: loadedConfig,
      };

    default:
      // eslint-disable-next-line no-console
      console.error(`Invalid stack name: '${stackType}'`);
      process.exit(1);
  }
}

// Backward compatible synchronous function that wraps the async version
export function loadDeploymentConfigSync(
  configBasePath: string,
  stage: string,
  stackType: string
): StackConfig | null {
  console.warn('loadDeploymentConfigSync is deprecated. Use loadDeploymentConfig (async) instead.');

  // For backward compatibility, try to load from files only
  const globalConfig = loadConfigFromFile(
    path.join(__dirname, '../../conf', `${stage}.json`),
    path.join(__dirname, '../../conf', 'schema.json')
  );

  if (globalConfig === null) {
    console.error('Error loading global configuration.');
    process.exit(1);
  }

  const commonConfigs: StackConfig = { stage, globalConfig };

  const loadedConfig = loadConfigFromFile(
    path.join(configBasePath, '../conf', `${stage}.json`),
    path.join(configBasePath, '../conf', 'schema.json')
  );

  if (loadedConfig === null) {
    console.error(`Error loading ${stackType} configuration.`);
    process.exit(1);
  }

  switch (stackType) {
    case 'app':
      return {
        ...commonConfigs,
        appConfig: loadedConfig,
      };

    case 'firewall':
      return {
        ...commonConfigs,
        fwConfig: loadedConfig,
      };

    case 'vpc':
      return {
        ...commonConfigs,
        vpcConfig: loadedConfig,
      };

    default:
      console.error(`Invalid stack name: '${stackType}'`);
      process.exit(1);
  }
}
