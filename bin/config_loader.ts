import * as fs from 'fs';
import * as path from 'path';

export interface StackConfig {
    [key: string]: any; // Use an index signature to allow dynamic keys and values
}

function loadAppConfigFromFile(configPath: string): StackConfig | null {
    if (!fs.existsSync(configPath)) {
        console.error(`JSON file does not exist at path '${configPath}'.`);
        return null;
    }

    try {
        const configData = fs.readFileSync(configPath, 'utf8');
        return JSON.parse(configData);
    } catch (err) {
        console.error(`Error reading/parsing JSON at path '${configPath}':`, err);
        return null;
    }
}

export function loadAppConfig(stage: string, stackType: string): StackConfig | null {
    const stageDir = path.join(__dirname, '../conf', stage);
    const globalConfig = loadAppConfigFromFile(path.join(stageDir, 'global.json'));

    // Declare commonConfigs with default values
    let commonConfigs: StackConfig = { stage, globalConfig };

    // Load stack-specific configurations based on stackType
    switch (stackType) {
        case 'app':
            // Update commonConfigs based on the globalConfig condition
            if (globalConfig && globalConfig.pipeline.deploy_stacksets === true) {
                commonConfigs = { ...commonConfigs, stacksetConfig: loadAppConfigFromFile(path.join(stageDir, 'stackset.json')) };
            } else {
                console.log('Stack sets deployment is not enabled in global configuration.');
                process.exit(1);
            }
            return {
                ...commonConfigs,
                appConfig: loadAppConfigFromFile(path.join(stageDir, 'app.json'))
            };

        case 'firewall':
            return {
                ...commonConfigs,
                fwConfig: loadAppConfigFromFile(path.join(stageDir, 'firewall.json'))
            };

        case 'vpc':
            return {
                ...commonConfigs,
                vpcConfig: loadAppConfigFromFile(path.join(stageDir, 'vpc.json'))
            };

        case 'all':
            if (globalConfig && globalConfig.pipeline.deploy_stacksets === true) {
                commonConfigs = { ...commonConfigs, stacksetConfig: loadAppConfigFromFile(path.join(stageDir, 'stackset.json')) };
            } else {
                console.log('Stack sets deployment is not enabled in global configuration.');
                process.exit(1);
            }
            return {
                ...commonConfigs,
                vpcConfig: loadAppConfigFromFile(path.join(stageDir, 'vpc.json')),
                fwConfig: loadAppConfigFromFile(path.join(stageDir, 'firewall.json')),
                appConfig: loadAppConfigFromFile(path.join(stageDir, 'app.json'))
            };

        default:
            console.error(`Invalid stack name: '${stackType}'`);
            return null;
    }
}
