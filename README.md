# Automate AWS Network Firewall Rule Management

An event-based serverless application that automatically performs CRUD operations on AWS Network Firewall rule-groups and rules based on distributed configuration files. The application consist of three modules:

1. VPC (Optional)
Creates VPC based on configuration using AWS CodePipeline. Not required if you already have existing VPC in AWS Network Firewall and Application account.

2. Firewall (Optional)
Creates AWS Network Firewall endpoints, and updates the routing tables of VPCs as configured. This requires Transit Gateway to be configured for the account and already attached to the AWS Network Firewall VPC. Not required, if you have existing AWS Network Firewall Setup.

3. Application
Creates a event-based serverless application that updates the rules and rule-groups attached to the AWS Network Firewall managed by the application. The rules are must be maintained in application managed S3 buckets. There is no limit on number of distributed configurations. The deployment is based on the configurations.

## PRE-REQUISITES
* Atleast two AWS Accounts are required as follows: 
    * Application Account (Dev)- to deploy any of the modules above in development environment. 
    * Resource Account - to deploy CICD pipeline for application deployment

> **NOTE:** Please add more Application accounts per environment to ensure appropriate resource isolation

* Other optional AWS Accounts are required depending upon your setup:
    * Delegated Admin Account - to managed spoke account using StackSets
    * Spoke Account - to test the application by mocking customer with distributed AWS Network Firewall configuration.

## DEPLOYMENT

### PREPARE

* Install npm
* Create `deploy_vars.sh` in root of repository using following template. Not all paramters are required, please add/delete parameters based on your AWS Account Setup. 

> **NOTE:** *STAGE* and *AWS_REGION* parameters are mandatory. The deployment loads configuration and names resources created by all CDK stacks using these variable. Consider the `STAGE` variable as representing your application environment i.e. dev, pre-prod, prod, etc. 

```
#!/bin/bash
# Resource Account configuration
export ACCOUNT_RES=111122223333;
export RES_ACCOUNT_AWS_PROFILE=deployer+res;

# Prod Application Account configuration
export ACCOUNT_PROD=222233334444;
export PROD_ACCOUNT_AWS_PROFILE=deployer+app;

# Delegated Admin Account configuration
export ACCOUNT_DELEGATED_ADMIN=333344445555;
export DELEGATED_ADMIN_ACCOUNT_AWS_PROFILE=admin+dadmin;

# Configure deployment
export AWS_PROFILE=${RES_ACCOUNT_AWS_PROFILE}
export STAGE=xxx
export AWS_REGION=xx-yyyy-1
```
* Create a file named `<STAGE>.json`  in [conf](../conf/) folder matching the name of the `STAGE` variable. This configuration is the global configuration used by all the stacks.

### DEPLOY
Proceed to deploy the necessary modules by following their respecitve README sections:
* [app](app/README.md)
* [firewall](firewall/README.md)
* [vpc](vpc/README.md)

#### Other Useful commands
* `npm run build`   compile typescript to js
* `npm run watch`   watch for changes and compile
* `npm run test`    perform the jest unit tests
* `cdk deploy`      deploy this stack to your default AWS account/region
* `cdk diff`        compare deployed stack with current state
* `cdk synth`       emits the synthesized CloudFormation template


## DEPENDENCIES

This list of dependencies are needed to build the project.
These packages are not part of the solution.

### Python dependencies

| Package                | Version  |
|------------------------|----------|
| aws-lambda-powertools | ^2.25.1  |
| aws-xray-sdk           | ^2.12.0  |
| jsonschema             | ^4.19.1  |
| python                 | ^3.11    |
| pyyaml                 | ^6.0.1   |
| requests               | ^2.31.0  |
| pytest                 | ^8.0.2   |
| bandit                 | ^1.7.7   |
| pip-audit              | ^2.7.2   |
| pip-licenses           | ^4.3.4   |
| boto3                  | ^1.34.52 |
| cfnresponse            | ^1.1.2   |

### Typescript dependencies

| Package                           | Version       |
|-----------------------------------|---------------|
| @types/jest                       | ^29.5.12      |
| @types/node                       | 20.11.30      |
| aws-cdk                           | 2.135.0       |
| jest                              | ^29.7.0       |
| ts-jest                           | ^29.1.2       |
| ts-node                           | ^10.9.2       |
| typescript                        | ~5.4.3        |
| @aws-cdk/aws-lambda-python-alpha | ^2.135.0-alpha.0 |
| aws-cdk-lib                       | 2.135.0       |
| cdk-nag                           | ^2.28.82      |
| constructs                        | ^10.0.0       |
| source-map-support                | ^0.5.21       |
| ajv                               | ^8.12.0       |
| ajv-formats                       | ^3.0.1        |

## APPENDIX

Please refer the [GLOSSARY](GLOSSARY.md) before creating any configuration files

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This project is licensed under the Apache-2.0 License.
