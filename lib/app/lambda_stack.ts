import { CfnOutput, Duration, RemovalPolicy, Stack, StackProps, aws_cloudwatch_actions } from 'aws-cdk-lib';
import * as sqs from 'aws-cdk-lib/aws-sqs';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import { Construct } from "constructs";
import { SqsEventSource } from 'aws-cdk-lib/aws-lambda-event-sources';
import * as pylambda from "@aws-cdk/aws-lambda-python-alpha";

export class LambdaStack extends Stack {
    constructor(scope: Construct, id: string, props: {
        namePrefix: string;
        vpcId: string;
        // vpcCidr: string;
        // internalNet: string;
        supportedRegions: [string];
        policyArns: { [key: string]: string[] };
        stage: string;
    }) {
        super(scope, id);

        const namedotprefix = props.namePrefix.replace(/-/g, ".");

        // Create DeadLetter SQS Queue
        const ruleSqsDlqQueue = new sqs.Queue(this, 'RuleSQSDLQueue', {
            queueName: `dlq-${props.namePrefix}-${props.stage}-LambdaSQS.fifo`,
            fifo: true,
            retentionPeriod: Duration.seconds(1209600)
        });

        ruleSqsDlqQueue.addToResourcePolicy(
            new iam.PolicyStatement({
                sid: "ReadWriteSameAccount",
                effect: iam.Effect.ALLOW,
                actions: ['sqs:SendMessage', 'sqs:ReceiveMessage'],
                resources: [`${ruleSqsDlqQueue.queueArn}`],
                principals: [new iam.AccountRootPrincipal]
            })
        );

        const ruleDlqQueue: sqs.DeadLetterQueue = {
            maxReceiveCount: 123,
            queue: ruleSqsDlqQueue,
        };

        // Create SQS Queues
        const ruleSqsQueue = new sqs.Queue(this, 'RuleSQSQueue', {
            queueName: `sqs-${props.namePrefix}-${props.stage}-LambdaSQS.fifo`,
            contentBasedDeduplication: true,
            deliveryDelay: Duration.seconds(0),
            fifo: true,
            maxMessageSizeBytes: 262144,
            visibilityTimeout: Duration.seconds(300),
            deadLetterQueue: ruleDlqQueue
        });

        // Create Lambda Functions
        const lambdaLayer = new pylambda.PythonLayerVersion(this, 'LamdaDependencyLayer', {
            layerVersionName: `lyr-${props.namePrefix}-layer-${props.stage}`,
            entry: 'app',
            compatibleRuntimes: [lambda.Runtime.PYTHON_3_11],
            bundling: {
                assetExcludes: ['.*', 'RuleCollect/', 'RuleExecute/', 'tests/', 'data/', 'lib/'],
            }
        });

        // RuleCollect Function
        const ruleCollectLambda = new lambda.Function(this, 'RuleCollectLambda', {
            runtime: lambda.Runtime.PYTHON_3_11,
            handler: 'collect_lambda.handler',
            code: lambda.Code.fromAsset('dist/RuleCollect'),
            environment: {
                QUEUE_NAME: `${ruleSqsQueue.queueName}`,
                LAMBDA_REGION: `${this.region}`,
                LOG_LEVEL: "DEBUG",
                XACCOUNT_ROLE: `rle.${namedotprefix}.xaccount.lmb.${this.region}.${props.stage}`,
                ENVIRONMENT: `${props.stage}`,
                POWERTOOLS_SERVICE_NAME: "RuleCollectLambda",
                NAME_PREFIX: `${props.namePrefix}`,
                STAGE: `${props.stage}`

            },
            memorySize: 256,
            timeout: Duration.seconds(30),
            tracing: lambda.Tracing.ACTIVE,
            logRetention: logs.RetentionDays.THREE_MONTHS,
            layers: [lambdaLayer]
        });

        const ruleExecuteLambda = new lambda.Function(this, 'RuleExecuteLambda', {
            runtime: lambda.Runtime.PYTHON_3_11,
            handler: 'execute_lambda.handler',
            code: lambda.Code.fromAsset('dist/RuleExecute'),
            environment: {
                QUEUE_NAME: `${ruleSqsQueue.queueName}`,
                LOG_LEVEL: "DEBUG",
                // HOME_NET: `${props.vpcCidr}`,
                // INTERNAL_NET: `${props.internalNet}`,
                POWERTOOLS_SERVICE_NAME: "RuleExecuteLambda",
                XACCOUNT_ROLE: `rle.${namedotprefix}.xaccount.lmb.${this.region}.${props.stage}`,
                SUPPORTED_REGIONS: `${props.supportedRegions.toString()}`,
                POLICY_ARNS: `${props.policyArns}`,
                VPC_ID: `${props.vpcId}`,
                NAME_PREFIX: `${props.namePrefix}`,
                STAGE: `${props.stage}`
            },
            timeout: Duration.seconds(30),
            tracing: lambda.Tracing.ACTIVE,
            logRetention: logs.RetentionDays.THREE_MONTHS,
            layers: [lambdaLayer]
        });

        // Create Lambda Event Source Mapping
        ruleExecuteLambda.addEventSource(new SqsEventSource(ruleSqsQueue));

        // read only permissions for lambda functions
        const readOnlyPolicy = new iam.PolicyStatement({
            sid: "ReadOnlyPermissions",
            effect: iam.Effect.ALLOW,
            actions: [
                'xray:Get*',
                'xray:List*',
                'xray:BatchGet*',
                'logs:Describe*',
                'logs:List*',
                'logs:GetLogEvents',
                'ec2:Describe*',
                'lambda:Get*',
                'lambda:List*',
                's3:GetBucketAcl',
            ],
            resources: ['*'],
        });

        // VPC Deployment permissions for lambda
        const vpcDeployPolicy = new iam.PolicyStatement({
            sid: "VPCDeployPermissions",
            effect: iam.Effect.ALLOW,
            actions: [
                'logs:CreateLogGroup',
                'logs:CreateExportTask',
                'logs:CreateLogStream',
                'logs:PutLogEvents',
                'xray:UpdateSamplingRule',
                'xray:PutTelemetryRecords',
                'xray:CreateGroup',
                'xray:PutTraceSegments',
                'xray:DeleteSamplingRule',
                'xray:DeleteGroup',
                'xray:UpdateGroup',
                'xray:CreateSamplingRule',
                'ec2:CreateNetworkInterface',
                'ec2:DescribeNetworkInterfaces',
                'ec2:DeleteNetworkInterface',
                'ec2:AssignPrivateIpAddresses',
                'ec2:UnassignPrivateIpAddresses',
            ],
            resources: ['*'],
        });

        // Cross Account Assume permissions for lambda
        const assumeRolePolicy = new iam.PolicyStatement({
            sid: "AssumeRolePermissions",
            effect: iam.Effect.ALLOW,
            actions: [
                'sts:AssumeRole',
            ],
            resources: [`arn:aws:iam::*:role/rle.${namedotprefix}*`],
        });

        // SQS permissions for lambda functions
        const sqsPolicy = new iam.PolicyStatement({
            sid: "SQSPermissions",
            effect: iam.Effect.ALLOW,
            actions: [
                'sqs:DeleteMessage',
                'sqs:GetQueueUrl',
                'sqs:ChangeMessageVisibility',
                'sqs:ReceiveMessage',
                'sqs:SendMessage',
                'sqs:GetQueueAttributes',
                'sqs:ListQueueTags',
                'sqs:ListQueues',
            ],
            resources: [`${ruleSqsQueue.queueArn}`],
        });

        // Grant lambda functions necessary permissions
        ruleCollectLambda.addToRolePolicy(readOnlyPolicy);
        ruleCollectLambda.addToRolePolicy(vpcDeployPolicy);
        ruleCollectLambda.addToRolePolicy(sqsPolicy);
        ruleCollectLambda.addToRolePolicy(assumeRolePolicy);

        ruleExecuteLambda.addToRolePolicy(readOnlyPolicy);
        ruleExecuteLambda.addToRolePolicy(vpcDeployPolicy);
        ruleExecuteLambda.addToRolePolicy(sqsPolicy);
        ruleExecuteLambda.addToRolePolicy(assumeRolePolicy);

        ruleExecuteLambda.addToRolePolicy(new iam.PolicyStatement({
            sid: "NetworkFirewallPermissions",
            effect: iam.Effect.ALLOW,
            actions: [
                'network-firewall:ListTagsForResource',
                'network-firewall:DeleteRuleGroup',
                'network-firewall:DescribeLoggingConfiguration',
                'network-firewall:CreateRuleGroup',
                'network-firewall:DescribeRuleGroupMetadata',
                'network-firewall:DescribeFirewall',
                'network-firewall:DeleteFirewallPolicy',
                'network-firewall:UpdateRuleGroup',
                'network-firewall:ListRuleGroups',
                'network-firewall:DescribeRuleGroup',
                'network-firewall:AssociateFirewallPolicy',
                'network-firewall:DescribeFirewallPolicy',
                'network-firewall:ListFirewalls',
                'network-firewall:UpdateFirewallPolicy',
                'network-firewall:DescribeResourcePolicy',
                'network-firewall:CreateFirewallPolicy',
                'network-firewall:ListFirewallPolicies',
            ],
            resources: [`arn:aws:network-firewall:${this.region}:${this.account}:*/*`]
        }));

        new CfnOutput(this, 'RuleCollectLambdaArn', {
            description: 'ARN of Lambda triggered by the EventBridge events',
            value: ruleCollectLambda.functionArn,
            exportName: `rulecollect-lambda-arn-${props.stage}`,
        });
    }
}