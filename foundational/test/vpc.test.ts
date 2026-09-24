import * as cdk from 'aws-cdk-lib';
import { Template, Match } from 'aws-cdk-lib/assertions';
import { VpcStack } from '../vpc/vpc_stack';

const STAGE = 'int';
const NAME_PREFIX = 'af-anfw-automate';

function synthVpc(): Template {
  const app = new cdk.App();
  const stack = new VpcStack(app, `vpc-${NAME_PREFIX}-${STAGE}`, {
    namePrefix: NAME_PREFIX,
    stage: STAGE,
    vpcCidr: '10.0.0.0/24',
    cidrMasks: { tgw: 28, firewall: 28, nat: 28 },
    availabilityZones: {
      az_a: 'eu-west-1a',
      az_b: 'eu-west-1b',
      az_c: 'eu-west-1c',
    },
    globalTags: {},
  });
  return Template.fromStack(stack);
}

describe('foundational VpcStack (migrated from vpc/lib/vpc_stack.ts)', () => {
  test('creates a VPC and internet gateway', () => {
    const t = synthVpc();
    t.resourceCountIs('AWS::EC2::VPC', 1);
    t.resourceCountIs('AWS::EC2::InternetGateway', 1);
  });

  test('retains the flow-log bucket on delete with an auto-generated (unclashable) name', () => {
    const t = synthVpc();
    // RETAIN so teardown keeps flow-log history; recreate gets a fresh name.
    t.hasResource('AWS::S3::Bucket', {
      DeletionPolicy: 'Retain',
      UpdateReplacePolicy: 'Retain',
    });
    // No explicit BucketName → CloudFormation auto-generates a unique name per create.
    const buckets = t.findResources('AWS::S3::Bucket');
    for (const b of Object.values(buckets)) {
      expect(b.Properties?.BucketName).toBeUndefined();
    }
  });

  test('preserves cross-stack export names (Req 2.3)', () => {
    const t = synthVpc();
    const outputs = t.findOutputs('*');
    const exportNames = Object.values(outputs)
      .map(o => o.Export?.Name)
      .filter(Boolean);
    expect(exportNames).toContain(`vpc-id-${STAGE}`);
    expect(exportNames).toContain(`igw-id-${STAGE}`);
    // subnet exports follow public-subnet-{stage}-* / private-subnet-{stage}-*
    expect(exportNames.some(n => String(n).startsWith(`public-subnet-${STAGE}-`))).toBe(true);
    expect(exportNames.some(n => String(n).startsWith(`private-subnet-${STAGE}-`))).toBe(true);
  });
});
