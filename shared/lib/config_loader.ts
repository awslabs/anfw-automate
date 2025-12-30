import * as fs from 'fs';
import * as path from 'path';
import Ajv from 'ajv';
import addFormats from 'ajv-formats';

export interface StackConfig {
  [key: string]: any;
}

function loadConfigFromFile(configPath: string, schemaPath: string): StackConfig | null {
  if (!fs.existsSync(configPath)) {
    // eslint-disable-next-line no-console
    console.error(`JSON file does not exist at path '${configPath}'.`);
    process.exit(1);
  }

  // Read the JSON schema
  let schema;
  try {
    schema = JSON.parse(fs.readFileSync(schemaPath, 'utf-8'));
  } catch (err) {
    // eslint-disable-next-line no-console
    console.error(`Error reading/parsing JSON schema at path '${schemaPath}':`, err);
    process.exit(1);
  }

  // Read the JSON data
  let data;
  try {
    data = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
  } catch (err) {
    // eslint-disable-next-line no-console
    console.error(`Error reading/parsing JSON at path '${configPath}':`, err);
    process.exit(1);
  }

  const ajv = new Ajv({ allErrors: true }); // Initialize Ajv
  addFormats(ajv); // Add format validation
  const validate = ajv.compile(schema); // Compile the schema
  const valid = validate(data); // Validate the data

  if (!valid) {
    // eslint-disable-next-line no-console
    console.error(`Validation errors in ${configPath}:`, validate.errors);
    return null;
  } else {
    // eslint-disable-next-line no-console
    console.log(`Validation successful for ${configPath}`);
    return data;
  }
}

export function loadDeploymentConfig(
  configBasePath: string,
  stage: string,
  stackType: string
): StackConfig | null {
  const globalConfig = loadConfigFromFile(
    path.join(__dirname, '../../conf', `${stage}.json`),
    path.join(__dirname, '../../conf', 'schema.json')
  );

  if (globalConfig === null) {
    // eslint-disable-next-line no-console
    console.error('Error loading global configuration.');
    process.exit(1);
  }

  // Declare commonConfigs with default values
  const commonConfigs: StackConfig = { stage, globalConfig };

  const loadedConfig = loadConfigFromFile(
    path.join(configBasePath, '../conf', `${stage}.json`),
    path.join(configBasePath, '../conf', 'schema.json')
  );

  if (loadedConfig === null) {
    // eslint-disable-next-line no-console
    console.error(`Error loading ${stackType} configuration.`);
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
