import { Construct } from 'constructs';
import { LambdaStage, ServerlessStage } from './app_stages';
import { CodeBuildStep, CodePipeline, CodePipelineSource } from 'aws-cdk-lib/pipelines';
import { StacksetStage } from './stackset_stage';
import { NagSuppressions } from 'cdk-nag';
import { TaggedStack, TaggedStackProps } from '../../shared/lib/tagged_stack';
import * as cdk from 'aws-cdk-lib';

interface AppPipelineStackProps extends TaggedStackProps {
  namePrefix: string;
  config: { [key: string]: any };
  globalConfig: { [key: string]: any };
}

export class AppPipelineStack extends TaggedStack {
  constructor(scope: Construct, id: string, props: AppPipelineStackProps) {
    super(scope, id, props);

    const target_account = props.globalConfig.base.target_account_id;
    const delegated_admin_account = props.globalConfig.base.delegated_admin_account_id;
    const primary_region = props.globalConfig.base.primary_region;

    // Checks if the config object contains a "stackset" key in any region.
    function hasStacksetInAnyRegion(config: any): boolean {
      for (const regionKey in config) {
        if (Object.prototype.hasOwnProperty.call(config, regionKey)) {
          const region = config[regionKey];
          if ('stackset' in region) {
            return true;
          }
        }
      }
      return false;
    }

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
      commands: ['cd app', 'make'],
      primaryOutputDirectory: 'app/cdk.out',
      env: {
        STAGE: props.stage,
        STACK_NAME: 'app',
      },
      buildEnvironment: {
        privileged: true,
      },
    });

    // Add integration test step
    const integrationTestStep = new CodeBuildStep('IntegrationTest', {
      input: sourceCode,
      commands: ['chmod +x scripts/integration-test.sh', 'scripts/integration-test.sh'],
      env: {
        STAGE: props.stage,
        STACK_NAME: 'app',
        AWS_REGION: primary_region,
      },
      buildEnvironment: {
        privileged: false,
      },
    });

    const pipeline = new CodePipeline(this, 'app-pipeline', {
      synth: synthStep,
      crossAccountKeys: true,
      pipelineName: `cpp-${props.namePrefix}-app-${props.stage}`,
    });

    const lambdaWave = pipeline.addWave('LambdaStack');
    const serverlessWave = pipeline.addWave('ServerlessStack');
    const stacksetWave = hasStacksetInAnyRegion(props.config)
      ? pipeline.addWave('StacksetStack')
      : undefined;

    const serverlessStages: any[] = [];

    Object.keys(props.config).forEach((region: string) => {
      lambdaWave.addStage(
        new LambdaStage(this, `lambda-${region}`, {
          namePrefix: props.namePrefix,
          config: props.config[region],
          globalConfig: props.globalConfig,
          stage: props.stage,
          env: {
            region: `${region}`,
            account: `${target_account}`,
          },
          stageName: `${region}-lambda`,
          globalTags: props.globalTags,
        })
      );

      const serverlessStage = new ServerlessStage(this, `serverless-${region}`, {
        namePrefix: props.namePrefix,
        config: props.config[region],
        globalConfig: props.globalConfig,
        stage: props.stage,
        env: {
          region: `${region}`,
          account: `${target_account}`,
        },
        stageName: `${region}-serverless`,
        globalTags: props.globalTags,
      });

      serverlessWave.addStage(serverlessStage);
      serverlessStages.push(serverlessStage);

      if ('stackset' in props.config[region]) {
        stacksetWave!.addStage(
          new StacksetStage(this, `stackset-${region}`, {
            namePrefix: props.namePrefix,
            config: props.config[region]['stackset'],
            globalConfig: props.globalConfig,
            stage: props.stage,
            env: {
              region: `${region}`,
              account: `${delegated_admin_account}`,
            },
            stageName: `${region}-stackset`,
            globalTags: props.globalTags,
          })
        );
      }
    });

    // Add integration tests as post-deployment steps to the last serverless stage
    if (serverlessStages.length > 0) {
      serverlessStages[serverlessStages.length - 1].addPost(integrationTestStep);
    }

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
