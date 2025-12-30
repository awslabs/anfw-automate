import { Construct } from 'constructs';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as logs from 'aws-cdk-lib/aws-logs';
import { aws_networkfirewall as anfw } from 'aws-cdk-lib';
import { CfnOutput } from 'aws-cdk-lib';
import * as fs from 'fs';
import { TaggedStack, TaggedStackProps } from '../../shared/lib/tagged_stack';

type RuleOrder = 'DEFAULT_ACTION_ORDER' | 'STRICT_ORDER';

export interface NetworkFirewallProps extends TaggedStackProps {
  namePrefix: string;
  vpcId: string;
  subnetIds: { [key: string]: string };
  azIds: { [key: string]: string };
  internalNet: string;
  ruleOrder: RuleOrder;
}

export class NetworkFirewallStack extends TaggedStack {
  constructor(scope: Construct, id: string, props: NetworkFirewallProps) {
    super(scope, id, props);

    const { namePrefix, vpcId, subnetIds, azIds, stage, internalNet } = props;
    const namedotprefix = namePrefix.replace(/-/g, '.');
    const absoluteFilePath = `policy/${props.ruleOrder}.json`;

    // Create subnet mappings based on the provided dictionary
    const subnetMappingList: anfw.CfnFirewall.SubnetMappingProperty[] = [];
    for (const az of Object.values(azIds)) {
      const azSuffix = az[az.length - 1];
      const subnetMappingProperty: anfw.CfnFirewall.SubnetMappingProperty = {
        subnetId: subnetIds[`firewall_subnet_${azSuffix}`],
        ipAddressType: 'IPV4',
      };
      subnetMappingList.push(subnetMappingProperty);

      // Create an Elastic IP
      const eip = new ec2.CfnEIP(this, `EIP${azSuffix}`);

      // Create a NAT Gateway and associate the Elastic IP with it
      const natGateway = new ec2.CfnNatGateway(this, `NATGateway${azSuffix}`, {
        allocationId: eip.attrAllocationId,
        subnetId: subnetIds[`nat_subnet_${azSuffix}`],
      });

      new CfnOutput(this, `NATGatewayId${azSuffix.toUpperCase()}`, {
        description: 'NAT Gateway ID',
        exportName: `nat-id-${stage}-${azSuffix}`,
        value: natGateway.attrNatGatewayId,
      });
    }

    const internal_net_list: string[] = internalNet.split(',');

    const policyContent = fs.readFileSync(absoluteFilePath, 'utf-8');
    const firewallPolicyJson = JSON.parse(policyContent);

    // Update HOME_NET policyVariables in the policy
    firewallPolicyJson.policyVariables = {
      ruleVariables: {
        HOME_NET: {
          definition: internal_net_list,
        },
      },
    };

    const ordername: string = props.ruleOrder === 'DEFAULT_ACTION_ORDER' ? 'action' : 'strict';

    // Create a Network Firewall policy
    const firewallPolicy = new anfw.CfnFirewallPolicy(this, 'FirewallPolicy', {
      firewallPolicyName: `plc-${namePrefix}-fwbase-00-${ordername}-${stage}`,
      firewallPolicy: {
        ...firewallPolicyJson,
      },
    });

    // Create a Network Firewall
    const firewall = new anfw.CfnFirewall(this, 'NetworkFirewall', {
      firewallName: `nfw-${namePrefix}-${stage}`,
      subnetMappings: subnetMappingList,
      firewallPolicyArn: firewallPolicy.attrFirewallPolicyArn,
      vpcId: vpcId,
    });

    // Create Logging Configuration
    const fwAlertLogGroup = new logs.LogGroup(this, 'FWAlertLogGroup', {
      logGroupName: `${namedotprefix}.nfw.alert.${stage}`,
      retention: logs.RetentionDays.ONE_YEAR,
    });

    const fwFlowLogGroup = new logs.LogGroup(this, 'FWFlowLogGroup', {
      logGroupName: `${namedotprefix}.nfw.flow.${stage}`,
      retention: logs.RetentionDays.ONE_YEAR,
    });

    const cfnLoggingConfiguration = new anfw.CfnLoggingConfiguration(
      this,
      'MyCfnLoggingConfiguration',
      {
        firewallArn: firewall.attrFirewallArn,
        loggingConfiguration: {
          logDestinationConfigs: [
            {
              logDestination: { logGroup: fwAlertLogGroup.logGroupName },
              logDestinationType: 'CloudWatchLogs',
              logType: 'ALERT',
            },
            {
              logDestination: { logGroup: fwFlowLogGroup.logGroupName },
              logDestinationType: 'CloudWatchLogs',
              logType: 'FLOW',
            },
          ],
        },
      }
    );

    // Ensure logging configuration is created after firewall
    cfnLoggingConfiguration.node.addDependency(firewall);

    // TODO: Create export to s3 task for logs and reduce CW retention

    new CfnOutput(this, 'FirewallArn', {
      description: 'AWS Network Firewall ARN',
      exportName: `nfw-arn-${stage}`,
      value: firewall.attrFirewallArn,
    });
  }
}
