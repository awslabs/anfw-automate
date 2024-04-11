#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { StackConfig, loadDeploymentConfig } from '../../shared/lib/config_loader'
import { AwsSolutionsChecks, NagSuppressions } from "cdk-nag";
import { AppPipelineStack } from '../lib/app_pipeline_stack';

const STAGE = process.env.STAGE;
if (!STAGE) {
  console.error('Required STAGE environment variable is not defined');
  process.exit(1);
}

const vpcRegion = process.env.AWS_REGION
if (!vpcRegion) {
  console.error('Required AWS_REGION environment variable is not defined');
  process.exit(1);
}

// const STACK_NAME = "app";
// Define your tagging configuration
const globalTags = {
  Environment: 'Dev',
  Owner: 'John Doe'
};

// Load configuration
const loadedConfig: StackConfig | null = loadDeploymentConfig(__dirname, STAGE, "app");
const stage = loadedConfig?.stage
const globalConfig = loadedConfig?.globalConfig
const appConfig = loadedConfig?.appConfig
const stacksetConfig = loadedConfig?.stacksetConfig

const namePrefix = `${(globalConfig as any).project?.aws_organziation_scope}-${(globalConfig as any).project?.project_name}-${(globalConfig as any).project.module_name}`

const app = new cdk.App();
cdk.Aspects.of(app).add(new AwsSolutionsChecks({ verbose: true }));
//Apply all tags
Object.entries(globalTags).forEach(([key, value]) => {
  cdk.Tags.of(app).add(`${key}`, `${value}`);
});

// if (STACK_NAME === 'app' || STACK_NAME === 'all') {
new AppPipelineStack(app, `app-pipeline-anfw-${stage}`, {
  stackName: `cpp-app-${namePrefix}-${stage}`,
  env: {
    region: (globalConfig as any).base?.primary_region || "",
    account: (globalConfig as any).base?.resource_account_id || ""
  },
  namePrefix: namePrefix,
  stage: stage,
  stacksetConfig: stacksetConfig,
  config: appConfig,
  globalConfig: globalConfig,
});
// }

// Suppress CDK NAG findings for autogenerated support stacks
const exclusionList: string[] = [
  'Default/CrossRegionCodePipelineReplicationBucketEncryptionKey/Resource',
  'Default/CrossRegionCodePipelineReplicationBucket/Resource',
];

app.node.findAll().forEach(element => {
  if (exclusionList.some(ele => element.node.path.includes(ele))) {
    NagSuppressions.addResourceSuppressions(element, [{
      id: 'AwsSolutions-KMS5',
      reason: 'The Key is used for pipeline artifacts and need not be rotated.',
    }]);

    NagSuppressions.addResourceSuppressions(element, [{
      id: 'AwsSolutions-S1',
      reason: 'The Bucket is CDK managed and used for artifact storage',
    }]);

  }
});

app.synth();

