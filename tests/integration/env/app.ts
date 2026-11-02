#!/usr/bin/env node
import 'source-map-support/register';
import { App } from 'aws-cdk-lib';
import { IntBaseStack } from './int_base_stack';

const app = new App();

const namePrefix = app.node.tryGetContext('namePrefix') ?? 'anfw';
// The central (firewall/automation) account that runs RuleCollect/RuleExecute
// and assumes the tenant cross-account role. Defaults (in the stack) to the
// current account for a same-account setup; override via context for the
// multi-account INT topology (the central/firewall account).
const centralAccountId: string | undefined =
  app.node.tryGetContext('centralAccountId') ?? undefined;

// Foundational outputs supplied as context (KISS — no cross-account SSM):
//   --context sharedTgwId=tgw-xxxx         (from the network-account TGW stack)
//   --context firewallPolicyArn=arn:...    (from the int firewall fabric)
const sharedTgwId: string | undefined = app.node.tryGetContext('sharedTgwId');
const firewallPolicyArn: string | undefined = app.node.tryGetContext('firewallPolicyArn');

if (!sharedTgwId || !firewallPolicyArn) {
  // eslint-disable-next-line no-console
  console.error(
    'Both --context sharedTgwId=<tgw-id> and --context firewallPolicyArn=<arn> are required.\n' +
      '  sharedTgwId: output of the foundational TransitGatewayStack (network account).\n' +
      '  firewallPolicyArn: int-stage foundational Network Firewall policy ARN (firewall account).'
  );
  process.exit(1);
}

new IntBaseStack(app, 'IntBaseStack', {
  namePrefix,
  centralAccountId,
  sharedTgwId,
  firewallPolicyArn,
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION,
  },
  description:
    'Long-lived INT tenant tier for integration tests (tenant VPC + TGW attachment ' +
    '+ egress-to-TGW + reachability probe + config bucket + xaccount role). ' +
    'Shared TGW id and firewall policy ARN supplied via context (foundational outputs).',
});

app.synth();
