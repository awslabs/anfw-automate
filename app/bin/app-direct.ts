#!/usr/bin/env node
/**
 * Direct-deploy entry point for the app module (no CodePipeline).
 *
 * The default entry point (`bin/app.ts`) deploys the app via `AppPipelineStack`
 * — a self-mutating CodePipeline that drives cross-account StackSet rollout and
 * the predictable release flow. That is the right driver for real deployments.
 *
 * This alternate entry point instantiates the SAME `LambdaStack` and
 * `ServerlessStack` directly, with the SAME config loader (SSM-first, file
 * fallback), for environments that need the solution deployed once into a single
 * account without a pipeline — specifically the INT environment, where the
 * solution runs in the firewall account against the int firewall policy.
 *
 * It is purely additive: it imports the existing stack classes and reuses the
 * exact props the pipeline's Stage wrappers pass. The pipeline, the Stage
 * classes, and the stacks themselves are unchanged — this is a second driver
 * over the same stacks, not a behavior change. Existing deployers are unaffected.
 *
 * Usage:
 *   cd app
 *   STAGE=int npx cdk deploy --all \
 *     --app "npx ts-node --prefer-ts-exts bin/app-direct.ts" --qualifier anfw
 */
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import {
  StackConfig,
  createConfigurationManager,
  ConfigurationError,
} from '../../shared/lib/config_loader';
import { AwsSolutionsChecks } from 'cdk-nag';
import { LambdaStack } from '../lib/lambda_stack';
import { ServerlessStack } from '../lib/serverless_stack';

async function main() {
  const app = new cdk.App();
  cdk.Aspects.of(app).add(new AwsSolutionsChecks({ verbose: true }));

  const STAGE = process.env.STAGE;
  if (!STAGE) {
    // eslint-disable-next-line no-console
    console.error('Required STAGE environment variable is not defined');
    process.exit(1);
  }

  try {
    const configManager = createConfigurationManager();
    const loadedConfig: StackConfig = await configManager.loadConfig('app', STAGE);

    const stage = loadedConfig.stage;
    const globalConfig = loadedConfig.globalConfig;
    const appConfig = loadedConfig.appConfig;
    const globalTags = loadedConfig.globalConfig?.pipeline?.tags ?? {};

    const namePrefix = `${globalConfig.project.aws_organziation_scope}-${globalConfig.project.project_name}-${globalConfig.project.module_name}`;
    const account = globalConfig.base.resource_account_id || '';

    // eslint-disable-next-line no-console
    console.log(`✅ Direct deploy: app module, stage '${STAGE}', prefix '${namePrefix}'`);

    const regionKeys = Object.keys(appConfig ?? {});
    if (regionKeys.length === 0) {
      // eslint-disable-next-line no-console
      console.error(`No region keys found in app config for stage '${STAGE}'.`);
      process.exit(1);
    }

    for (const regionKey of regionKeys) {
      const regionConfig = appConfig[regionKey];
      const env = { region: regionKey, account };

      // Same props the pipeline's LambdaStage passes — instantiated directly.
      const lambda = new LambdaStack(app, `lambda-${namePrefix}-${regionKey}-${stage}`, {
        env,
        namePrefix,
        vpcId: regionConfig.vpc_id,
        supportedRegions: regionConfig.supported_regions,
        policyArns: regionConfig.firewall_policy_arns,
        ruleOrder: regionConfig.rule_order,
        stage,
        globalTags,
      });

      // Same props the pipeline's ServerlessStage passes.
      const serverless = new ServerlessStack(
        app,
        `serverless-${namePrefix}-${regionKey}-${stage}`,
        {
          env,
          namePrefix,
          vpcId: regionConfig.vpc_id,
          organizationIds: globalConfig.base.organziation_ids,
          stage,
          globalTags,
        }
      );

      // ServerlessStack imports the rulecollect-lambda-arn export from LambdaStack,
      // so it must deploy after it (the pipeline enforces this via wave ordering).
      serverless.addDependency(lambda);
    }

    app.synth();
  } catch (error) {
    if (error instanceof ConfigurationError) {
      // eslint-disable-next-line no-console
      console.error('❌ Configuration Error:');
      // eslint-disable-next-line no-console
      console.error(error.getDetailedMessage());
      // eslint-disable-next-line no-console
      console.error('\n💡 Troubleshooting:');
      // eslint-disable-next-line no-console
      console.error(
        `   - SSM: /anfw-automate/${STAGE}/global/config and /anfw-automate/${STAGE}/app/config`
      );
      // eslint-disable-next-line no-console
      console.error(`   - Or files: conf/${STAGE}.json and app/conf/${STAGE}.json`);
    } else {
      // eslint-disable-next-line no-console
      console.error('❌ Unexpected error:', error);
    }
    process.exit(1);
  }
}

main().catch(error => {
  // eslint-disable-next-line no-console
  console.error('Error in main:', error);
  process.exit(1);
});
