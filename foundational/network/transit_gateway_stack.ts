import { Construct } from 'constructs';
import { CfnOutput } from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as ram from 'aws-cdk-lib/aws-ram';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import { TaggedStack, TaggedStackProps } from '../../shared/lib/tagged_stack';

export interface TransitGatewayStackProps extends TaggedStackProps {
  namePrefix: string;
  /**
   * AWS account ids the shared Transit Gateway is RAM-shared to
   * (e.g. the firewall and INT accounts). The owning (network) account does
   * not need to be listed.
   */
  sharePrincipals: string[];
}

/**
 * Shared-once network hub. Deployed a single time in the network/TGW account
 * (NOT per stage, NOT by the per-region loop in bin/foundational.ts). It:
 *   1. creates the org-wide Transit Gateway,
 *   2. RAM-shares it to the firewall + INT accounts, and
 *   3. publishes the TGW id to a shared SSM parameter that every downstream
 *      stack (per-stage foundational fabric, INT tenant tier) resolves.
 *
 * The published parameter `/anfw-automate/shared/tgw-id` is the handle the
 * int-environment spec consumes (its Req 2.1 / Phase B1).
 */
export class TransitGatewayStack extends TaggedStack {
  constructor(scope: Construct, id: string, props: TransitGatewayStackProps) {
    super(scope, id, props);

    const { namePrefix, stage, sharePrincipals } = props;

    // 1. Org-wide Transit Gateway (default RT association + propagation on, as the
    //    INT/prod spoke topology expects).
    const tgw = new ec2.CfnTransitGateway(this, 'TransitGateway', {
      description: `${namePrefix} shared transit gateway`,
      autoAcceptSharedAttachments: 'enable',
      defaultRouteTableAssociation: 'enable',
      defaultRouteTablePropagation: 'enable',
      dnsSupport: 'enable',
      tags: [{ key: 'Name', value: `tgw-${namePrefix}-shared` }],
    });

    // 2. RAM-share to the consuming accounts (firewall + INT).
    new ram.CfnResourceShare(this, 'TransitGatewayShare', {
      name: `ram-${namePrefix}-tgw-shared`,
      allowExternalPrincipals: false,
      resourceArns: [
        `arn:aws:ec2:${this.region}:${this.account}:transit-gateway/${tgw.ref}`,
      ],
      principals: sharePrincipals,
    });

    // 3. Publish the TGW id for cross-account consumers via shared SSM parameter.
    new ssm.StringParameter(this, 'TransitGatewayIdParam', {
      parameterName: '/anfw-automate/shared/tgw-id',
      stringValue: tgw.ref,
    });

    new CfnOutput(this, 'TransitGatewayId', {
      description: 'Shared Transit Gateway id',
      exportName: `tgw-id-${stage}`,
      value: tgw.ref,
    });
  }
}
