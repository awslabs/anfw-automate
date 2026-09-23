#!/usr/bin/env node
import 'source-map-support/register';
import { App } from 'aws-cdk-lib';
import { IntBaseStack } from './int_base_stack';

const app = new App();

const namePrefix = app.node.tryGetContext('namePrefix') ?? 'anfw';
// The central (firewall/automation) account that runs RuleCollect/RuleExecute
// and assumes the tenant cross-account role. Defaults (in the stack) to the
// current account for a same-account setup; override via context for the
// multi-account INT topology (firewall account 421222417363).
const centralAccountId: string | undefined =
  app.node.tryGetContext('centralAccountId') ?? undefined;

new IntBaseStack(app, 'IntBaseStack', {
  namePrefix,
  centralAccountId,
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION,
  },
  description:
    'Long-lived INT tenant tier for integration tests (tenant VPC + TGW attachment ' +
    '+ egress-to-TGW + reachability probe + config bucket + xaccount role). ' +
    'Shared TGW and firewall policy are resolved from SSM (foundational).',
});

app.synth();
