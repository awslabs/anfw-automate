import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';

export interface TaggedStackProps extends cdk.StackProps {
    stage: string;
    globalTags: { [key: string]: string };
}

export class TaggedStack extends cdk.Stack {
    constructor(scope: Construct, id: string, props: TaggedStackProps) {
        super(scope, id, props);

        //Apply user tags
        Object.entries(props.globalTags).forEach(([key, value]) => {
            cdk.Tags.of(this).add(`${key}`, `${value}`);
        });

        // Add Environent tag to the stack
        cdk.Tags.of(this).add('Environment', props.stage);
    }
}
