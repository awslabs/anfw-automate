import { Stage, StageProps } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { VpcStack } from './vpc_stack';

interface VPCStageProps extends StageProps {
  namePrefix: string;
  stage: string;
  config: { [key: string]: any };
  globalConfig: { [key: string]: any };
  globalTags: { [key: string]: string };
}

export class VPCStage extends Stage {
  constructor(scope: Construct, id: string, props: VPCStageProps) {
    super(scope, id, props);

    new VpcStack(this, `vpc-${props.namePrefix}-${props.stage}`, {
      namePrefix: props.namePrefix,
      vpcCidr: props.config.vpc_cidr,
      cidrMasks: props.config.cidr_masks,
      availabilityZones: props.config.availability_zones,
      stage: props.stage,
      globalTags: props.globalTags,
    });
  }
}
