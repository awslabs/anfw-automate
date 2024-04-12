# Automate AWS Network Firewall Rule Management (Application Module)

This event-driven, serverless application automates CRUD operations on AWS Network Firewall rule-groups and rules using configuration files. It updates rules and rule-groups on the AWS Network Firewall managed by the application, pulling configurations from application-managed S3 buckets. There's no limit on the number of distributed configurations. Deployment is based on the configurations detailed below.

> **Note:** The application makes cross-region API calls, eliminating the need for deployment in all regions where AWS Network Firewall is used. Choose a primary region for deployment to optimize costs.

The optional "StackSets" submodule is necessary only if automating resource management in spoke accounts (those holding configuration files). It leverages delegated admin for AWS CloudFormation to deploy these stacksets. Alternatively, you can manually deploy the stack or use other enterprise modules with the provided CloudFormation template (`templates/spoke-serverless-stack.yaml`). To test the solution without a delegated administrator account, manual deployment of the CloudFormation template is available. Configure necessary parameters in configuration files if using a delegated admin AWS Account with StackSets.

Deployment of the application module utilizes a cross-account CI/CD pipeline (AWS CodePipeline) hosted in the Resource Account.
## PRE-REQUISITES

* Atleast two AWS Accounts are required as follows: 
    * Application Account - to deploy application. This is same account where AWS Network Firewall is deployed.
    * Resource Account - to deploy CICD pipeline for application deployment
* Other optional AWS Accounts are required depending upon your setup:
    * Delegated Admin Account - to managed spoke account using StackSets
    * Spoke Account - to test the application

## DEPLOYMENT

### PREPARE

* Ensure that you completed the steps in `PREPARE` section of [README](../README.md) 

### CONFIGURE

* Create a file named `<STAGE>.json`  in [conf](../conf/) folder matching the name of the `STAGE` variable. This configuration is the global configuration used by all the stacks.
* change to module directory e.g. `cd app`
* Create a file named `<STAGE>.json` in `conf` folder in-line with the explaination `STAGE` variable so far.
* Follow appropriate `schema.json` in `conf` folder to create the configuration files. Refer the [GLOSSARY](../GLOSSARY.md) to understand each parameter. e.g. create `dev.json` in `conf` folder based on `conf/schema.json`.
* Run `chmod a+x deploy_vars.sh && source deploy_vars.sh`

### DEPLOY
* Ensure that BOOTSTRAP section of [README](../README.md) is completed.
* Run `make deploy` in module folder

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

### Typescript dependencies

| Package                           | Version         |
|-----------------------------------|-----------------|
| @types/jest                       | ^29.5.12        |
| @types/node                       | 20.11.30        |
| aws-cdk                           | 2.135.0         |
| jest                              | ^29.7.0         |
| ts-jest                           | ^29.1.2         |
| ts-node                           | ^10.9.2         |
| typescript                        | ~5.4.3          |
| @aws-cdk/aws-lambda-python-alpha | ^2.135.0-alpha.0 |
| aws-cdk-lib                       | 2.135.0         |
| cdk-nag                           | ^2.28.82        |
| constructs                        | ^10.0.0         |
| source-map-support                | ^0.5.21         |

## APPENDIX

Please refer the [GLOSSARY](../GLOSSARY.md) before creating any configuration files

## Security

See [CONTRIBUTING](../CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This project is licensed under the Apache-2.0 License.
