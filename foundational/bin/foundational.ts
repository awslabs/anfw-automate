#!/usr/bin/env node
import 'source-map-support/register';
import * as path from 'path';
import * as cdk from 'aws-cdk-lib';
import { AwsSolutionsChecks, NagSuppressions } from 'cdk-nag';
import { loadDeploymentConfig, ConfigurationError } from '../../shared/lib/config_loader';
import { VpcStack } from '../vpc/vpc_stack';
import { NetworkFirewallStack } from '../firewall/firewall_stack';
import { BaseRoutingStack } from '../firewall/base_routing_stack';
import { RoutingStack } from '../firewall/routing_stack';

/**
 * Single multi-region, stage-parameterized entry point for the foundational
 * module. Replaces the two pipeline-based bins. Deploys once per stage via
 * `cdk deploy` — no CodePipeline, no Stage wrappers.
 *
 * VPC and Firewall configs are loaded SEPARATELY (decision A): the firewall
 * config carries identifiers that may originate from a central landing-zone
 * deployment, so it is not merged with the VPC config and is not resolved via
 * Fn.importValue. See the foundational-stack-migration design.
 *
 * The shared Transit Gateway (network/transit_gateway_stack.ts) is a separate
 * create-once deploy in the network account and is intentionally NOT part of
 * this per-region/per-stage loop.
 */
async function main() {
  const app = new cdk.App();
  cdk.Aspects.of(app).add(new AwsSolutionsChecks({ verbose: true }));

  const STAGE = process.env.STAGE;
  if (!STAGE) {
    console.error('Required STAGE environment variable is not defined');
    process.exit(1);
  }

  try {
    // Caller-relative config loads: `../conf` from each base path resolves to
    // foundational/vpc/conf and foundational/firewall/conf respectively. No SSM
    // credentials required for local synth — missing SSM falls back to file.
    const vpcBase = path.join(__dirname, '..', 'vpc', 'bin');
    const fwBase = path.join(__dirname, '..', 'firewall', 'bin');

    const vpcLoaded = await loadDeploymentConfig(vpcBase, STAGE, 'vpc');
    const fwLoaded = await loadDeploymentConfig(fwBase, STAGE, 'firewall');

    if (!vpcLoaded || !fwLoaded) {
      // loadDeploymentConfig already logged and exited on hard failure; this is
      // a defensive guard for the type-narrowing.
      process.exit(1);
    }

    const stage = vpcLoaded.stage;
    const globalConfig = vpcLoaded.globalConfig;
    const vpcConfig = vpcLoaded.vpcConfig as Record<string, any>;
    const fwConfig = fwLoaded.fwConfig as Record<string, any>;
    const globalTags = globalConfig?.pipeline?.tags ?? {};

    if (!globalConfig?.project || !globalConfig?.base) {
      throw new ConfigurationError('Missing required global project/base configuration', [
        { field: 'globalConfig', message: 'project and base are required' },
      ]);
    }

    const namePrefix = `${globalConfig.project.aws_organziation_scope}-${globalConfig.project.project_name}-${globalConfig.project.module_name}`;
    // Foundational deploys stack resources directly (no pipeline), so its target is
    // target_account_id (where stack resources live — the firewall/solution account),
    // NOT resource_account_id (the pipeline account used by the old pipeline bins).
    const account = globalConfig.base.target_account_id;

    // One stack set per region key. The firewall config drives the fabric; the
    // VPC config must supply the same region (Requirement 6.2).
    const regionKeys = Object.keys(fwConfig ?? {});
    if (regionKeys.length === 0) {
      console.error(
        'Foundational configuration contains zero region keys; at least one region must be configured.'
      );
      process.exit(1);
    }

    for (const regionKey of regionKeys) {
      const fwRegion = fwConfig[regionKey];
      const vpcRegion = vpcConfig?.[regionKey];
      if (!vpcRegion) {
        throw new ConfigurationError(
          `Region '${regionKey}' present in firewall config but missing from VPC config`,
          [{ field: `vpcConfig.${regionKey}`, message: 'region missing from VPC config' }]
        );
      }

      const env = { region: regionKey, account };

      const vpc = new VpcStack(app, `vpc-${namePrefix}-${regionKey}-${stage}`, {
        env,
        namePrefix,
        stage,
        vpcCidr: vpcRegion.vpc_cidr,
        cidrMasks: vpcRegion.cidr_masks,
        availabilityZones: vpcRegion.availability_zones,
        globalTags,
      });

      const firewall = new NetworkFirewallStack(
        app,
        `firewall-${namePrefix}-${regionKey}-${stage}`,
        {
          env,
          namePrefix,
          stage,
          vpcId: fwRegion.vpc_id,
          subnetIds: fwRegion.subnet_ids,
          azIds: fwRegion.availability_zones,
          internalNet: fwRegion.internal_network_cidrs,
          ruleOrder: fwRegion.rule_order,
          globalTags,
        }
      );

      const baseRouting = new BaseRoutingStack(
        app,
        `base-routing-${namePrefix}-${regionKey}-${stage}`,
        {
          env,
          namePrefix,
          stage,
          vpcId: fwRegion.vpc_id,
          subnetIds: fwRegion.subnet_ids,
          azIds: fwRegion.availability_zones,
          vpcCidr: fwRegion.vpc_cidr,
          multiAz: fwRegion.multi_az,
          transitGateway: fwRegion.transit_gateway,
          internalNet: fwRegion.internal_network_cidrs,
          globalTags,
        }
      );

      const routing = new RoutingStack(app, `routing-${namePrefix}-${regionKey}-${stage}`, {
        env,
        namePrefix,
        stage,
        vpcId: fwRegion.vpc_id,
        vpcCidr: fwRegion.vpc_cidr,
        subnetIds: fwRegion.subnet_ids,
        azIds: fwRegion.availability_zones,
        multiAz: fwRegion.multi_az,
        transitGateway: fwRegion.transit_gateway,
        internalNet: fwRegion.internal_network_cidrs,
        internetGateway: fwRegion.internet_gateway_id,
        globalTags,
      });

      // Deployment ordering: VPC → Firewall → BaseRouting → Routing.
      firewall.addDependency(vpc);
      baseRouting.addDependency(firewall);
      routing.addDependency(baseRouting);

      // CDK auto-generates a BucketNotificationsHandler (a singleton Lambda) for the
      // flow-logs bucket; its role uses the AWS-managed basic execution role. This is
      // CDK-internal and not customer-controlled. The finding previously ran inside the
      // pipeline stage; with pipelines removed (Requirement 5) it surfaces at direct
      // synth, so we suppress it narrowly here.
      NagSuppressions.addResourceSuppressionsByPath(
        vpc,
        `${vpc.node.path}/BucketNotificationsHandler050a0587b7544547bf325f094a3db834/Role/Resource`,
        [
          {
            id: 'AwsSolutions-IAM4',
            reason:
              'CDK-managed S3 bucket-notifications handler uses the AWS-managed basic execution role; not customer-controlled.',
            appliesTo: [
              'Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole',
            ],
          },
        ]
      );
    }

    console.log(
      `✅ Foundational stacks synthesized for stage '${stage}' across regions: ${regionKeys.join(', ')}`
    );

    app.synth();
  } catch (error) {
    if (error instanceof ConfigurationError) {
      console.error('❌ Configuration Error:');
      console.error(error.getDetailedMessage());
      console.error('\n💡 Troubleshooting:');
      console.error(`   - Check that configuration exists for stage '${STAGE}'`);
      console.error(`   - SSM: /anfw-automate/${STAGE}/vpc/config and /anfw-automate/${STAGE}/firewall/config`);
      console.error(`   - Or files: foundational/vpc/conf/${STAGE}.json and foundational/firewall/conf/${STAGE}.json`);
    } else {
      console.error('❌ Unexpected error:', error);
    }
    process.exit(1);
  }
}

main().catch(error => {
  console.error('Error in main:', error);
  process.exit(1);
});
