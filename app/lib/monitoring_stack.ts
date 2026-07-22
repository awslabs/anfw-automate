import { Duration } from 'aws-cdk-lib';
import * as cloudwatch from 'aws-cdk-lib/aws-cloudwatch';
import { Construct } from 'constructs';
import { TaggedStack, TaggedStackProps } from '../../shared/lib/tagged_stack';

export interface MonitoringStackProps extends TaggedStackProps {
  namePrefix: string;
  ruleCollectFunctionName: string;
  ruleExecuteFunctionName: string;
  sqsQueueName: string;
  dlqQueueName: string;
}

/**
 * Per-stage CloudWatch dashboard and alarms for the ANFW automation pipeline.
 *
 * Shows: invocations, errors, duration, SQS depth, DLQ depth, and ANFW update throttles.
 * Alarms: DLQ depth > 0, Lambda error rate > 1%, InvalidTokenException retries > 3,
 *         Network Firewall throttling > 0 (all 5-minute windows).
 *
 * Requirements: 13.3, 13.4
 */
export class MonitoringStack extends TaggedStack {
  constructor(scope: Construct, id: string, props: MonitoringStackProps) {
    super(scope, id, props);

    const { namePrefix, stage } = props;

    // ─── Metrics ──────────────────────────────────────────────────────────

    // Lambda metrics — RuleCollect
    const collectInvocations = new cloudwatch.Metric({
      namespace: 'AWS/Lambda',
      metricName: 'Invocations',
      dimensionsMap: { FunctionName: props.ruleCollectFunctionName },
      statistic: 'Sum',
      period: Duration.minutes(5),
    });

    const collectErrors = new cloudwatch.Metric({
      namespace: 'AWS/Lambda',
      metricName: 'Errors',
      dimensionsMap: { FunctionName: props.ruleCollectFunctionName },
      statistic: 'Sum',
      period: Duration.minutes(5),
    });

    const collectDuration = new cloudwatch.Metric({
      namespace: 'AWS/Lambda',
      metricName: 'Duration',
      dimensionsMap: { FunctionName: props.ruleCollectFunctionName },
      statistic: 'Average',
      period: Duration.minutes(5),
    });

    // Lambda metrics — RuleExecute
    const executeInvocations = new cloudwatch.Metric({
      namespace: 'AWS/Lambda',
      metricName: 'Invocations',
      dimensionsMap: { FunctionName: props.ruleExecuteFunctionName },
      statistic: 'Sum',
      period: Duration.minutes(5),
    });

    const executeErrors = new cloudwatch.Metric({
      namespace: 'AWS/Lambda',
      metricName: 'Errors',
      dimensionsMap: { FunctionName: props.ruleExecuteFunctionName },
      statistic: 'Sum',
      period: Duration.minutes(5),
    });

    const executeDuration = new cloudwatch.Metric({
      namespace: 'AWS/Lambda',
      metricName: 'Duration',
      dimensionsMap: { FunctionName: props.ruleExecuteFunctionName },
      statistic: 'Average',
      period: Duration.minutes(5),
    });

    // SQS metrics
    const sqsDepth = new cloudwatch.Metric({
      namespace: 'AWS/SQS',
      metricName: 'ApproximateNumberOfMessagesVisible',
      dimensionsMap: { QueueName: props.sqsQueueName },
      statistic: 'Maximum',
      period: Duration.minutes(5),
    });

    const dlqDepth = new cloudwatch.Metric({
      namespace: 'AWS/SQS',
      metricName: 'ApproximateNumberOfMessagesVisible',
      dimensionsMap: { QueueName: props.dlqQueueName },
      statistic: 'Maximum',
      period: Duration.minutes(5),
    });

    // Network Firewall throttle metric (custom metric published by the app)
    const anfwThrottles = new cloudwatch.Metric({
      namespace: `${namePrefix}/NetworkFirewall`,
      metricName: 'UpdateThrottles',
      dimensionsMap: { Stage: stage },
      statistic: 'Sum',
      period: Duration.minutes(5),
    });

    // ─── Dashboard ────────────────────────────────────────────────────────

    const dashboard = new cloudwatch.Dashboard(this, 'ANFWDashboard', {
      dashboardName: `${namePrefix}-${stage}-overview`,
    });

    dashboard.addWidgets(
      new cloudwatch.GraphWidget({
        title: 'Lambda Invocations',
        left: [collectInvocations, executeInvocations],
        width: 8,
      }),
      new cloudwatch.GraphWidget({
        title: 'Lambda Errors',
        left: [collectErrors, executeErrors],
        width: 8,
      }),
      new cloudwatch.GraphWidget({
        title: 'Lambda Duration (ms)',
        left: [collectDuration, executeDuration],
        width: 8,
      })
    );

    dashboard.addWidgets(
      new cloudwatch.GraphWidget({
        title: 'SQS Queue Depth',
        left: [sqsDepth],
        width: 8,
      }),
      new cloudwatch.GraphWidget({
        title: 'DLQ Depth',
        left: [dlqDepth],
        width: 8,
      }),
      new cloudwatch.GraphWidget({
        title: 'ANFW Update Throttles',
        left: [anfwThrottles],
        width: 8,
      })
    );

    // ─── Alarms (Requirement 13.4) ───────────────────────────────────────

    // DLQ depth > 0 (5-min window)
    new cloudwatch.Alarm(this, 'DLQDepthAlarm', {
      alarmName: `${namePrefix}-${stage}-dlq-depth`,
      alarmDescription: 'DLQ has messages — indicates processing failures',
      metric: dlqDepth,
      threshold: 0,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
      evaluationPeriods: 1,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });

    // Lambda error rate > 1% (5-min window) — using math expression
    const collectErrorRate = new cloudwatch.MathExpression({
      expression: '(errors / invocations) * 100',
      usingMetrics: {
        errors: new cloudwatch.Metric({
          namespace: 'AWS/Lambda',
          metricName: 'Errors',
          dimensionsMap: { FunctionName: props.ruleExecuteFunctionName },
          statistic: 'Sum',
          period: Duration.minutes(5),
        }),
        invocations: new cloudwatch.Metric({
          namespace: 'AWS/Lambda',
          metricName: 'Invocations',
          dimensionsMap: { FunctionName: props.ruleExecuteFunctionName },
          statistic: 'Sum',
          period: Duration.minutes(5),
        }),
      },
      period: Duration.minutes(5),
    });

    new cloudwatch.Alarm(this, 'LambdaErrorRateAlarm', {
      alarmName: `${namePrefix}-${stage}-lambda-error-rate`,
      alarmDescription: 'Lambda error rate exceeds 1% over 5 minutes',
      metric: collectErrorRate,
      threshold: 1,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
      evaluationPeriods: 1,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });

    // InvalidTokenException retries > 3 (5-min window)
    const invalidTokenRetries = new cloudwatch.Metric({
      namespace: `${namePrefix}/NetworkFirewall`,
      metricName: 'InvalidTokenExceptionRetries',
      dimensionsMap: { Stage: stage },
      statistic: 'Sum',
      period: Duration.minutes(5),
    });

    new cloudwatch.Alarm(this, 'InvalidTokenRetriesAlarm', {
      alarmName: `${namePrefix}-${stage}-invalid-token-retries`,
      alarmDescription: 'InvalidTokenException retries exceed 3 in 5 minutes',
      metric: invalidTokenRetries,
      threshold: 3,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
      evaluationPeriods: 1,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });

    // Network Firewall throttling > 0 (5-min window)
    new cloudwatch.Alarm(this, 'ANFWThrottleAlarm', {
      alarmName: `${namePrefix}-${stage}-anfw-throttles`,
      alarmDescription: 'Network Firewall API throttling detected',
      metric: anfwThrottles,
      threshold: 0,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
      evaluationPeriods: 1,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });
  }
}
