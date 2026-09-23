import { CfnOutput, Duration, RemovalPolicy, Stack, StackProps } from 'aws-cdk-lib';
import * as path from 'path';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as events from 'aws-cdk-lib/aws-events';
import * as sqs from 'aws-cdk-lib/aws-sqs';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';

export interface IntBaseStackProps extends StackProps {
  /** Resource naming prefix (matches the app deployment, e.g. "anfw"). */
  readonly namePrefix?: string;
  /** Deployment stage. Defaults to "int". */
  readonly stage?: string;
  /**
   * The central (firewall/automation) account id that runs RuleCollect/RuleExecute.
   * In single-account INT this equals the current account. Used for the tenant
   * cross-account role trust and the central event bus target.
   */
  readonly centralAccountId?: string;
}

/**
 * IntBaseStack — consolidated, prod-representative INT environment (single account).
 *
 * Models the full centralized ANFW + TGW topology in one stack:
 *
 *   Shared Transit Gateway (hub) — created once by the foundational
 *   TransitGatewayStack (network account) and RAM-shared here; resolved from
 *   SSM `/anfw-automate/shared/tgw-id`. NOT created by this stack.
 *    ├─ Inspection side: the int-stage foundational Network Firewall + policy
 *    │   (firewall account). This stack does NOT create a firewall/policy; it
 *    │   resolves the policy ARN from SSM so rule groups attach to the REAL
 *    │   foundational policy that probe traffic is actually inspected by.
 *    └─ Dummy tenant (mirrors spoke-serverless-stack.yaml + the VPC a real spoke
 *        account already has):
 *          - Workload VPC attached to the shared TGW (passes RuleCollect's
 *            _is_vpc_attached_to_transit_gateway check), egress 0.0.0.0/0 → TGW
 *          - Reachability probe Lambda in the isolated subnets (data-plane
 *            enforcement assertion channel)
 *          - S3 config bucket (anfw-allowlist-<region>-<account>-<stage>)
 *          - Cross-account role the central Lambdas assume to read the bucket
 *          - EventBridge role + rules forwarding S3/VPC-delete events to the
 *            central bus (ARN derived by naming convention — no deploy ordering
 *            dependency on the app pipeline)
 *          - DLQ + customer log group
 *
 * All handles are exposed as CloudFormation exports and resolved at runtime by
 * the integration conftest (StableEnvResolver). Deployed once, kept warm.
 */
export class IntBaseStack extends Stack {
  public readonly tenantVpc: ec2.Vpc;
  public readonly tgwAttachment: ec2.CfnTransitGatewayAttachment;
  public readonly configBucket: s3.Bucket;
  public readonly crossAccountRole: iam.Role;
  public readonly probeFunction: lambda.Function;

  constructor(scope: Construct, id: string, props: IntBaseStackProps = {}) {
    super(scope, id, props);

    const namePrefix = props.namePrefix ?? 'anfw';
    const stage = props.stage ?? 'int';
    const namedotprefix = namePrefix.replace(/-/g, '.');
    const account = Stack.of(this).account;
    const region = Stack.of(this).region;
    const centralAccountId = props.centralAccountId ?? account;

    // Central event bus ARN, derived by naming convention from the app's
    // ServerlessStack (`eb-<prefix>-ConfigEventBus-<stage>`). Deriving it avoids
    // a hard deploy-ordering dependency between this stack and the app pipeline.
    const centralEventBusName = `eb-${namePrefix}-ConfigEventBus-${stage}`;
    const centralEventBusArn = `arn:aws:events:${region}:${centralAccountId}:event-bus/${centralEventBusName}`;

    // -------------------------------------------------------------------------
    // Shared Transit Gateway (hub) — resolved from SSM.
    //
    // The TGW is a shared-once, foundational-owned resource created by the
    // network-account TransitGatewayStack and RAM-shared into this account. Its
    // id is published to `/anfw-automate/shared/tgw-id`. We read it here rather
    // than creating a TGW (the INT env no longer owns the hub).
    // -------------------------------------------------------------------------
    const sharedTgwId = ssm.StringParameter.valueForStringParameter(
      this,
      '/anfw-automate/shared/tgw-id'
    );

    // -------------------------------------------------------------------------
    // Dummy tenant workload VPC + TGW attachment.
    //
    // The tenant VPC has NO NAT/IGW of its own. All egress is steered to the
    // shared TGW, which routes to the int-stage foundational Network Firewall
    // for inspection/enforcement. This is what makes probe reachability reflect
    // real NFW enforcement (full fidelity).
    // -------------------------------------------------------------------------
    this.tenantVpc = new ec2.Vpc(this, 'TenantWorkloadVpc', {
      vpcName: `${namePrefix}-tenant-vpc-${stage}`,
      ipAddresses: ec2.IpAddresses.cidr('10.20.0.0/24'),
      maxAzs: 2,
      natGateways: 0,
      subnetConfiguration: [
        { cidrMask: 26, name: 'Workload', subnetType: ec2.SubnetType.PRIVATE_ISOLATED },
      ],
    });

    this.tgwAttachment = new ec2.CfnTransitGatewayAttachment(this, 'TenantTgwAttachment', {
      transitGatewayId: sharedTgwId,
      vpcId: this.tenantVpc.vpcId,
      subnetIds: this.tenantVpc.isolatedSubnets.map(s => s.subnetId),
      tags: [{ key: 'Name', value: `${namePrefix}-tenant-tgw-attachment-${stage}` }],
    });

    // -------------------------------------------------------------------------
    // Tenant egress routing: default route → shared TGW.
    //
    // Each isolated workload subnet's route table gets 0.0.0.0/0 → TGW so that
    // outbound traffic from the probe Lambda is carried to the central
    // inspection side (foundational firewall). Return routing on the firewall
    // side is owned by the foundational RoutingStack.
    // -------------------------------------------------------------------------
    this.tenantVpc.isolatedSubnets.forEach((subnet, idx) => {
      const route = new ec2.CfnRoute(this, `TenantEgressRoute${idx}`, {
        routeTableId: subnet.routeTable.routeTableId,
        destinationCidrBlock: '0.0.0.0/0',
        transitGatewayId: sharedTgwId,
      });
      // The route cannot be created until the VPC is attached to the TGW.
      route.addDependency(this.tgwAttachment);
    });

    // -------------------------------------------------------------------------
    // Tenant S3 config bucket (mirrors spoke-serverless-stack.yaml ConfigBucket)
    // -------------------------------------------------------------------------
    this.configBucket = new s3.Bucket(this, 'ConfigBucket', {
      bucketName: `anfw-allowlist-${region}-${account}-${stage}`,
      versioned: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      enforceSSL: true,
      eventBridgeEnabled: true,
      removalPolicy: RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    // -------------------------------------------------------------------------
    // Cross-account role the central Lambdas assume (mirrors CrossTargetAccountRole).
    // Single-account INT → same-account assume-role, identical code path to prod.
    // -------------------------------------------------------------------------
    this.crossAccountRole = new iam.Role(this, 'CrossTargetAccountRole', {
      roleName: `rle.${namedotprefix}.xaccount.lmb.${region}.${stage}`,
      assumedBy: new iam.AccountPrincipal(centralAccountId),
      path: '/',
    });
    this.crossAccountRole.addToPolicy(
      new iam.PolicyStatement({
        sid: 'ValidationPerms',
        effect: iam.Effect.ALLOW,
        actions: ['s3:Get*', 's3:List*', 's3:PutBucketNotification'],
        resources: [this.configBucket.bucketArn, `${this.configBucket.bucketArn}/*`],
      })
    );
    this.crossAccountRole.addToPolicy(
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
    this.crossAccountRole.addToPolicy(
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
    // EventBridge forwarding role + rules (spoke default bus → central bus)
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

    const dlq = new sqs.Queue(this, 'EBDLQueue', {
      queueName: `dlq-${namePrefix}-ConfigEventBus-${stage}`,
      enforceSSL: true,
    });

    const s3ObjectRule = new events.Rule(this, 'S3ObjectEventRule', {
      ruleName: `DoNotDelete-S3ObjectRule-${namePrefix}-${stage}`,
      description: 'Routes tenant S3 object events to the central event bus',
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
    const s3BucketRule = new events.Rule(this, 'S3BucketEventRule', {
      ruleName: `DoNotDelete-S3BucketRule-${namePrefix}-${stage}`,
      description: 'Routes tenant S3 bucket delete to the central event bus',
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
    const vpcDeleteRule = new events.Rule(this, 'VPCDeleteEventRule', {
      ruleName: `DoNotDelete-VPCDeleteRule-${namePrefix}-${stage}`,
      description: 'Routes VPC delete events to the central event bus',
      eventPattern: {
        source: ['aws.ec2'],
        detailType: ['AWS API Call via CloudTrail'],
        detail: { eventSource: ['ec2.amazonaws.com'], eventName: ['DeleteVpc'] },
      },
    });

    for (const rule of [s3ObjectRule, s3BucketRule, vpcDeleteRule]) {
      const cfnRule = rule.node.defaultChild as events.CfnRule;
      cfnRule.targets = [
        {
          arn: centralEventBusArn,
          id: centralEventBusName,
          roleArn: eventBridgeRole.roleArn,
          deadLetterConfig: { arn: dlq.queueArn },
        },
      ];
    }

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

    new logs.LogGroup(this, 'CustomerLogGroup', {
      logGroupName: `cw-${namePrefix}-CustomerLog-${stage}`,
      retention: logs.RetentionDays.ONE_WEEK,
      removalPolicy: RemovalPolicy.DESTROY,
    });

    // -------------------------------------------------------------------------
    // Reachability probe Lambda — deployed IN the tenant VPC's isolated subnets.
    //
    // The integration ReachabilityChecker invokes this to attempt a TCP connect
    // to a domain:port. Because the tenant VPC's only egress is 0.0.0.0/0 → TGW
    // → foundational Network Firewall, a successful connect proves the NFW rules
    // allow the traffic, and a failed connect proves default-deny/drop. This is
    // the data-plane (full-fidelity) assertion channel.
    //
    // The function name is exported so the harness can invoke it by name.
    // -------------------------------------------------------------------------
    this.probeFunction = new lambda.Function(this, 'ReachabilityProbe', {
      functionName: `lmb-${namePrefix}-int-probe-${stage}`,
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'index.handler',
      code: lambda.Code.fromAsset(path.join(__dirname, 'probe_lambda')),
      timeout: Duration.seconds(30),
      vpc: this.tenantVpc,
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_ISOLATED },
      description:
        'INT reachability probe: TCP connect from the tenant VPC through the ' +
        'foundational NFW to assert allow/deny enforcement.',
    });

    // -------------------------------------------------------------------------
    // CloudFormation exports — resolved at runtime by StableEnvResolver.
    // -------------------------------------------------------------------------
    new CfnOutput(this, 'IntTransitGatewayId', {
      value: sharedTgwId,
      description: 'Shared Transit Gateway id (resolved from SSM /anfw-automate/shared/tgw-id)',
      exportName: `${namePrefix}-int-tgw-id-${stage}`,
    });
    new CfnOutput(this, 'IntTenantVpcId', {
      value: this.tenantVpc.vpcId,
      description: 'Dummy tenant workload VPC id (TGW-attached)',
      exportName: `${namePrefix}-int-tenant-vpc-id-${stage}`,
    });
    new CfnOutput(this, 'IntFirewallPolicyArn', {
      // Resolved from the int-stage foundational fabric (firewall account) via
      // the shared SSM parameter it publishes. The INT env no longer creates a
      // standalone/fake firewall policy — rule groups attach to the real
      // foundational policy that the probe traffic is actually inspected by.
      value: ssm.StringParameter.valueForStringParameter(
        this,
        `/anfw-automate/${stage}/foundational/firewall-policy-arn`
      ),
      description: 'Int-stage foundational Network Firewall policy ARN (from SSM)',
      exportName: `${namePrefix}-int-firewall-policy-arn-${stage}`,
    });
    new CfnOutput(this, 'IntProbeFunctionName', {
      value: this.probeFunction.functionName,
      description: 'Reachability probe Lambda function name (invoked by the harness)',
      exportName: `${namePrefix}-int-probe-function-name-${stage}`,
    });
    new CfnOutput(this, 'IntConfigBucketName', {
      value: this.configBucket.bucketName,
      description: 'Tenant S3 config bucket name',
      exportName: `${namePrefix}-int-config-bucket-name-${stage}`,
    });
    new CfnOutput(this, 'IntXAccountRoleArn', {
      value: this.crossAccountRole.roleArn,
      description: 'Cross-account role ARN assumed by the central Lambdas',
      exportName: `${namePrefix}-int-xaccount-role-arn-${stage}`,
    });
    new CfnOutput(this, 'IntCentralEventBusArn', {
      value: centralEventBusArn,
      description: 'Central event bus ARN (by convention) the tenant forwards to',
      exportName: `${namePrefix}-int-event-bus-arn-${stage}`,
    });
  }
}
