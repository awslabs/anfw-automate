import { Stack, StackProps } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { VPCStage } from "./vpc_stages";
import {
    CodeBuildStep,
    CodePipeline,
    CodePipelineSource,
} from "aws-cdk-lib/pipelines";
import { NagSuppressions } from 'cdk-nag';

interface VpcPipelineStackProps extends StackProps {
    namePrefix: string;
    stage: string;
    config: { [key: string]: any };
    globalConfig: { [key: string]: any };
}

export class VpcPipelineStack extends Stack {
    constructor(scope: Construct, id: string, props: VpcPipelineStackProps) {
        super(scope, id, props);

        const target_account = props.globalConfig.base.target_account_id
        const primary_region = props.globalConfig.base.primary_region
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
                'cd vpc',
                'make'
            ],
            env: {
                STAGE: props.stage,
                STACK_NAME: 'vpc'
            },
            buildEnvironment: {
                privileged: true,
            }
        });

        const pipeline = new CodePipeline(this, "vpc-pipeline", {
            synth: synthStep,
            crossAccountKeys: true,
            pipelineName: `cpp-${props.namePrefix}-vpc-${props.stage}`,
        });

        const vpcWave = pipeline.addWave("VpcStack");

        props.globalConfig.pipeline.vpc_regions.forEach((region: string) => {
            vpcWave.addStage(
                new VPCStage(this, `vpc-${region}`, {
                    namePrefix: props.namePrefix,
                    config: props.config[region],
                    globalConfig: props.globalConfig,
                    stage: props.stage,
                    env: {
                        region: `${region}`,
                        account: `${target_account}`
                    },
                    stageName: `${region}-vpc`
                })
            )

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


