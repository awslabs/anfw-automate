import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';

export interface TaggedStackProps extends cdk.StackProps {
    stage: string;
}

export class TaggedStack extends cdk.Stack {
    constructor(scope: Construct, id: string, props: TaggedStackProps) {
        super(scope, id, props);

        // Add tags to the stack
        cdk.Tags.of(this).add('Environment', props.stage);
        cdk.Tags.of(this).add('Environment2', props.stage);
    }
}
