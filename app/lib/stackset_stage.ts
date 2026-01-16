import { Stage, StageProps } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { StacksetStack } from './stackset_stack';

interface StacksetStageProps extends StageProps {
  namePrefix: string;
  stage: string;
  config: { [key: string]: any };
  globalConfig: { [key: string]: any };
  globalTags: { [key: string]: string };
}

export class StacksetStage extends Stage {
  constructor(scope: Construct, id: string, props: StacksetStageProps) {
    super(scope, id, props);

    new StacksetStack(this, `stackset-${props.namePrefix}-${props.stage}`, {
      namePrefix: props.namePrefix,
      stage: props.stage,
      targetAccountId: props.globalConfig.base.target_account_id,
      deployRegions: props.config.stack_regions,
      permissionModel: props.config.permission_model,
      autoDeployment: props.config.auto_deployment,
      accountFilterType: props.config.account_filter_type,
      failureTolerancePercentage: props.config.failure_tolerance_percentage,
      maxConcurrentPercentage: props.config.max_concurrent_percentage,
      regionConcurrencyType: props.config.region_concurrency_type,
      callAs: props.config.call_as,
      ...(props.config.accounts ? { accounts: props.config.accounts } : {}),
      ...(props.config.organizational_unit_ids
        ? { organizationalUnitIds: props.config.organizational_unit_ids }
        : {}),
      globalTags: props.globalTags,
    });
  }
}
