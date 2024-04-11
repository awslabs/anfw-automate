import * as events from 'aws-cdk-lib/aws-events';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import { Construct } from "constructs";
import { CfnOutput, Duration, Fn, Stack } from 'aws-cdk-lib';
import { LambdaFunction } from 'aws-cdk-lib/aws-events-targets';
import { Alarm } from 'aws-cdk-lib/aws-cloudwatch';
import { Queue } from 'aws-cdk-lib/aws-sqs';
import { Effect, PolicyStatement, ServicePrincipal } from 'aws-cdk-lib/aws-iam';
import { TaggedStack, TaggedStackProps } from '../../shared/lib/tagged_stack';

export interface ServerlessProps extends TaggedStackProps {
    namePrefix: string;
    vpcId: string;
    organizationIds: [string];
}

export class ServerlessStack extends TaggedStack {
    constructor(scope: Construct, id: string, props: ServerlessProps) {
        super(scope, id, props);

        const RuleCollectLambdaArn = Fn.importValue(`rulecollect-lambda-arn-${props.stage}`);

        // Initialize the Lambda function
        const ruleCollectLambda = lambda.Function.fromFunctionArn(
            this,
            'RuleCollectLambda',
            RuleCollectLambdaArn
        );

        // Create Event Bus
        const s3EventBus = new events.EventBus(this, 'S3EventBus', {
            eventBusName: `eb-${props.namePrefix}-ConfigEventBus-${props.stage}`,
        });

        // Event Bus Policy
        new events.CfnEventBusPolicy(this, 'S3EventBusPolicy', {
            eventBusName: s3EventBus.eventBusName,
            statementId: 'CentralEventBusStatement',
            statement: {
                "Effect": "Allow",
                "Principal": "*",
                "Action": "events:PutEvents",
                "Resource": `${s3EventBus.eventBusArn}`,
                "Condition": { "ForAnyValue:StringEquals": { "aws:PrincipalOrgID": `${props.organizationIds.toString()}` } }
            }
        });

        // Create SQS
        const s3DLQueue = new Queue(this, 'S3DLQueue', {
            queueName: `dlq-${props.namePrefix}-${props.stage}-ConfigEventBus`,
        });


        // S3 Object Event Rule
        const s3ObjectEventRule = new events.Rule(this, 'S3ObjectEventRule', {
            ruleName: `er-${props.namePrefix}-S3ObjectEventRule-${props.stage}`,
            eventBus: s3EventBus,
            eventPattern: {
                source: ['aws.s3'],
                detailType: [
                    'Object Created',
                    'Object Deleted',
                    'Object Restore Completed',
                    'Object Restore Expired',
                    'Object Restore Initiated',
                ],
            },
        });

        s3ObjectEventRule.addTarget(new LambdaFunction(ruleCollectLambda, {
            deadLetterQueue: s3DLQueue,
            maxEventAge: Duration.hours(2),
            retryAttempts: 2,
        }));

        // S3 Bucket Event Rule
        const s3BucketEventRule = new events.Rule(this, 'S3BucketEventRule', {
            ruleName: `er-${props.namePrefix}-S3BucketEventRule-${props.stage}`,
            eventBus: s3EventBus,
            eventPattern: {
                source: ['aws.s3'],
                detailType: ['AWS API Call via CloudTrail'],
                detail: {
                    eventSource: ['s3.amazonaws.com'],
                    eventName: ['DeleteBucket'],
                },
            },
        });
        s3BucketEventRule.addTarget(new LambdaFunction(ruleCollectLambda, {
            deadLetterQueue: s3DLQueue,
            maxEventAge: Duration.hours(2),
            retryAttempts: 2,
        }));

        // VPC Delete Event Rule
        const vpcDeleteEventRule = new events.Rule(this, 'VPCDeleteEventRule', {
            ruleName: `er-${props.namePrefix}-VPCDeleteEventRule-${props.stage}`,
            eventBus: s3EventBus,
            eventPattern: {
                source: ['aws.ec2'],
                detailType: ['AWS API Call via CloudTrail'],
                detail: {
                    eventSource: ['ec2.amazonaws.com'],
                    eventName: ['DeleteVpc'],
                },
            },
        });
        vpcDeleteEventRule.addTarget(new LambdaFunction(ruleCollectLambda, {
            deadLetterQueue: s3DLQueue,
            maxEventAge: Duration.hours(2),
            retryAttempts: 2,
        }));


        // Grant Event Rules Permission SQS Queue
        s3DLQueue.addToResourcePolicy(
            new PolicyStatement({
                effect: Effect.ALLOW,
                actions: ['sqs:SendMessage', 'sqs:ReceiveMessage'],
                principals: [new ServicePrincipal('events.amazonaws.com')],
                resources: [s3DLQueue.queueArn],
                conditions: {
                    'ForAnyValue:StringEquals': {
                        'aws:SourceArn': [
                            s3ObjectEventRule.ruleArn,
                            s3BucketEventRule.ruleArn,
                            vpcDeleteEventRule.ruleArn,
                        ],
                    },
                },
            })
        );

        // Grant EventBridge Lambda Permissions
        new lambda.CfnPermission(this, 'S3ObjectLambdaPermission', {
            action: 'lambda:InvokeFunction',
            functionName: RuleCollectLambdaArn,
            principal: 'events.amazonaws.com',
            sourceArn: s3ObjectEventRule.ruleArn,
        });

        new lambda.CfnPermission(this, 'S3BucketLambdaPermission', {
            action: 'lambda:InvokeFunction',
            functionName: RuleCollectLambdaArn,
            principal: 'events.amazonaws.com',
            sourceArn: s3BucketEventRule.ruleArn,
        });

        new lambda.CfnPermission(this, 'VPCDeleteLambdaPermission', {
            action: 'lambda:InvokeFunction',
            functionName: RuleCollectLambdaArn,
            principal: 'events.amazonaws.com',
            sourceArn: vpcDeleteEventRule.ruleArn,
        });

        // CloudWatch Alarms
        const dlqAlarm = new Alarm(this, 'DLQAlarm', {
            alarmDescription: 'SQS failed',
            alarmName: `cwa-${props.namePrefix}-SQSAlarm-${props.stage}`,
            metric: s3DLQueue.metricApproximateNumberOfMessagesVisible(),
            evaluationPeriods: 1,
            threshold: 1,
        });

        // Outputs
        new CfnOutput(this, 'CentralEventBusArn', {
            value: s3EventBus.eventBusArn,
            description: 'Central Event Bus ARN',
            exportName: `central-eventbus-arn-${props.stage}`
        });

    }
}
