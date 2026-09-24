#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { AwsSolutionsChecks } from 'cdk-nag';
import { TransitGatewayStack } from '../network/transit_gateway_stack';

/**
 * Dedicated entry point for the shared-once Transit Gateway hub.
 *
 * This is intentionally SEPARATE from bin/foundational.ts: the TGW is created
 * once in the network account and RAM-shared, not per-stage/per-region. Deploy
 * with an explicit --app so it does not collide with the foundational app:
 *
 *   cd foundational
 *   yarn exec cdk --app "npx ts-node --prefer-ts-exts bin/transit_gateway.ts" deploy \
 *     --context networkAccountId=040781035187 \
 *     --context sharePrincipals=421222417363,537622539377,868363312618 \
 *     --context namePrefix=af-anfw-automate
 *
 * Region defaults to eu-west-1 (CDK_DEFAULT_REGION overrides). Credentials must
 * resolve to the network account.
 */
const app = new cdk.App();
cdk.Aspects.of(app).add(new AwsSolutionsChecks({ verbose: true }));

const networkAccountId = app.node.tryGetContext('networkAccountId') ?? process.env.CDK_DEFAULT_ACCOUNT;
if (!networkAccountId) {
  console.error(
    'networkAccountId is required (pass --context networkAccountId=<acct> or set CDK_DEFAULT_ACCOUNT)'
  );
  process.exit(1);
}

const principalsRaw = app.node.tryGetContext('sharePrincipals') ?? '';
const sharePrincipals: string[] = String(principalsRaw)
  .split(',')
  .map(s => s.trim())
  .filter(Boolean);
if (sharePrincipals.length === 0) {
  console.error(
    'sharePrincipals is required (pass --context sharePrincipals=<acct1>,<acct2>,... — the firewall and INT accounts)'
  );
  process.exit(1);
}

const namePrefix = app.node.tryGetContext('namePrefix') ?? 'af-anfw-automate';
const region = process.env.CDK_DEFAULT_REGION ?? 'eu-west-1';
// The hub is shared-once, not stage-scoped; tag it 'shared'.
const stage = app.node.tryGetContext('tgwStage') ?? 'shared';

new TransitGatewayStack(app, `tgw-${namePrefix}-shared`, {
  env: { account: networkAccountId, region },
  namePrefix,
  stage,
  sharePrincipals,
  globalTags: {},
  description:
    'Shared-once org-wide Transit Gateway + RAM share; publishes /anfw-automate/shared/tgw-id',
});

app.synth();
