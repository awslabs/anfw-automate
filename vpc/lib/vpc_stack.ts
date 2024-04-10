import { Stack, StackProps, Tags, RemovalPolicy, CfnOutput } from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import { Construct } from 'constructs';
import { BlockPublicAccess, Bucket, BucketEncryption, ObjectOwnership } from "aws-cdk-lib/aws-s3";

interface VpcStackProps extends StackProps {
    namePrefix: string;
    vpcCidr: string;
    cidrMasks: Record<string, number>;
    availabilityZones: Record<string, string>;
    stage: string;
}

export class VpcStack extends Stack {
    constructor(scope: Construct, id: string, props: VpcStackProps) {
        super(scope, id);

        const namedotprefix = props.namePrefix.replace(/-/g, ".");

        // Create an array of SubnetConfiguration objects
        const subnetConfigurations: ec2.SubnetConfiguration[] = [];

        for (const [subnetName, cidrMask] of Object.entries(props.cidrMasks)) {
            let subnetType: ec2.SubnetType;
            if (subnetName == 'nat') {
                subnetType = ec2.SubnetType.PUBLIC;
            } else {
                subnetType = ec2.SubnetType.PRIVATE_WITH_EGRESS;
            }
            subnetConfigurations.push({
                cidrMask: cidrMask,
                name: `${subnetName.toUpperCase()}-`,
                subnetType: subnetType,
            });
        }

        // Create a VPC
        // TODO: If required create a custom VPC setup using L1 construct 
        // https://github.com/aws/aws-cdk/blob/6e4b4eab65dacea52af7d955575887bbafdff1fc/packages/%40aws-cdk/aws-ec2/lib/vpc.ts#L1130
        const vpc = new ec2.Vpc(this, 'vpc', {
            availabilityZones: Object.values(props.availabilityZones),
            natGateways: 0,
            ipAddresses: ec2.IpAddresses.cidr(props.vpcCidr),
            subnetConfiguration: subnetConfigurations,
        });

        Tags.of(vpc).add('Name', `vpc.${namedotprefix}.${props.stage}`);


        // Flow Log S3 Bucket
        const flowLogsBucket = new Bucket(this, 'FlowLogBucket', {
            blockPublicAccess: BlockPublicAccess.BLOCK_ALL,
            versioned: false,
            encryption: BucketEncryption.S3_MANAGED,
            serverAccessLogsPrefix: 'accesslogs/',
            enforceSSL: true,
            eventBridgeEnabled: true,
            objectOwnership: ObjectOwnership.BUCKET_OWNER_PREFERRED,
            removalPolicy: RemovalPolicy.DESTROY,
        });

        // Add flow logs
        const flowLogs = vpc.addFlowLog('FlowLogS3', {
            destination: ec2.FlowLogDestination.toS3(flowLogsBucket),
            trafficType: ec2.FlowLogTrafficType.ALL,
        });

        // Output the VPC ID and subnet details for reference
        new CfnOutput(this, 'VpcId', {
            value: vpc.vpcId,
            description: 'VPC ID',
            exportName: `vpc-id-${props.stage}`,
        });

        // Output the VPC ID and subnet details for reference
        new CfnOutput(this, 'InternetGatewayId', {
            value: vpc.internetGatewayId!,
            description: 'Internet Gateway ID',
            exportName: `igw-id-${props.stage}`,
        });

        // Iterate through public subnets
        const publicSubnets = vpc.selectSubnets({ subnetType: ec2.SubnetType.PUBLIC });
        for (const [index, subnet] of publicSubnets.subnets.entries()) {
            new CfnOutput(this, `PublicSubnet${index}Id`, {
                value: subnet.subnetId,
                description: `ID of public subnet ${index}`,
                exportName: `public-subnet-${props.stage}-${index}${subnet.availabilityZone.slice(-1)}`, // Export name in the format "NatSubnetX"
            });
        }

        // Iterate through private subnets and export values
        const privateSubnets = vpc.selectSubnets({ subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS });
        for (const [index, subnet] of privateSubnets.subnets.entries()) {
            new CfnOutput(this, `PrivateSubnet${index}Id`, {
                value: subnet.subnetId,
                description: `ID of private subnet ${index}`,
                exportName: `private-subnet-${props.stage}-${index}${subnet.availabilityZone.slice(-1)}`, // Export name in the format "NatSubnetX"
            });
        }

    }
}