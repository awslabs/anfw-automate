import { Stack, StackProps } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { LambdaStage, ServerlessStage } from "./app_stages";
import {
    CodeBuildStep,
    CodePipeline,
    CodePipelineSource,
} from "aws-cdk-lib/pipelines";
import { StacksetStage } from './stackset_stage';
import { NagSuppressions } from 'cdk-nag';

interface AppPipelineStackProps extends StackProps {
    namePrefix: string;
    stage: string;
    config: { [key: string]: any; };
    stacksetConfig: { [key: string]: any; };
    globalConfig: { [key: string]: any; };
}

export class AppPipelineStack extends Stack {
    constructor(scope: Construct, id: string, props: AppPipelineStackProps) {
        super(scope, id, props);

        const target_account = props.globalConfig.base.target_account_id;
        const delegated_admin_account = props.globalConfig.base.delegated_admin_account_id;

        const primary_region = props.globalConfig.base.primary_region;
        const name_dot_prefix = props.namePrefix.replace(/-/g, ".");

        // Source repo
        const sourceCode = CodePipelineSource.connection(
            props.globalConfig.pipeline.repo_name,
            props.globalConfig.pipeline.repo_branch_name,
            {
                connectionArn: props.globalConfig.pipeline.codestar_connection_arn,
            },
        );

        const synthStep = new CodeBuildStep("Synth", {
            input: sourceCode,
            commands: [
                'cd app',
                'make'
            ],
            primaryOutputDirectory: 'app/cdk.out',
            env: {
                STAGE: props.stage,
                STACK_NAME: 'app'
            },
            buildEnvironment: {
                privileged: true,
            },
        });

        const pipeline = new CodePipeline(this, "app-pipeline", {
            synth: synthStep,
            crossAccountKeys: true,
            pipelineName: `cpp-${props.namePrefix}-app-${props.stage}`,
        });

        const lambdaWave = pipeline.addWave("LambdaStack");
        const serverlessWave = pipeline.addWave("ServerlessStack");
        const stacksetWave = props.globalConfig.pipeline.deploy_stacksets ? pipeline.addWave("StacksetStack") : undefined;

        props.globalConfig.pipeline.app_regions.forEach((region: string) => {
            lambdaWave.addStage(
                new LambdaStage(this, `lambda-${region}`, {
                    namePrefix: props.namePrefix,
                    config: props.config[region],
                    globalConfig: props.globalConfig,
                    stage: props.stage,
                    env: {
                        region: `${region}`,
                        account: `${target_account}`
                    },
                    stageName: `${region}-lambda`
                })
            );

            serverlessWave.addStage(
                new ServerlessStage(this, `serverless-${region}`, {
                    namePrefix: props.namePrefix,
                    config: props.config[region],
                    globalConfig: props.globalConfig,
                    stage: props.stage,
                    env: {
                        region: `${region}`,
                        account: `${target_account}`
                    },
                    stageName: `${region}-serverless`
                })
            );

            stacksetWave!.addStage(
                new StacksetStage(this, `stackset-${region}`, {
                    namePrefix: props.namePrefix,
                    config: props.stacksetConfig[region],
                    globalConfig: props.globalConfig,
                    stage: props.stage,
                    env: {
                        region: `${region}`,
                        account: `${delegated_admin_account}`
                    },
                    stageName: `${region}-stackset`
                })
            );
        });

        pipeline.buildPipeline();

        NagSuppressions.addStackSuppressions(this, [{
            id: 'AwsSolutions-S1',
            reason: 'The Bucket is CDK managed and used for artifact storage',
        }]);

        NagSuppressions.addStackSuppressions(this, [{
            id: 'AwsSolutions-KMS5',
            reason: 'The Key is used for pipeline artifacts and need not be rotated.',
        }]);

        NagSuppressions.addStackSuppressions(this, [{
            id: 'AwsSolutions-IAM5',
            reason: 'Known wildcards coming from CDK Pipeline construct',
        }]);

        NagSuppressions.addStackSuppressions(this, [{
            id: 'AwsSolutions-CB3',
            reason: 'Privileged mode required to package Lambda',
        }]);
    }
}
