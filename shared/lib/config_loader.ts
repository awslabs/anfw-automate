import * as fs from 'fs';
import * as path from 'path';
import Ajv from 'ajv';
import addFormats from 'ajv-formats';

export interface StackConfig {
    [key: string]: any; // Use an index signature to allow dynamic keys and values
}


function loadAppConfigFromFile(stage: string, filename: string): StackConfig | null {
    const configPath = path.join(__dirname, '../conf', stage, filename);
    const schemaPath = path.join(__dirname, '../conf', 'schemas', filename);

    if (!fs.existsSync(configPath)) {
        console.error(`JSON file does not exist at path '${configPath}'.`);
        process.exit(1);
    }

    // Read the JSON schema
    let schema;
    try {
        schema = JSON.parse(fs.readFileSync(schemaPath, 'utf-8'));
    } catch (err) {
        console.error(`Error reading/parsing JSON schema at path '${schemaPath}':`, err);
        process.exit(1);
    }

    // Read the JSON data
    let data;
    try {
        data = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
    } catch (err) {
        console.error(`Error reading/parsing JSON at path '${configPath}':`, err);
        process.exit(1);
    }

    const ajv = new Ajv({ allErrors: true }); // Initialize Ajv
    addFormats(ajv); // Add format validation
    const validate = ajv.compile(schema); // Compile the schema
    const valid = validate(data); // Validate the data

    if (!valid) {
        console.error(`Validation errors in ${configPath}:`, validate.errors);
        return null;
    } else {
        console.log(`Validation successful for ${configPath}`);
        return data;
    }
}

export function loadAppConfig(stage: string, stackType: string): StackConfig | null {
    const globalConfig = loadAppConfigFromFile(stage, 'global.json');
    const stacksetConfig = loadAppConfigFromFile(stage, 'stackset.json');
    const appConfig = loadAppConfigFromFile(stage, 'app.json')
    const fwConfig = loadAppConfigFromFile(stage, 'firewall.json');
    const vpcConfig = loadAppConfigFromFile(stage, 'vpc.json');

    if (globalConfig === null) {
        console.error('Error loading global configuration.');
        process.exit(1);
    }

    // Declare commonConfigs with default values
    let commonConfigs: StackConfig = { stage, globalConfig };

    // Load stack-specific configurations based on stackType
    switch (stackType) {
        case 'app':
            if (stacksetConfig === null) {
                console.error('Error loading stackset configuration.');
                process.exit(1);
            }

            if (appConfig === null) {
                console.error('Error loading app configuration.');
                process.exit(1);
            }

            return {
                ...commonConfigs,
                stacksetConfig: stacksetConfig,
                appConfig: appConfig
            };

        case 'firewall':
            if (fwConfig === null) {
                console.error('Error loading firewall configuration.');
                process.exit(1);
            }

            return {
                ...commonConfigs,
                fwConfig
            };

        case 'vpc':
            if (vpcConfig === null) {
                console.error('Error loading VPC configuration.');
                process.exit(1);
            }

            return {
                ...commonConfigs,
                vpcConfig
            };

        case 'all':
            if (stacksetConfig === null) {
                console.error('Error loading stackset configuration.');
                process.exit(1);
            }

            if (appConfig === null) {
                console.error('Error loading app configuration.');
                process.exit(1);
            }

            if (fwConfig === null) {
                console.error('Error loading firewall configuration.');
                process.exit(1);
            }

            if (vpcConfig === null) {
                console.error('Error loading VPC configuration.');
                process.exit(1);
            }

            return {
                ...commonConfigs,
                stacksetConfig: stacksetConfig,
                vpcConfig: vpcConfig,
                fwConfig: fwConfig,
                appConfig: appConfig
            };

        default:
            console.error(`Invalid stack name: '${stackType}'`);
            process.exit(1);
    }
}