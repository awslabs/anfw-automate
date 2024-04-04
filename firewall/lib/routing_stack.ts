import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as logs from 'aws-cdk-lib/aws-logs';
import { Construct } from 'constructs';
import { CustomResource, Duration, Fn, Stack } from 'aws-cdk-lib';
import * as pylambda from "@aws-cdk/aws-lambda-python-alpha";
import { execSync } from 'child_process';
import { Runtime } from 'aws-cdk-lib/aws-lambda';

// Adds all required routes to the route tables
export class RoutingStack extends Stack {
    constructor(scope: Construct, id: string, props: {
        namePrefix: string;
        stage: string;
        vpcId: string;
        vpcCidr: string;
        subnetIds: { [key: string]: string };
        azIds: { [key: string]: string };
        multiAz: boolean;
        transitGateway: string;
        internalNet: string;
        internetGateway: string;
    }) {
        super(scope, id);

        // Import values from FirewallStack using Fn::ImportValue
        const firewallArn = Fn.importValue(`nfw-arn-${props.stage}`)

        // Create Lambda function for custom resource
        const deleteRoutesLambda = new pylambda.PythonFunction(this, 'DeleteRoutesFunction', {
            entry: 'lambda/delete_routes',
            runtime: Runtime.PYTHON_3_11,
            index: 'delete_routes.py',
            timeout: Duration.seconds(60),
            tracing: lambda.Tracing.ACTIVE,
            logRetention: logs.RetentionDays.ONE_WEEK,
            bundling: {
                assetExcludes: ['.venv'],
            }
        });

        // Define the CFN custom resource
        const deleteRoutesCustomResource = new CustomResource(this, 'DeleteRoutesCustomResource', {
            serviceToken: deleteRoutesLambda.functionArn,
            properties: {
                VpcId: props.vpcId,
                VpcCidrBlock: props.vpcCidr,
            },
        });
        // ARNs of route tables not known
        deleteRoutesLambda.addToRolePolicy(new iam.PolicyStatement({
            actions: ['ec2:DeleteRoute'],
            resources: [`arn:aws:ec2:${this.region}:${this.account}:route-table/*`],
        }));

        // Only supports * resource
        deleteRoutesLambda.addToRolePolicy(new iam.PolicyStatement({
            actions: ['ec2:DescribeRouteTables'],
            resources: ["*"],
        }));

        // Create custom resource for fetching VPC endpoint IDs
        const fetchAnfwVpceLambda = new pylambda.PythonFunction(this, 'FetchVpcEndpointsFunction', {
            entry: 'lambda/fetch_vpc_endpoints',
            runtime: Runtime.PYTHON_3_11,
            index: 'fetch_vpc_endpoints.py',
            timeout: Duration.seconds(30),
            tracing: lambda.Tracing.ACTIVE,
            logRetention: logs.RetentionDays.ONE_WEEK,
            bundling: {
                assetExcludes: ['.venv'],
            }
        });

        // Define the CFN custom resource
        const getAnfwVpceCustomResource = new CustomResource(this, 'GetAnfwVpceCustomResource', {
            serviceToken: fetchAnfwVpceLambda.functionArn,
            properties: {
                az_a: props.azIds['az_a'],
                az_b: props.azIds['az_b'],
                az_c: props.azIds['az_c'],
                MultiAZ: props.multiAz,
                FwArn: firewallArn,
            },
        });

        fetchAnfwVpceLambda.addToRolePolicy(new iam.PolicyStatement({
            actions: ['network-firewall:DescribeFirewall'],
            resources: [`arn:aws:network-firewall:${this.region}:${this.account}:firewall/*`],
        }));

        for (const azKey in props.azIds) {
            const azSuffix = props.azIds[azKey][props.azIds[azKey].length - 1];

            // Import Values from Basic RoutingStack
            const firewallRouteTable = Fn.importValue(`fw-routetable-${props.stage}-${azSuffix}`);
            const tgwRouteTable = Fn.importValue(`tgw-routetable-${props.stage}-${azSuffix}`);
            const publicRouteTable = Fn.importValue(`nat-routetable-${props.stage}-${azSuffix}`);
            const natGatewayId = Fn.importValue(`nat-id-${props.stage}-${azSuffix}`);


            let internalNetArray: string[] = props.internalNet.split(',');
            for (let i = 0; i < internalNetArray.length; i++) {
                let currentValue: string = internalNetArray[i];
                // Create Firewall Internal Route
                let firewallInternalRoute = new ec2.CfnRoute(this, `FirewallInternalRoute${i}${azSuffix.toUpperCase()}`, {
                    destinationCidrBlock: internalNetArray[i],
                    transitGatewayId: props.transitGateway,
                    routeTableId: firewallRouteTable,
                });

                firewallInternalRoute.node.addDependency(deleteRoutesCustomResource);

                // Create PublicInternalRoute
                let publicInternalRoute = new ec2.CfnRoute(this, `PublicAInternalRoute${i}${azSuffix.toUpperCase()}`, {
                    destinationCidrBlock: internalNetArray[i],
                    vpcEndpointId: getAnfwVpceCustomResource.getAttString(`FwVpceId_${azSuffix}`),
                    routeTableId: publicRouteTable,
                });

                publicInternalRoute.node.addDependency(getAnfwVpceCustomResource);
                publicInternalRoute.node.addDependency(deleteRoutesCustomResource);

            }

            // Create Firewall Default Route
            const firewallDefaultRoute = new ec2.CfnRoute(this, `FirewallDefaultRoute${azSuffix.toUpperCase()}`, {
                destinationCidrBlock: '0.0.0.0/0',
                natGatewayId: natGatewayId,
                routeTableId: firewallRouteTable,
            });

            firewallDefaultRoute.node.addDependency(getAnfwVpceCustomResource);
            firewallDefaultRoute.node.addDependency(deleteRoutesCustomResource);

            // Create PublicDefaultRoute
            const publicDefaultRoute = new ec2.CfnRoute(this, `PublicDefaultRoute${azSuffix.toUpperCase()}`, {
                destinationCidrBlock: '0.0.0.0/0',
                gatewayId: props.internetGateway,
                routeTableId: publicRouteTable,
            });

            publicDefaultRoute.node.addDependency(getAnfwVpceCustomResource);
            publicDefaultRoute.node.addDependency(deleteRoutesCustomResource);

            // Create TGWDefaultRoute
            const tgwDefaultRoute = new ec2.CfnRoute(this, `TGWDefaultRoute${azSuffix.toUpperCase()}`, {
                destinationCidrBlock: '0.0.0.0/0',
                vpcEndpointId: getAnfwVpceCustomResource.getAttString(`FwVpceId_${azSuffix}`),
                routeTableId: tgwRouteTable,
            });

            tgwDefaultRoute.node.addDependency(getAnfwVpceCustomResource);
            tgwDefaultRoute.node.addDependency(deleteRoutesCustomResource);
        }
    }
}
