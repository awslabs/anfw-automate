import { App } from 'aws-cdk-lib';
import { Template, Match } from 'aws-cdk-lib/assertions';
import { IntBaseStack } from './int_base_stack';

const NAME_PREFIX = 'anfw';
const STAGE = 'int';

function synth(): Template {
  const app = new App();
  const stack = new IntBaseStack(app, 'IntBaseStack', {
    namePrefix: NAME_PREFIX,
    stage: STAGE,
    centralAccountId: '421222417363',
  });
  return Template.fromStack(stack);
}

describe('IntBaseStack — consumes foundational, does not create hub/firewall (Req 2.3)', () => {
  test('does NOT create a Transit Gateway (resolves shared TGW from SSM)', () => {
    synth().resourceCountIs('AWS::EC2::TransitGateway', 0);
  });

  test('does NOT create a Network Firewall policy (resolves foundational policy from SSM)', () => {
    const t = synth();
    t.resourceCountIs('AWS::NetworkFirewall::FirewallPolicy', 0);
    t.resourceCountIs('AWS::NetworkFirewall::Firewall', 0);
  });

  test('attaches the tenant VPC to the shared TGW', () => {
    synth().resourceCountIs('AWS::EC2::TransitGatewayAttachment', 1);
  });
});

describe('IntBaseStack — data-plane wiring (Req 3, 4)', () => {
  test('deploys the probe Lambda inside the tenant VPC (has VpcConfig)', () => {
    const t = synth();
    const fns = t.findResources('AWS::Lambda::Function');
    const vpcFns = Object.values(fns).filter(f => f.Properties?.VpcConfig !== undefined);
    expect(vpcFns.length).toBeGreaterThanOrEqual(1);
    // the probe function is named lmb-{prefix}-int-probe-{stage}
    t.hasResourceProperties('AWS::Lambda::Function', {
      FunctionName: `lmb-${NAME_PREFIX}-int-probe-${STAGE}`,
      VpcConfig: Match.anyValue(),
    });
  });

  test('routes tenant egress 0.0.0.0/0 to the shared TGW', () => {
    synth().hasResourceProperties('AWS::EC2::Route', {
      DestinationCidrBlock: '0.0.0.0/0',
      TransitGatewayId: Match.anyValue(),
    });
  });
});

describe('IntBaseStack — exports the harness resolves (Req 3.7)', () => {
  test('exposes all seven CloudFormation exports', () => {
    const t = synth();
    const exportNames = Object.values(t.findOutputs('*'))
      .map(o => o.Export?.Name)
      .filter(Boolean);
    const expected = [
      `${NAME_PREFIX}-int-tgw-id-${STAGE}`,
      `${NAME_PREFIX}-int-tenant-vpc-id-${STAGE}`,
      `${NAME_PREFIX}-int-firewall-policy-arn-${STAGE}`,
      `${NAME_PREFIX}-int-probe-function-name-${STAGE}`,
      `${NAME_PREFIX}-int-config-bucket-name-${STAGE}`,
      `${NAME_PREFIX}-int-xaccount-role-arn-${STAGE}`,
      `${NAME_PREFIX}-int-event-bus-arn-${STAGE}`,
    ];
    for (const name of expected) {
      expect(exportNames).toContain(name);
    }
  });
});
