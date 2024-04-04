import { Stack } from "aws-cdk-lib";
import { Construct } from "constructs";
import * as cloudformation from "aws-cdk-lib/aws-cloudformation";
import * as fs from "fs";

export class StacksetStack extends Stack {
    constructor(scope: Construct, id: string, props: {
        namePrefix: string;
        targetAccountId: string;
        deployRegions: [string];
        permissionModel: string;
        autoDeployment: boolean;
        accountFilterType: string;
        accounts?: [string];
        organizationalUnitIds?: [string];
        failureTolerancePercentage: number;
        maxConcurrentPercentage: number;
        regionConcurrencyType: string;
        callAs: string;
        stage: string;
    }) {
        super(scope, id);

        // Load YAML Stack Template
        const yamlTemplate = fs.readFileSync('templates/spoke-serverless-stack.yaml', 'utf8');

        // Create Deployment Targets Property
        const stackSetProps: any = {
            accountFilterType: props.accountFilterType,
        };

        if (props.accounts) {
            stackSetProps.accounts = props.accounts;
        }

        if (props.organizationalUnitIds) {
            stackSetProps.organizationalUnitIds = props.organizationalUnitIds;
        }

        // Define Stacket Set
        new cloudformation.CfnStackSet(this, 'SpokeStackSet', {
            permissionModel: props.permissionModel,
            stackSetName: `${props.namePrefix}-resources-${props.stage}`,
            autoDeployment: {
                enabled: props.autoDeployment,
                retainStacksOnAccountRemoval: props.autoDeployment ? false : undefined,
            },
            callAs: props.callAs,
            capabilities: ['CAPABILITY_AUTO_EXPAND', 'CAPABILITY_NAMED_IAM'],
            description: `Security - Network Firewall Stackset deploying required spoke resources using "${props.permissionModel}" permission model`,
            operationPreferences: {
                failureTolerancePercentage: props.failureTolerancePercentage,
                maxConcurrentPercentage: props.maxConcurrentPercentage,
                regionConcurrencyType: props.regionConcurrencyType,
            },
            parameters: [{
                parameterKey: 'CentralEventBusARN',
                parameterValue: `arn:aws:events:${this.region}:${props.targetAccountId}:event-bus/eb-${props.namePrefix}-ConfigEventBus-${props.stage}`,
            },
            {
                parameterKey: 'CentralEventBusId',
                parameterValue: `eb-${props.namePrefix}-ConfigEventBus-${props.stage}`,
            },
            {
                parameterKey: 'TargetAccountId',
                parameterValue: `${props.targetAccountId}`,
            },
            {
                parameterKey: 'NamePrefix',
                parameterValue: `${props.namePrefix}`,
            },
            {
                parameterKey: 'NameDotPrefix',
                parameterValue: `${props.namePrefix.replace(/-/g, ".")}`,
            },
            {
                parameterKey: 'Stage',
                parameterValue: `${props.stage}`,
            },
            ],
            stackInstancesGroup: [{
                deploymentTargets: Object.keys(stackSetProps).length === 0 ? undefined : stackSetProps,
                regions: props.deployRegions,
            }],
            tags: [{
                key: 'component',
                value: 'anfw',
            }],
            templateBody: yamlTemplate
        });
    }
}