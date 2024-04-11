# Automate AWS Network Firewall Rule Management

An event-based serverless application that automatically performs CRUD operations on AWS Network Firewall rule-groups and rules based on distributed configuration files. The application consist of three modules:

1. VPC (Optional)
Creates VPC based on `vpc.json` config using AWS CodePipeline. Not required if you already have existing VPC in AWS Network Firewall and Application deployment. VPC for Application is only required if you want to run AWS Lambda Functions inside a VPC.

2. Firewall (Optional)
Creates AWS Network Firewall endpoints, and updates the routing tables of VPCs as configured in `firewall.json`. This requires Transit Gateway to be configured for the account and already attached to the AWS Network Firewall VPC. Not required, if you have existing AWS Network Firewall Setup.

3. Application
Creates a event-based serverless application that updates the rules and rule-groups attached to the AWS Network Firewall managed by the application. The rules are must be maintained in application managed S3 buckets. There is no limit on number of distributed configurations. The deployment is based on the configurations defined in `app.json`.

NOTE: Application makes cross-region API calls so it is not needed to deploy it in all the regions used by AWS Network Firewall. Pick a primary region to deploy the Application and save costs.

The Application module has one optional sub-module "StackSets". The Stacksets are only required if you want to automate the resource management in spoke accounts, i.e. accounts that hold the configuration files. It uses delegated admin for AWS Cloudformation to deploy those stacksets. You can also deploy the stack manually for testing using the Cloudformation template in `templates/spoke-serverless-stack.yaml`. If you wish to use delegated admin AWS Account with Stacksets please configure necessary parameters in `stackset.json`

NOTE: All the modules above are deployed using dedicated cross-account CICD pipelines (AWS CodePipeline) hosted in Resource Account. 

## PRE-REQUISITES

* Atleast two AWS Accounts are required as follows: 
    * Application Account - to deploy application. This is same account where AWS Network Firewall is deployed.
    * Resource Account - to deploy CICD pipeline for application deployment
* Other optional AWS Accounts are required depending upon your setup:
    * Delegated Admin Account - to managed spoke account using StackSets
    * Spoke Account - to test the application

## DEPLOYMENT

### PREPARE

* Install npm
* Create `deploy_vars.sh` in root of repository using following template. Not all paramters are required, please add/delete parameters based on you AWS Account Setup. 

NOTE: **STAGE** and **AWS_REGION** parameters are mandatory. The deployment loads configuration and names resources created by CDK all stacks using the `STAGE` variable. Consider the `STAGE` variable as representing your application environment i.e. dev, pre-prod, prod, etc. 

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
* Run `chmod a+x deploy_vars.sh && source deploy_vars.sh`

### CONFIGURE

* Create a file named `<STAGE>.json`  in `conf` folder matching the name of the `STAGE` variable. This configuration is the global configuration used by all the stacks.
* For every module you want to deploy, perform following steps:
    * change to module directory e.g. `cd app`
    * create a folder named `STAGE` in `conf` folder in-line with the explaination `STAGE` variable above.
    * Follow appropriate `schema.json` in respective `conf` folders to create the configuration files. Refer to Glossary to understand each parameters. e.g. create `vpc.json` in `<STAGE>` folder based on `conf/schemas/vpc.json`.
* Run `chmod a+x deploy_vars.sh && source deploy_vars.sh`

### BOOTSTRAP
* Login to all AWS Account of AWS profiles configured in deploy_vars.sh
* CDK Bootstrap Resource Account:

```
cdk bootstrap --profile $RES_ACCOUNT_AWS_PROFILE \
aws://${ACCOUNT_RES}/${AWS_REGION} \
--stack-name CDKToolkit-anfw  \
--qualifier anfw
```

* Bootstrap all other accounts to trust resource account (ACCOUNT_RES) as follows:

```
cdk bootstrap --profile $APP_ACCOUNT_AWS_PROFILE  \
--cloudformation-execution-policies arn:aws:iam::aws:policy/AdministratorAccess \
--trust ${ACCOUNT_RES} aws://${ACCOUNT_APP}/${AWS_REGION} \
--stack-name CDKToolkit-anfw  \
--qualifier anfw
```

NOTE: Bootstrap all the regions you wish to deploy the solution, either AWS Network Firewall or Application or both modules.

### DEPLOY
* Run `make deploy` in module folder

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

| Package                | Version     |
| ---------------------- | ----------- |
| aws-lambda-powertools | ^2.25.1      |
| aws-xray-sdk           | ^2.12.0      |
| jsonschema             | ^4.19.1      |
| python                 | ^3.11        |
| pyyaml                 | ^6.0.1       |
| requests               | ^2.31.0      |
| pytest                 | ^8.0.2       |
| bandit                 | ^1.7.7       |
| pip-audit              | ^2.7.2       |
| pip-licenses           | ^4.3.4       |
| cfnresponse           | ^1.1.2       |

### Typescript dependencies

| Package                             | Version               |
| ----------------------------------- | --------------------- |
| @types/jest                         | ^29.5.4               |
| @types/node                         | 20.5.7                |
| jest                                | ^29.6.4               |
| ts-jest                             | ^29.1.1               |
| ts-node                             | ^10.9.1               |
| typescript                          | ~5.2.2                |
| @aws-cdk/aws-lambda-python-alpha    | ^2.128.0-alpha.0      |
| ajv                                 | ^8.12.0               |
| ajv-formats                         | ^2.1.1                |
| aws-cdk                             | ^2.128.0              |
| aws-cdk-lib                         | ^2.128.0              |
| cdk-nag                             | ^2.28.41              |
| fs                                  | ^0.0.2                |
| source-map-support                  | ^0.5.21               |

## APPENDIX

Please refer the [GLOSSARY](GLOSSARY.md) before creating any configuration files

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This project is licensed under the Apache-2.0 License.
