import { Aspects, Stage, StageProps, Tags } from "aws-cdk-lib";
import { Construct } from "constructs";
import { NetworkFirewallStack } from "./firewall_stack";
import { BaseRoutingStack } from "./base_routing_stack";
import { RoutingStack } from "./routing_stack";
import { NagSuppressions } from "cdk-nag";

interface FirewallStageProps extends StageProps {
    namePrefix: string;
    stage: string;
    config: { [key: string]: any; };
    globalConfig: { [key: string]: any; };
}

export class FirewallStage extends Stage {
    constructor(scope: Construct, id: string, props: FirewallStageProps) {
        super(scope, id, props);

        new NetworkFirewallStack(this, `firewall-${props.namePrefix}-${props.stage}`, {
            namePrefix: props.namePrefix,
            vpcId: props.config.vpc_id,
            subnetIds: props.config.subnet_ids,
            azIds: props.config.availability_zones,
            stage: props.stage,
            internalNet: props.config.internal_network_cidrs,
            ruleOrder: props.config.rule_order,
        });
    }
}

interface BaseRoutingProps extends StageProps {
    namePrefix: string;
    stage: string;
    config: { [key: string]: any; };
    globalConfig: { [key: string]: any; };
}

export class BaseRoutingStage extends Stage {
    constructor(scope: Construct, id: string, props: FirewallStageProps) {
        super(scope, id, props);
        new BaseRoutingStack(this, `base-routing-${props.namePrefix}-${props.stage}`, {
            namePrefix: props.namePrefix,
            vpcId: props.config.vpc_id,
            subnetIds: props.config.subnet_ids,
            azIds: props.config.availability_zones,
            stage: props.stage,
            vpcCidr: props.config.vpc_cidr,
            multiAz: props.config.multi_az,
            transitGateway: props.config.transit_gateway,
            internalNet: props.config.internal_network_cidrs
        });
    }
}

interface RoutingProps extends StageProps {
    namePrefix: string;
    stage: string;
    config: { [key: string]: any; };
    globalConfig: { [key: string]: any; };
}

export class RoutingStage extends Stage {
    constructor(scope: Construct, id: string, props: RoutingProps) {
        super(scope, id, props);
        new RoutingStack(this, `routing-${props.namePrefix}-${props.stage}`, {
            namePrefix: props.namePrefix,
            stage: props.stage,
            vpcId: props.config.vpc_id,
            vpcCidr: props.config.vpc_cidr,
            subnetIds: props.config.subnet_ids,
            azIds: props.config.availability_zones,
            multiAz: props.config.multi_az,
            transitGateway: props.config.transit_gateway,
            internalNet: props.config.internal_network_cidrs,
            internetGateway: props.config.internet_gateway_id
        });

    }
}

