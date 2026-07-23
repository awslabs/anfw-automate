import { CfnOutput, Duration, RemovalPolicy, Stack, StackProps } from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as events from 'aws-cdk-lib/aws-events';
import * as sqs from 'aws-cdk-lib/aws-sqs';
import * as logs from 'aws-cdk-lib/aws-logs';
import { Construct } from 'constructs';

export interface DummyTenantStackProps extends StackProps {
  /** Resource naming prefix (matches the app deployment, e.g. "anfw"). */
  readonly namePrefix: string;
  /** Deployment stage (e.g. "int"). */
  readonly stage: string;
  /**
   * The central (firewall/automation) account id. In single-account INT this
   * equals the current account. Used for the cross-account role trust policy
   * and the central event bus target.
   */
  readonly centralAccountId: string;
  /**
   * ARN of the central EventBridge bus created by the app ServerlessStack
   * (export `central-eventbus-arn-<stage>`). Spoke event rules forward here.
   */
  readonly centralEventBusArn: string;
  /** Name/id of the central event bus (last path segment of the ARN). */
  readonly centralEventBusId: string;
  /**
   * The shared Transit Gateway id that the inspection VPC is also attached to.
   * The dummy tenant's workload VPC attaches here so RuleCollect's
   * `_is_vpc_attached_to_transit_gateway` check passes.
   */
  readonly transitGatewayId: string;
  /** CIDR for the dummy tenant workload VPC. */
  readonly vpcCidr?: string;
}

/**
 * DummyTenantStack — a prod-representative tenant/spoke fixture for INT tests.
 *
 * Replicates exactly what `app/templates/spoke-serverless-stack.yaml` deploys
 * into a real spoke account via StackSet:
 *   - S3 config bucket (anfw-allowlist-<region>-<account>-<stage>)
 *   - Cross-account role the central Lambdas assume to read the bucket
 *   - EventBridge role + rules forwarding S3/VPC-delete events to the central bus
 *   - DLQ for failed event delivery
 *   - Customer log group
 *
 * PLUS the piece a real spoke account already has (not in the StackSet):
 *   - A workload VPC attached to the shared Transit Gateway
 *
 * This makes the INT flow a genuine tenant onboarding: the tenant uploads its
 * own region-config.yaml, the central automation reads it (cross-account role),
 * verifies the tenant VPC is TGW-attached, and materializes rules in the
 * central Network Firewall.
 */
export class DummyTenantStack extends Stack {
  public readonly workloadVpc: ec2.Vpc;
  public readonly tgwAttachment: ec2.CfnTransitGatewayAttachment;
  public readonly configBucket: s3.Bucket;

  constructor(scope: Construct, id: string, props: DummyTenantStackProps) {
    super(scope, id, props);

    const { namePrefix, stage, centralAccountId, centralEventBusArn, centralEventBusId, transitGatewayId } = props;
    const namedotprefix = namePrefix.replace(/-/g, '.');
    const region = Stack.of(this).region;

    // -------------------------------------------------------------------------
    // Workload VPC + Transit Gateway attachment
    // A real spoke account already has this; for single-account INT we create a
    // dedicated workload VPC and attach it to the shared TGW so the tenant's
    // VPC passes the TGW-attachment check in RuleCollect.
    // -------------------------------------------------------------------------
    this.workloadVpc = new ec2.Vpc(this, 'TenantWorkloadVpc', {
      vpcName: `${namePrefix}-tenant-vpc-${stage}`,
      ipAddresses: ec2.IpAddresses.cidr(props.vpcCidr ?? '10.20.0.0/24'),
      maxAzs: 2,
      natGateways: 0,
      subnetConfiguration: [
        { cidrMask: 26, name: 'Workload', subnetType: ec2.SubnetType.PRIVATE_ISOLATED },
      ],
    });

    this.tgwAttachment = new ec2.CfnTransitGatewayAttachment(this, 'TenantTgwAttachment', {
      transitGatewayId: transitGatewayId,
      vpcId: this.workloadVpc.vpcId,
      subnetIds: this.workloadVpc.isolatedSubnets.map((s) => s.subnetId),
      tags: [{ key: 'Name', value: `${namePrefix}-tenant-tgw-attachment-${stage}` }],
    });

    // -------------------------------------------------------------------------
    // S3 Config Bucket (mirrors spoke-serverless-stack.yaml ConfigBucket)
    // -------------------------------------------------------------------------
    this.configBucket = new s3.Bucket(this, 'ConfigBucket', {
      bucketName: `anfw-allowlist-${region}-${centralAccountId}-${stage}`,
      versioned: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      enforceSSL: true,
      eventBridgeEnabled: true,
      removalPolicy: RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    // -------------------------------------------------------------------------
    // Cross-account role the central Lambdas assume (mirrors CrossTargetAccountRole)
    // In single-account INT, centralAccountId == this account, so this is a
    // same-account assume-role — exercising the identical code path as prod.
    // -------------------------------------------------------------------------
    const crossAccountRole = new iam.Role(this, 'CrossTargetAccountRole', {
      roleName: `rle.${namedotprefix}.xaccount.lmb.${region}.${stage}`,
      assumedBy: new iam.AccountPrincipal(centralAccountId),
      path: '/',
    });
    crossAccountRole.addToPolicy(
      new iam.PolicyStatement({
        sid: 'ValidationPerms',
        effect: iam.Effect.ALLOW,
        actions: ['s3:Get*', 's3:List*', 's3:PutBucketNotification'],
        resources: [this.configBucket.bucketArn, `${this.configBucket.bucketArn}/*`],
      })
    );
    crossAccountRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          'ec2:DescribeVpcs',
          'ec2:DescribeVpcAttribute',
          'ec2:DescribeTransitGatewayAttachments',
        ],
        resources: ['*'],
      })
    );
    crossAccountRole.addToPolicy(
      new iam.PolicyStatement({
        sid: 'LoggerPerms',
        effect: iam.Effect.ALLOW,
        actions: [
          'logs:Describe*',
          'logs:List*',
          'logs:GetLogEvents',
          'logs:CreateLogGroup',
          'logs:CreateExportTask',
          'logs:CreateLogStream',
          'logs:PutLogEvents',
        ],
        resources: ['*'],
      })
    );

    // -------------------------------------------------------------------------
    // EventBridge role that forwards spoke events to the central bus
    // (mirrors EventBridgeIAMrole)
    // -------------------------------------------------------------------------
    const eventBridgeRole = new iam.Role(this, 'EventBridgeIAMrole', {
      roleName: `rle.${namedotprefix}.eb.${region}.${stage}`,
      assumedBy: new iam.ServicePrincipal('events.amazonaws.com'),
      path: '/',
    });
    eventBridgeRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: ['events:PutEvents'],
        resources: [centralEventBusArn],
      })
    );

    // -------------------------------------------------------------------------
    // DLQ for failed event delivery (mirrors EBDLQueue)
    // -------------------------------------------------------------------------
    const dlq = new sqs.Queue(this, 'EBDLQueue', {
      queueName: `dlq-${namePrefix}-ConfigEventBus-${stage}`,
      enforceSSL: true,
    });

    // Helper to build a rule that forwards to the central bus with DLQ.
    const centralTarget = {
      arn: centralEventBusArn,
      role: eventBridgeRole,
      deadLetterQueue: dlq,
    };

    // S3 object events (created/deleted/restore) for THIS tenant's config bucket
    const s3ObjectRule = new events.Rule(this, 'S3ObjectEventRule', {
      ruleName: `DoNotDelete-S3ObjectRule-${namePrefix}-${stage}`,
      description: 'Routes S3 object events to the central event bus',
      eventPattern: {
        source: ['aws.s3'],
        detailType: [
          'Object Created',
          'Object Deleted',
          'Object Restore Completed',
          'Object Restore Expired',
          'Object Restore Initiated',
        ],
        detail: { bucket: { name: [this.configBucket.bucketName] } },
      },
    });

    // S3 bucket delete for THIS tenant's config bucket
    const s3BucketRule = new events.Rule(this, 'S3BucketEventRule', {
      ruleName: `DoNotDelete-S3BucketRule-${namePrefix}-${stage}`,
      description: 'Routes S3 bucket delete to the central event bus',
      eventPattern: {
        source: ['aws.s3'],
        detailType: ['AWS API Call via CloudTrail'],
        detail: {
          eventSource: ['s3.amazonaws.com'],
          eventName: ['DeleteBucket'],
          requestParameters: { bucketName: [this.configBucket.bucketName] },
        },
      },
    });

    // VPC delete (any VPC in this account) → central bus
    const vpcDeleteRule = new events.Rule(this, 'VPCDeleteEventRule', {
      ruleName: `DoNotDelete-VPCDeleteRule-${namePrefix}-${stage}`,
      description: 'Routes VPC delete events to the central event bus',
      eventPattern: {
        source: ['aws.ec2'],
        detailType: ['AWS API Call via CloudTrail'],
        detail: {
          eventSource: ['ec2.amazonaws.com'],
          eventName: ['DeleteVpc'],
        },
      },
    });

    // CDK's CfnRule target for a cross-bus forward with a role + DLQ.
    for (const [logicalId, rule] of [
      ['S3ObjectTarget', s3ObjectRule],
      ['S3BucketTarget', s3BucketRule],
      ['VPCDeleteTarget', vpcDeleteRule],
    ] as [string, events.Rule][]) {
      const cfnRule = rule.node.defaultChild as events.CfnRule;
      cfnRule.targets = [
        {
          arn: centralTarget.arn,
          id: centralEventBusId,
          roleArn: eventBridgeRole.roleArn,
          deadLetterConfig: { arn: dlq.queueArn },
        },
      ];
    }

    // Allow EventBridge rules to send to the DLQ
    dlq.addToResourcePolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        principals: [new iam.ServicePrincipal('events.amazonaws.com')],
        actions: ['sqs:SendMessage'],
        resources: [dlq.queueArn],
        conditions: {
          'ForAnyValue:ArnEquals': {
            'aws:SourceArn': [s3ObjectRule.ruleArn, s3BucketRule.ruleArn, vpcDeleteRule.ruleArn],
          },
        },
      })
    );

    // -------------------------------------------------------------------------
    // Customer log group (mirrors CustomerLogGroup)
    // -------------------------------------------------------------------------
    new logs.LogGroup(this, 'CustomerLogGroup', {
      logGroupName: `cw-${namePrefix}-CustomerLog-${stage}`,
      retention: logs.RetentionDays.ONE_WEEK,
      removalPolicy: RemovalPolicy.DESTROY,
    });

    // -------------------------------------------------------------------------
    // Outputs — consumed by the integration conftest to resolve the tenant.
    // -------------------------------------------------------------------------
    new CfnOutput(this, 'TenantVpcId', {
      value: this.workloadVpc.vpcId,
      description: 'Dummy tenant workload VPC id (TGW-attached)',
      exportName: `${namePrefix}-tenant-vpc-id-${stage}`,
    });
    new CfnOutput(this, 'TenantConfigBucketName', {
      value: this.configBucket.bucketName,
      description: 'Dummy tenant S3 config bucket name',
      exportName: `${namePrefix}-tenant-config-bucket-${stage}`,
    });
    new CfnOutput(this, 'TenantTgwAttachmentId', {
      value: this.tgwAttachment.attrId,
      description: 'Dummy tenant TGW attachment id',
      exportName: `${namePrefix}-tenant-tgw-attachment-${stage}`,
    });
  }
}
