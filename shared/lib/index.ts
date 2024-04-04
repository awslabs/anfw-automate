// import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
// import * as sqs from 'aws-cdk-lib/aws-sqs';

export interface SharedProps {
  // Define construct properties here
}

export class Shared extends Construct {

  constructor(scope: Construct, id: string, props: SharedProps = {}) {
    super(scope, id);

    // Define construct contents here

    // example resource
    // const queue = new sqs.Queue(this, 'SharedQueue', {
    //   visibilityTimeout: cdk.Duration.seconds(300)
    // });
  }
}
