import { Aspects, Stage, StageProps, Tags } from "aws-cdk-lib";
import { Construct } from "constructs";
import { LambdaStack } from "./lambda_stack";
import { ServerlessStack } from "./serverless_stack";

interface LambdaStageProps extends StageProps {
    namePrefix: string;
    stage: string;
    config: { [key: string]: any };
    globalConfig: { [key: string]: any };
}

export class LambdaStage extends Stage {
    constructor(scope: Construct, id: string, props: LambdaStageProps) {
        super(scope, id, props);
        const lstack = new LambdaStack(this, `lambda-${props.namePrefix}-${props.stage}`, {
            namePrefix: props.namePrefix,
            vpcId: props.config.vpc_id,
            supportedRegions: props.config.supported_regions,
            policyArns: props.config.firewall_policy_arns,
            ruleOrder: props.config.rule_order,
            stage: props.stage,
        });
        Tags.of(lstack).add('Environment', `${props.stage}`);
    }
}

interface ServerlessStageProps extends StageProps {
    namePrefix: string;
    stage: string;
    config: { [key: string]: any };
    globalConfig: { [key: string]: any };
}

export class ServerlessStage extends Stage {
    constructor(scope: Construct, id: string, props: ServerlessStageProps) {
        super(scope, id, props);

        new ServerlessStack(this, `serverless-${props.namePrefix}-${props.stage}`, {
            namePrefix: props.namePrefix,
            vpcId: props.config.vpc_id,
            organizationIds: props.globalConfig.base.organziation_ids,
            stage: props.stage,
        });

    }
}