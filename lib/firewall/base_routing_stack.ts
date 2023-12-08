import * as ec2 from 'aws-cdk-lib/aws-ec2';
import { Stack, Duration, CfnOutput } from 'aws-cdk-lib';
import { Construct } from 'constructs';

// Creates required route tables for egress VPC routing
export class BaseRoutingStack extends Stack {
    constructor(scope: Construct, id: string, props: {
        namePrefix: string;
        stage: string;
        vpcId: string;
        vpcCidr: string;
        subnetIds: Record<string, string>;
        azIds: Record<string, string>;
        multiAz: boolean;
        transitGateway: string;
        internalNet: string;
    }) {
        super(scope, id);

        for (const az of Object.values(props.azIds)) {
            const azSuffix = az[az.length - 1];

            // Firewall Route Table
            const firewallRouteTable = new ec2.CfnRouteTable(this, `FirewallRouteTable_${azSuffix.toUpperCase()}`, {
                vpcId: props.vpcId,
                tags: [{ key: 'Name', value: `rtb.${props.namePrefix}.nfw.10${azSuffix}.${props.stage}` }],
            });

            // Firewall Route Table Association
            new ec2.CfnSubnetRouteTableAssociation(this, `FirewallRouteTableAssociation_${azSuffix.toUpperCase()}`, {
                routeTableId: firewallRouteTable.ref,
                subnetId: props.subnetIds[`firewall_subnet_${azSuffix}`],
            });

            // Public Route Table
            const publicRouteTable = new ec2.CfnRouteTable(this, `PublicRouteTable_${azSuffix.toUpperCase()}`, {
                vpcId: props.vpcId,
                tags: [{ key: 'Name', value: `rtb.${props.namePrefix}.ngw.11${azSuffix}.${props.stage}` }],
            });

            // Public Route Table Association
            new ec2.CfnSubnetRouteTableAssociation(this, `PublicRouteTableAssociation_${azSuffix.toUpperCase()}`, {
                routeTableId: publicRouteTable.ref,
                subnetId: props.subnetIds[`nat_subnet_${azSuffix}`],
            });

            // TGW Route Table
            const tgwRouteTable = new ec2.CfnRouteTable(this, `TGWRouteTable_${azSuffix.toUpperCase()}`, {
                vpcId: props.vpcId,
                tags: [{ key: 'Name', value: `rtb.${props.namePrefix}.tgw.00${azSuffix}.${props.stage}` }],
            });

            // TGW Route Table Association
            new ec2.CfnSubnetRouteTableAssociation(this, `TGWRouteTableAssociation_${azSuffix.toUpperCase()}`, {
                routeTableId: tgwRouteTable.ref,
                subnetId: props.subnetIds[`tgw_subnet_${azSuffix}`],
            });

            // Output the VPC ID and subnet details for reference
            new CfnOutput(this, `FirewallRouteTableId_${azSuffix.toUpperCase()}`, {
                value: firewallRouteTable.attrRouteTableId,
                description: `FirewallRouteTable for AZ ${azSuffix.toUpperCase()}`,
                exportName: `fw-routetable-${props.stage}-${azSuffix}`,
            });

            // Output the VPC ID and subnet details for reference
            new CfnOutput(this, `TGWRouteTableId_${azSuffix.toUpperCase()}`, {
                value: tgwRouteTable.attrRouteTableId,
                description: `TGWRouteTable for AZ ${azSuffix.toUpperCase()}`,
                exportName: `tgw-routetable-${props.stage}-${azSuffix}`,
            });

            // Output the VPC ID and subnet details for reference
            new CfnOutput(this, `PublicRouteTableId_${azSuffix.toUpperCase()}`, {
                value: publicRouteTable.attrRouteTableId,
                description: `PublicRouteTable for AZ ${azSuffix.toUpperCase()}`,
                exportName: `nat-routetable-${props.stage}-${azSuffix}`,
            });
        }
    }
}
