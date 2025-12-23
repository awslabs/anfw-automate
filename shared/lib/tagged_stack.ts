import { Stack, StackProps, Tags } from 'aws-cdk-lib';
import { Construct } from 'constructs';

export interface TaggedStackProps extends StackProps {
  stage: string;
  globalTags: Record<string, string>;
}

export abstract class TaggedStack extends Stack {
  protected readonly stage: string;
  protected readonly globalTags: Record<string, string>;

  constructor(scope: Construct, id: string, props: TaggedStackProps) {
    super(scope, id, props);

    this.stage = props.stage;
    this.globalTags = props.globalTags;

    this.applyGlobalTags();
  }

  private applyGlobalTags(): void {
    for (const [key, value] of Object.entries(this.globalTags)) {
      this.addStackTag(key, value); // Use public method
    }

    this.addStackTag('Environment', this.stage);
  }

  // ✅ Public methods required by CDK Nag
  public addStackTag(key: string, value: string): void {
    Tags.of(this).add(key, value);
  }

  public removeStackTag(key: string): void {
    Tags.of(this).remove(key);
  }
}
