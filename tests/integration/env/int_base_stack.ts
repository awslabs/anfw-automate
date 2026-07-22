import { CfnOutput, RemovalPolicy, Stack, StackProps } from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as networkfirewall from 'aws-cdk-lib/aws-networkfirewall';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import { Construct } from 'constructs';

export interface IntBaseStackProps extends StackProps {
  /**
   * The name prefix used consistently across the project.
   * @default 'anfw'
   */
  readonly namePrefix?: string;

  /**
   * The account IDs allowed to assume the cross-account role.
   * These are the accounts where the Lambdas (RuleCollect/RuleExecute) run.
   */
  readonly trustedAccountIds?: string[];
}

/**
 * IntBaseStack — Long-lived CDK stack for integration test prerequisites.
 *
 * Deployed once to the INT account and kept warm. Never destroyed/recreated per
 * test run. Provides:
 * - A VPC attached to a Transit Gateway (RuleCollect skips VPCs not attached to a TGW)
 * - A Network Firewall policy ARN to associate rule groups with
 * - An S3 config bucket with EventBridge notifications enabled
 * - A cross-account role the Lambdas assume
 *
 * All handles are exposed as CloudFormation outputs for StableEnvResolver to read.
 */
export class IntBaseStack extends Stack {
  public readonly vpc: ec2.Vpc;
  public readonly transitGatewayAttachment: ec2.CfnTransitGatewayAttachment;
  public readonly firewallPolicy: networkfirewall.CfnFirewallPolicy;
  public readonly configBucket: s3.Bucket;
  public readonly crossAccountRole: iam.Role;
  public readonly eventBus: events.EventBus;

  constructor(scope: Construct, id: string, props: IntBaseStackProps = {}) {
    super(scope, id, props);

    const namePrefix = props.namePrefix ?? 'anfw';
    const trustedAccountIds = props.trustedAccountIds ?? [Stack.of(this).account];

    // -------------------------------------------------------------------------
    // VPC with public/private subnets (for TGW attachment)
    // -------------------------------------------------------------------------
    this.vpc = new ec2.Vpc(this, 'IntVpc', {
      vpcName: `${namePrefix}-int-vpc`,
      maxAzs: 2,
      subnetConfiguration: [
        {
          cidrMask: 24,
          name: 'Public',
          subnetType: ec2.SubnetType.PUBLIC,
        },
        {
          cidrMask: 24,
          name: 'Private',
          subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
        },
      ],
    });

    // -------------------------------------------------------------------------
    // Transit Gateway + VPC Attachment
    // RuleCollect skips VPCs not attached to a TGW, so this is required.
    // -------------------------------------------------------------------------
    const transitGateway = new ec2.CfnTransitGateway(this, 'IntTransitGateway', {
      description: `${namePrefix}-int-tgw`,
      defaultRouteTableAssociation: 'enable',
      defaultRouteTablePropagation: 'enable',
      tags: [{ key: 'Name', value: `${namePrefix}-int-tgw` }],
    });

    this.transitGatewayAttachment = new ec2.CfnTransitGatewayAttachment(
      this,
      'IntTgwAttachment',
      {
        transitGatewayId: transitGateway.ref,
        vpcId: this.vpc.vpcId,
        subnetIds: this.vpc.privateSubnets.map((subnet) => subnet.subnetId),
        tags: [{ key: 'Name', value: `${namePrefix}-int-tgw-attachment` }],
      }
    );

    // -------------------------------------------------------------------------
    // Network Firewall Policy (stateful)
    // -------------------------------------------------------------------------
    this.firewallPolicy = new networkfirewall.CfnFirewallPolicy(
      this,
      'IntFirewallPolicy',
      {
        firewallPolicyName: `${namePrefix}-int-firewall-policy`,
        firewallPolicy: {
          statelessDefaultActions: ['aws:forward_to_sfe'],
          statelessFragmentDefaultActions: ['aws:forward_to_sfe'],
          statefulEngineOptions: {
            ruleOrder: 'STRICT_ORDER',
          },
          statefulDefaultActions: ['aws:drop_strict', 'aws:alert_strict'],
        },
        tags: [{ key: 'Name', value: `${namePrefix}-int-firewall-policy` }],
      }
    );

    // -------------------------------------------------------------------------
    // S3 Config Bucket with EventBridge notifications
    // -------------------------------------------------------------------------
    this.configBucket = new s3.Bucket(this, 'IntConfigBucket', {
      bucketName: `${namePrefix}-int-config-${Stack.of(this).account}-${Stack.of(this).region}`,
      eventBridgeEnabled: true,
      removalPolicy: RemovalPolicy.RETAIN,
      versioned: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      enforceSSL: true,
    });

    // -------------------------------------------------------------------------
    // EventBridge Bus for config events
    // -------------------------------------------------------------------------
    this.eventBus = new events.EventBus(this, 'IntConfigEventBus', {
      eventBusName: `${namePrefix}-int-ConfigEventBus`,
    });

    // EventBridge rule to forward S3 object events to the event bus
    new events.Rule(this, 'IntS3EventRule', {
      eventBus: events.EventBus.fromEventBusArn(
        this,
        'DefaultBus',
        `arn:aws:events:${Stack.of(this).region}:${Stack.of(this).account}:event-bus/default`
      ),
      ruleName: `${namePrefix}-int-s3-config-event`,
      eventPattern: {
        source: ['aws.s3'],
        detailType: ['Object Created', 'Object Deleted'],
        detail: {
          bucket: {
            name: [this.configBucket.bucketName],
          },
        },
      },
      targets: [new targets.EventBus(this.eventBus)],
    });

    // -------------------------------------------------------------------------
    // Cross-account IAM Role
    // -------------------------------------------------------------------------
    this.crossAccountRole = new iam.Role(this, 'IntXAccountRole', {
      roleName: `rle.${namePrefix.replace(/-/g, '.')}.xaccount.lmb.${Stack.of(this).region}.int`,
      assumedBy: new iam.CompositePrincipal(
        ...trustedAccountIds.map(
          (accountId) => new iam.AccountPrincipal(accountId)
        )
      ),
      description:
        'Cross-account role assumed by RuleCollect/RuleExecute Lambdas during INT tests',
    });

    // Grant the cross-account role permissions to read from the config bucket
    this.configBucket.grantRead(this.crossAccountRole);

    // Grant the cross-account role permissions to describe EC2/VPC resources
    this.crossAccountRole.addToPolicy(
      new iam.PolicyStatement({
        sid: 'DescribeVpcResources',
        effect: iam.Effect.ALLOW,
        actions: [
          'ec2:DescribeVpcs',
          'ec2:DescribeTransitGatewayAttachments',
          'ec2:DescribeTransitGatewayVpcAttachments',
        ],
        resources: ['*'],
      })
    );

    // -------------------------------------------------------------------------
    // CloudFormation Outputs — handles for StableEnvResolver
    // -------------------------------------------------------------------------
    new CfnOutput(this, 'IntVpcId', {
      description: 'VPC ID of the TGW-attached INT VPC',
      value: this.vpc.vpcId,
      exportName: `${namePrefix}-int-vpc-id`,
    });

    new CfnOutput(this, 'IntFirewallPolicyArn', {
      description: 'ARN of the INT Network Firewall policy',
      value: this.firewallPolicy.attrFirewallPolicyArn,
      exportName: `${namePrefix}-int-firewall-policy-arn`,
    });

    new CfnOutput(this, 'IntConfigBucketName', {
      description: 'Name of the INT S3 config bucket',
      value: this.configBucket.bucketName,
      exportName: `${namePrefix}-int-config-bucket-name`,
    });

    new CfnOutput(this, 'IntConfigBucketArn', {
      description: 'ARN of the INT S3 config bucket',
      value: this.configBucket.bucketArn,
      exportName: `${namePrefix}-int-config-bucket-arn`,
    });

    new CfnOutput(this, 'IntXAccountRoleArn', {
      description: 'ARN of the cross-account role for Lambda assumption',
      value: this.crossAccountRole.roleArn,
      exportName: `${namePrefix}-int-xaccount-role-arn`,
    });

    new CfnOutput(this, 'IntEventBusArn', {
      description: 'ARN of the INT EventBridge event bus',
      value: this.eventBus.eventBusArn,
      exportName: `${namePrefix}-int-event-bus-arn`,
    });
  }
}
