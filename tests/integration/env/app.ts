#!/usr/bin/env node
import 'source-map-support/register';
import { App } from 'aws-cdk-lib';
import { IntBaseStack } from './int_base_stack';

const app = new App();

const namePrefix = app.node.tryGetContext('namePrefix') ?? 'anfw';
const trustedAccountIds: string[] = app.node.tryGetContext('trustedAccountIds') ?? [];

new IntBaseStack(app, 'IntBaseStack', {
  namePrefix,
  trustedAccountIds: trustedAccountIds.length > 0 ? trustedAccountIds : undefined,
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION,
  },
  description: 'Long-lived INT base infrastructure for integration tests (TGW VPC, FW policy, config bucket, xaccount role)',
});

app.synth();
