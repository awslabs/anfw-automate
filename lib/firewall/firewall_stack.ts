import { RemovalPolicy, Stack } from 'aws-cdk-lib';
import { Construct } from "constructs";
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as logs from 'aws-cdk-lib/aws-logs';
import { aws_networkfirewall as anfw } from 'aws-cdk-lib';
import { CfnOutput } from 'aws-cdk-lib';
import { Bucket } from 'aws-cdk-lib/aws-s3';
import * as fs from "fs";

type RuleOrder = 'DEFAULT_ACTION_ORDER' | 'STRICT_ORDER';

export class NetworkFirewallStack extends Stack {
    constructor(scope: Construct, id: string, props: {
        namePrefix: string;
        vpcId: string;
        subnetIds: { [key: string]: string };
        azIds: { [key: string]: string };
        stage: string;
        internalNet: string;
        ruleOrder: RuleOrder;
    }) {
        super(scope, id);

        const { namePrefix, vpcId, subnetIds, azIds, stage, internalNet } = props;
        const namedotprefix = namePrefix.replace(/-/g, ".");
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

        let internal_net_list: string[] = internalNet.split(',');

        const policyContent = fs.readFileSync(absoluteFilePath, 'utf-8');
        const firewallPolicyJson = JSON.parse(policyContent);

        // Update HOME_NET policyVariables in the policy
        firewallPolicyJson.policyVariables = {
            ruleVariables: {
                HOME_NET: {
                    definition: internal_net_list,
                },
            },
        }

        // Create a Network Firewall policy
        const firewallPolicy = new anfw.CfnFirewallPolicy(this, 'FirewallPolicy', {
            firewallPolicyName: `plc-${namePrefix}-fwbase-00-${stage}`,
            firewallPolicy: {
                ...firewallPolicyJson,
                // statelessDefaultActions: ['aws:forward_to_sfe'],
                // statelessFragmentDefaultActions: ['aws:forward_to_sfe'],
                // policyVariables: {
                //     ruleVariables: {
                //         HOME_NET: {
                //             definition: internal_net_list,
                //         },
                //     },
                // },
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
            retention: logs.RetentionDays.ONE_YEAR
        });

        const fwFlowLogGroup = new logs.LogGroup(this, 'FWFlowLogGroup', {
            logGroupName: `${namedotprefix}.nfw.flow.${stage}`,
            retention: logs.RetentionDays.ONE_YEAR
        });

        const cfnLoggingConfiguration = new anfw.CfnLoggingConfiguration(this, 'MyCfnLoggingConfiguration', {
            firewallArn: firewall.attrFirewallArn,
            loggingConfiguration: {
                logDestinationConfigs: [{
                    logDestination:
                        { "logGroup": fwAlertLogGroup.logGroupName },
                    logDestinationType: 'CloudWatchLogs',
                    logType: 'ALERT',
                },
                {
                    logDestination:
                        { "logGroup": fwFlowLogGroup.logGroupName },
                    logDestinationType: 'CloudWatchLogs',
                    logType: 'FLOW',
                }],
            },
        });

        // TODO: Create export to s3 task for logs and reduce CW retention

        new CfnOutput(this, 'FirewallArn', {
            description: 'AWS Network Firewall ARN',
            exportName: `nfw-arn-${stage}`,
            value: firewall.attrFirewallArn,
        });

    }
}
