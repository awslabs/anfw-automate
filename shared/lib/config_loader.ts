import * as fs from 'fs';
import * as path from 'path';
import Ajv from 'ajv';
import addFormats from 'ajv-formats';

export interface StackConfig {
    [key: string]: any;
}

function loadConfigFromFile(configPath: string, schemaPath: string): StackConfig | null {
    // const configPath = path.join(configBasePath, '../conf', stage, filename);
    // const schemaPath = path.join(configBasePath, '../conf', 'schemas', filename);

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

export function loadDeploymentConfig(configBasePath: string, stage: string, stackType: string): StackConfig | null {
    const globalConfig = loadConfigFromFile(path.join(__dirname, '../conf', `${stage}.json`),
        path.join(__dirname, '../conf', 'schema.json'));

    if (globalConfig === null) {
        console.error('Error loading global configuration.');
        process.exit(1);
    }

    // Declare commonConfigs with default values
    let commonConfigs: StackConfig = { stage, globalConfig };

    // Load stack-specific configurations based on stackType
    switch (stackType) {
        case 'app':
            const appConfig = loadConfigFromFile(path.join(configBasePath, '../conf', stage, 'app.json'),
                path.join(configBasePath, '../conf', 'schemas', 'app.json'));

            if (appConfig === null) {
                console.error('Error loading app configuration.');
                process.exit(1);
            }

            if (globalConfig.pipeline.deploy_stacksets) {
                const stacksetConfig = loadConfigFromFile(path.join(configBasePath, '../conf', stage, 'stackset.json'),
                    path.join(configBasePath, '../conf', 'schemas', 'stackset.json'));
                if (stacksetConfig === null) {
                    console.error('Error loading stackset configuration.');
                    process.exit(1);
                }
                return {
                    ...commonConfigs,
                    stacksetConfig: stacksetConfig,
                    appConfig: appConfig
                };
            }

            return {
                ...commonConfigs,
                appConfig: appConfig
            };

        case 'firewall':
            const fwConfig = loadConfigFromFile(path.join(configBasePath, '../conf', stage, 'firewall.json'),
                path.join(configBasePath, '../conf', 'schemas', 'firewall.json'));
            if (fwConfig === null) {
                console.error('Error loading firewall configuration.');
                process.exit(1);
            }

            return {
                ...commonConfigs,
                fwConfig
            };

        case 'vpc':
            const vpcConfig = loadConfigFromFile(path.join(configBasePath, '../conf', stage, 'vpc.json'),
                path.join(configBasePath, '../conf', 'schemas', 'vpc.json'));
            if (vpcConfig === null) {
                console.error('Error loading VPC configuration.');
                process.exit(1);
            }

            return {
                ...commonConfigs,
                vpcConfig
            };

        // case 'all':
        //     const appConfigAll = loadConfigFromFile(configBasePath, stage, 'app.json');
        //     const fwConfigAll = loadConfigFromFile(configBasePath, stage, 'firewall.json');
        //     const vpcConfigAll = loadConfigFromFile(configBasePath, stage, 'vpc.json');

        //     if (appConfigAll === null) {
        //         console.error('Error loading app configuration.');
        //         process.exit(1);
        //     }

        //     if (fwConfigAll === null) {
        //         console.error('Error loading firewall configuration.');
        //         process.exit(1);
        //     }

        //     if (vpcConfigAll === null) {
        //         console.error('Error loading VPC configuration.');
        //         process.exit(1);
        //     }

        //     if (globalConfig.pipeline.deploy_stacksets) {
        //         const stacksetConfigAll = loadConfigFromFile(configBasePath, stage, 'stackset.json');
        //         if (stacksetConfigAll === null) {
        //             console.error('Error loading stackset configuration.');
        //             process.exit(1);
        //         }
        //         return {
        //             ...commonConfigs,
        //             stacksetConfig: stacksetConfigAll,
        //             vpcConfig: vpcConfigAll,
        //             fwConfig: fwConfigAll,
        //             appConfig: appConfigAll
        //         };
        //     }

        //     return {
        //         ...commonConfigs,
        //         vpcConfig: vpcConfigAll,
        //         fwConfig: fwConfigAll,
        //         appConfig: appConfigAll
        //     };

        default:
            console.error(`Invalid stack name: '${stackType}'`);
            process.exit(1);
    }
}