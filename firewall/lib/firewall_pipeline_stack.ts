import { RemovalPolicy, Stack, StackProps } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { TaggedStack, TaggedStackProps } from '../../shared/lib/tagged_stack';
import { FirewallStage, BaseRoutingStage, RoutingStage } from './firewall_stages';
import { CodeBuildStep, CodePipeline, CodePipelineSource } from 'aws-cdk-lib/pipelines';
import { NagSuppressions } from 'cdk-nag';
import * as cdk from 'aws-cdk-lib';

interface FirewallPipelineStackProps extends TaggedStackProps {
  namePrefix: string;
  config: { [key: string]: any };
  globalConfig: { [key: string]: any };
}

export class FirewallPipelineStack extends TaggedStack {
  constructor(scope: Construct, id: string, props: FirewallPipelineStackProps) {
    super(scope, id, props);

    const target_account = props.globalConfig.base.target_account_id;
    const primary_region = props.globalConfig.base.primary_region;
    const name_dot_prefix = props.namePrefix.replace(/-/g, '.');

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
      commands: ['cd firewall', 'make'],
      primaryOutputDirectory: 'firewall/cdk.out',
      env: {
        STAGE: props.stage,
        STACK_NAME: 'firewall',
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
        STACK_NAME: 'firewall',
        AWS_REGION: primary_region,
      },
      buildEnvironment: {
        privileged: false,
      },
    });

    const pipeline = new CodePipeline(this, 'firewall-pipeline', {
      synth: synthStep,
      crossAccountKeys: true,
      pipelineName: `cpp-${props.namePrefix}-fw-${props.stage}`,
    });

    const firewallWave = pipeline.addWave('FirewallStack');
    const baseRoutingWave = pipeline.addWave('BaseRoutingStack');
    const routingWave = pipeline.addWave('RoutingStack');

    const routingStages: any[] = [];

    Object.keys(props.config).forEach((region: string) => {
      firewallWave.addStage(
        new FirewallStage(this, `firewall-${region}`, {
          namePrefix: props.namePrefix,
          config: props.config[region],
          globalConfig: props.globalConfig,
          stage: props.stage,
          env: {
            region: `${region}`,
            account: `${target_account}`,
          },
          stageName: `${region}-firewall`,
          globalTags: props.globalTags,
        })
      );

      baseRoutingWave.addStage(
        new BaseRoutingStage(this, `baserouting-${region}`, {
          namePrefix: props.namePrefix,
          config: props.config[region],
          globalConfig: props.globalConfig,
          stage: props.stage,
          env: {
            region: `${region}`,
            account: `${target_account}`,
          },
          stageName: `${region}-baserouting`,
          globalTags: props.globalTags,
        })
      );

      const routingStage = new RoutingStage(this, `routing-${region}`, {
        namePrefix: props.namePrefix,
        config: props.config[region],
        globalConfig: props.globalConfig,
        stage: props.stage,
        env: {
          region: `${region}`,
          account: `${target_account}`,
        },
        stageName: `${region}-routing`,
        globalTags: props.globalTags,
      });

      routingWave.addStage(routingStage);
      routingStages.push(routingStage);
    });

    // Add integration tests as post-deployment steps to the last routing stage
    if (routingStages.length > 0) {
      routingStages[routingStages.length - 1].addPost(integrationTestStep);
    }

    pipeline.buildPipeline();

    NagSuppressions.addStackSuppressions(this as any, [
      {
        id: 'AwsSolutions-S1',
        reason: 'The Bucket is CDK managed and used for artifact storage',
      },
    ]);

    NagSuppressions.addStackSuppressions(this as any, [
      {
        id: 'AwsSolutions-KMS5',
        reason: 'The Key is used for pipeline artifacts and need not be rotated.',
      },
    ]);

    NagSuppressions.addStackSuppressions(this as any, [
      {
        id: 'AwsSolutions-IAM5',
        reason: 'Known wildcards coming from CDK Pipeline construct',
      },
    ]);

    NagSuppressions.addStackSuppressions(this as any, [
      {
        id: 'AwsSolutions-CB3',
        reason: 'Privileged mode required to package Lambda',
      },
    ]);
  }
}
