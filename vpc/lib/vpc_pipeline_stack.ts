import { Construct } from 'constructs';
import { VPCStage } from './vpc_stages';
import { TaggedStack, TaggedStackProps } from '../../shared/lib/tagged_stack';
import { CodeBuildStep, CodePipeline, CodePipelineSource } from 'aws-cdk-lib/pipelines';
import { NagSuppressions } from 'cdk-nag';
import * as cdk from 'aws-cdk-lib';

interface VpcPipelineStackProps extends TaggedStackProps {
  namePrefix: string;
  config: { [key: string]: any };
  globalConfig: { [key: string]: any };
}

export class VpcPipelineStack extends TaggedStack {
  constructor(scope: Construct, id: string, props: VpcPipelineStackProps) {
    super(scope, id, props);

    const target_account = props.globalConfig.base.target_account_id;

    // Source repo
    const sourceCode = CodePipelineSource.connection(
      props.globalConfig.pipeline.repo_name,
      props.globalConfig.pipeline.repo_branch_name,
      {
        connectionArn: props.globalConfig.pipeline.codestar_connection_arn,
      }
    );

    const synthStep = new CodeBuildStep('Synth', {
      input: sourceCode,
      commands: ['cd vpc', 'make'],
      primaryOutputDirectory: 'vpc/cdk.out',
      env: {
        STAGE: props.stage,
        STACK_NAME: 'vpc',
      },
      buildEnvironment: {
        privileged: true,
      },
    });

    const pipeline = new CodePipeline(this, 'vpc-pipeline', {
      synth: synthStep,
      crossAccountKeys: true,
      pipelineName: `cpp-${props.namePrefix}-vpc-${props.stage}`,
    });

    const vpcWave = pipeline.addWave('VpcStack');

    const vpcStages: any[] = [];

    Object.keys(props.config).forEach((region: string) => {
      const vpcStage = new VPCStage(this, `vpc-${region}`, {
        namePrefix: props.namePrefix,
        config: props.config[region],
        globalConfig: props.globalConfig,
        stage: props.stage,
        env: {
          region: `${region}`,
          account: `${target_account}`,
        },
        stageName: `${region}-vpc`,
        globalTags: props.globalTags,
      });

      vpcWave.addStage(vpcStage);
      vpcStages.push(vpcStage);
    });

    pipeline.buildPipeline();

    NagSuppressions.addStackSuppressions(this as unknown as cdk.Stack, [
      {
        id: 'AwsSolutions-S1',
        reason: 'The Bucket is CDK managed and used for artifact storage',
      },
    ]);

    NagSuppressions.addStackSuppressions(this as unknown as cdk.Stack, [
      {
        id: 'AwsSolutions-KMS5',
        reason: 'The Key is used for pipeline artifacts and need not be rotated.',
      },
    ]);

    NagSuppressions.addStackSuppressions(this as unknown as cdk.Stack, [
      {
        id: 'AwsSolutions-IAM5',
        reason: 'Known wildcards coming from CDK Pipeline construct',
      },
    ]);

    NagSuppressions.addStackSuppressions(this as unknown as cdk.Stack, [
      {
        id: 'AwsSolutions-CB3',
        reason: 'Privileged mode required to package Lambda',
      },
    ]);
  }
}
