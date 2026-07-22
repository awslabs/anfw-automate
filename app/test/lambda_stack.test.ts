import * as cdk from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';
import * as path from 'path';
import { LambdaStack } from '../lib/lambda_stack';

/**
 * Skip Docker bundling for PythonLayerVersion during tests.
 * We provide a local bundling implementation that creates an empty output,
 * allowing CDK synthesis to complete without Docker.
 */
jest.mock('@aws-cdk/aws-lambda-python-alpha', () => {
  const actual = jest.requireActual('@aws-cdk/aws-lambda-python-alpha');
  const cdk = require('aws-cdk-lib');
  const lambda = require('aws-cdk-lib/aws-lambda');
  const { Construct } = require('constructs');

  class MockPythonLayerVersion extends lambda.LayerVersion {
    constructor(scope: any, id: string, props: any) {
      super(scope, id, {
        ...props,
        code: lambda.Code.fromAsset(path.join(__dirname, '..', 'src')),
        compatibleRuntimes: props.compatibleRuntimes,
      });
    }
  }

  return {
    ...actual,
    PythonLayerVersion: MockPythonLayerVersion,
  };
});

/**
 * Property 7 — SQS/DLQ synthesis
 * Validates: Requirements 1.6
 *
 * Synthesize LambdaStack and assert:
 * - Exactly two SQS queues (main FIFO + DLQ)
 * - At least one queue has FifoQueue: true
 * - Exactly one SQS event source mapping for RuleExecute
 */
describe('LambdaStack - SQS/DLQ synthesis (Property 7)', () => {
  let template: Template;

  beforeAll(() => {
    const app = new cdk.App();
    const stack = new LambdaStack(app, 'TestLambdaStack', {
      namePrefix: 'test-prefix',
      vpcId: 'vpc-12345678',
      supportedRegions: ['us-east-1', 'us-west-2'],
      policyArns: ['arn:aws:network-firewall:us-east-1:123456789012:firewall-policy/test-policy'],
      ruleOrder: 1,
      stage: 'test',
      globalTags: { Project: 'anfw-automate', Owner: 'test' },
      env: { account: '123456789012', region: 'us-east-1' },
    });

    template = Template.fromStack(stack);
  });

  test('contains exactly two SQS queues (main FIFO + DLQ)', () => {
    template.resourceCountIs('AWS::SQS::Queue', 2);
  });

  test('at least one queue is FIFO', () => {
    template.hasResourceProperties('AWS::SQS::Queue', {
      FifoQueue: true,
    });
  });

  test('contains exactly one SQS event source mapping for RuleExecute', () => {
    template.resourceCountIs('AWS::Lambda::EventSourceMapping', 1);
  });
});
