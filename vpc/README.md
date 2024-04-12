# Automate AWS Network Firewall Rule Management (VPC Module)

VPC module deploys a sample VPC. This optional module is only required if you don't have existing VPC deployed to AWS Network Firewall account.

Deployment of the vpc module utilizes a cross-account CI/CD pipeline (AWS CodePipeline) hosted in the Resource Account.

## PRE-REQUISITES

* Atleast two AWS Accounts are required as follows: 
    * Application Account - to deploy VPC. This is same account where AWS Network Firewall and application is deployed.
    * Resource Account - to deploy CICD pipeline for application deployment

## DEPLOYMENT

### PREPARE

* Ensure that you completed the steps in `PREPARE` section of [README](../README.md) 

### CONFIGURE

* Create a file named `<STAGE>.json`  in [conf](../conf/) folder matching the name of the `STAGE` variable. This configuration is the global configuration used by all the stacks.
* change to module directory e.g. `cd vpc`
* Create a file named `<STAGE>.json` in `conf` folder in-line with the explaination `STAGE` variable so far.
* Follow appropriate `schema.json` in `conf` folder to create the configuration files. Refer the [GLOSSARY](../GLOSSARY.md) to understand each parameter. e.g. create `dev.json` in `conf` folder based on `conf/schema.json`.
* Run `chmod a+x deploy_vars.sh && source deploy_vars.sh`

### DEPLOY
* Ensure that BOOTSTRAP section of [README](../README.md) is completed.
* Run `make deploy` in module folder
* Manully attach the VPC to appropriate Transit Gateway to ensure communication between spoke and AWS Network Firewall accounts.

## DEPENDENCIES

This list of dependencies are needed to build the project.
These packages are not part of the solution.

### Typescript dependencies

| Package          | Version    |
|------------------|------------|
| @types/jest      | ^29.5.12   |
| @types/node      | 20.11.30   |
| aws-cdk          | 2.135.0    |
| jest             | ^29.7.0    |
| ts-jest          | ^29.1.2    |
| ts-node          | ^10.9.2    |
| typescript       | ~5.4.3     |
| aws-cdk-lib      | 2.135.0    |
| cdk-nag          | ^2.28.82   |
| constructs       | ^10.0.0    |
| source-map-support | ^0.5.21  |

## APPENDIX

Please refer the [GLOSSARY](../GLOSSARY.md) before creating any configuration files

## Security

See [CONTRIBUTING](../CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This project is licensed under the Apache-2.0 License.
