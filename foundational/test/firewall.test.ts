import * as cdk from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';
import { NetworkFirewallStack } from '../firewall/firewall_stack';
import { BaseRoutingStack } from '../firewall/base_routing_stack';

// Note: RoutingStack is intentionally NOT unit-tested here — its PythonFunction
// constructs bundle via Docker at synth time, which is exercised in CI (and full
// `cdk synth`) rather than in local jest runs. See the module README / design
// Testing Strategy.

const STAGE = 'int';
const NAME_PREFIX = 'af-anfw-automate';

const AZS = { az_a: 'eu-west-1a', az_b: 'eu-west-1b', az_c: 'eu-west-1c' };
const SUBNETS = {
  tgw_subnet_a: 'subnet-0tgwa',
  tgw_subnet_b: 'subnet-0tgwb',
  tgw_subnet_c: 'subnet-0tgwc',
  firewall_subnet_a: 'subnet-0fwa',
  firewall_subnet_b: 'subnet-0fwb',
  firewall_subnet_c: 'subnet-0fwc',
  nat_subnet_a: 'subnet-0nata',
  nat_subnet_b: 'subnet-0natb',
  nat_subnet_c: 'subnet-0natc',
};

function synthFirewall(): Template {
  const app = new cdk.App();
  const stack = new NetworkFirewallStack(app, `firewall-${NAME_PREFIX}-${STAGE}`, {
    namePrefix: NAME_PREFIX,
    stage: STAGE,
    vpcId: 'vpc-0placeholder',
    subnetIds: SUBNETS,
    azIds: AZS,
    internalNet: '10.0.0.0/8',
    ruleOrder: 'STRICT_ORDER',
    globalTags: {},
  });
  return Template.fromStack(stack);
}

function synthBaseRouting(): Template {
  const app = new cdk.App();
  const stack = new BaseRoutingStack(app, `base-routing-${NAME_PREFIX}-${STAGE}`, {
    namePrefix: NAME_PREFIX,
    stage: STAGE,
    vpcId: 'vpc-0placeholder',
    subnetIds: SUBNETS,
    azIds: AZS,
    vpcCidr: '10.0.0.0/24',
    multiAz: true,
    transitGateway: 'tgw-0placeholder',
    internalNet: '10.0.0.0/8',
    globalTags: {},
  });
  return Template.fromStack(stack);
}

describe('foundational NetworkFirewallStack (migrated)', () => {
  test('creates the Network Firewall + policy (policy JSON read via __dirname)', () => {
    const t = synthFirewall();
    t.resourceCountIs('AWS::NetworkFirewall::Firewall', 1);
    t.resourceCountIs('AWS::NetworkFirewall::FirewallPolicy', 1);
    t.hasResourceProperties('AWS::NetworkFirewall::FirewallPolicy', {
      FirewallPolicyName: `plc-${NAME_PREFIX}-fwbase-00-strict-${STAGE}`,
    });
  });

  test('preserves the nfw-arn export and NAT gateways', () => {
    const t = synthFirewall();
    const exportNames = Object.values(t.findOutputs('*'))
      .map(o => o.Export?.Name)
      .filter(Boolean);
    expect(exportNames).toContain(`nfw-arn-${STAGE}`);
    // one NAT gateway per AZ
    t.resourceCountIs('AWS::EC2::NatGateway', 3);
  });

  test('retains alert/flow log groups on delete with auto-generated (unclashable) names', () => {
    const t = synthFirewall();
    const groups = t.findResources('AWS::Logs::LogGroup');
    expect(Object.keys(groups).length).toBe(2);
    for (const g of Object.values(groups)) {
      expect(g.DeletionPolicy).toBe('Retain');
      expect(g.UpdateReplacePolicy).toBe('Retain');
      // no fixed LogGroupName → CFN auto-generates a unique name per create
      expect(g.Properties?.LogGroupName).toBeUndefined();
    }
  });

  test('publishes cross-account SSM handles (Task 3.3, int-environment Req 2.2)', () => {
    const t = synthFirewall();
    t.hasResourceProperties('AWS::SSM::Parameter', {
      Name: `/anfw-automate/${STAGE}/foundational/firewall-policy-arn`,
    });
    t.hasResourceProperties('AWS::SSM::Parameter', {
      Name: `/anfw-automate/${STAGE}/foundational/nfw-arn`,
    });
  });
});

describe('foundational BaseRoutingStack (migrated)', () => {
  test('preserves route-table export names (Req 3.2)', () => {
    const t = synthBaseRouting();
    const exportNames = Object.values(t.findOutputs('*'))
      .map(o => String(o.Export?.Name))
      .filter(Boolean);
    for (const az of ['a', 'b', 'c']) {
      expect(exportNames).toContain(`fw-routetable-${STAGE}-${az}`);
      expect(exportNames).toContain(`tgw-routetable-${STAGE}-${az}`);
      expect(exportNames).toContain(`nat-routetable-${STAGE}-${az}`);
    }
  });
});
