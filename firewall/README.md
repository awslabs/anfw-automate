# Automate AWS Network Firewall Rule Management (Firewall Module)

Firewall module deploys AWS Network Firewall to existing VPC in
[central deployment model](https://aws.amazon.com/blogs/networking-and-content-delivery/deployment-models-for-aws-network-firewall/).
This optional module is only required if you don't have existing AWS Network
Firewall.

Deployment of the firewall module utilizes a cross-account CI/CD pipeline (AWS
CodePipeline) hosted in the Resource Account.

## PRE-REQUISITES

- **Node.js 20.8.1+** and **Yarn 4.0.0+** (install with `corepack enable`)
- **Python 3.11+** for Lambda functions
- At least two AWS Accounts are required as follows:
  - Application Account - to deploy application. This is same account where AWS
    Network Firewall is deployed.
  - Resource Account - to deploy CICD pipeline for application deployment

> **Note:** Before proceeding ensure that Transit Gateway is configured for the
> Application account and already attached to the VPC used for AWS Network
> Firewall deployment.

## DEPLOYMENT

### PREPARE

- Ensure that you completed the steps in `PREPARE` section of
  [README](../README.md)
- Install dependencies: `yarn install` (from project root)

## CONFIGURATION

### Enhanced Configuration Management

The firewall module now uses an enhanced configuration management system that
provides:

- **Multiple Configuration Sources**: SSM Parameter Store (primary) and JSON
  files (fallback)
- **Schema Validation**: Comprehensive validation with detailed error messages
- **Environment Overrides**: Environment-specific configuration merging
- **Error Handling**: Clear, actionable error messages for troubleshooting

#### Configuration Sources

The system supports multiple configuration sources with automatic fallback:

1. **SSM Parameter Store** (Primary)
   - Global: `/anfw-automate/{stage}/global/config`
   - Firewall module: `/anfw-automate/{stage}/firewall/config`
   - Overrides: `/anfw-automate/{stage}/firewall/overrides`

2. **JSON Files** (Fallback)
   - Global: `conf/{stage}.json`
   - Firewall module: `firewall/conf/{stage}.json`
   - Overrides: `firewall/conf/{stage}-overrides.json`

**Credential Handling**: The system gracefully handles AWS credential errors by
automatically falling back to file-based configuration for local development.

### CONFIGURE

- Change to module directory e.g. `cd firewall`
- Create a file named `<STAGE>.json` in [conf](conf/) folder in-line with the
  explanation `STAGE` variable so far.
- Follow appropriate `schema.json` in **conf** folder to create the
  configuration files. Refer the [GLOSSARY](../GLOSSARY.md) to understand each
  parameter. e.g. create `dev.json` in `conf` folder based on
  `conf/schema.json`.
- **Schema Validation**: The system automatically validates your configuration
  against the schema and provides detailed error messages for any issues.
- **Environment Overrides**: You can create environment-specific override files
  (e.g., `firewall/conf/dev-overrides.json`) that will be automatically merged
  with the base configuration.
- Run `chmod a+x deploy_vars.sh && source deploy_vars.sh`

### BOOTSTRAP

- Login to all AWS Account of AWS profiles configured in _PREPARE_ section of
  README(../README.md)
- CDK Bootstrap Resource Account:

```
cdk bootstrap --profile $RES_ACCOUNT_AWS_PROFILE \
aws://${ACCOUNT_RES}/${AWS_REGION} \
--stack-name CDKToolkit-anfw  \
--qualifier anfw
```

- Bootstrap all other accounts to trust resource account (ACCOUNT_RES) as
  follows:

```
cdk bootstrap --profile $APP_ACCOUNT_AWS_PROFILE  \
--cloudformation-execution-policies arn:aws:iam::aws:policy/AdministratorAccess \
--trust ${ACCOUNT_RES} aws://${ACCOUNT_APP}/${AWS_REGION} \
--stack-name CDKToolkit-anfw  \
--qualifier anfw
```

NOTE: Bootstrap all the regions you wish to deploy the solution, either AWS
Network Firewall or Application or both modules.

### DEPLOY

- Run `make deploy` from **firewall** folder

## DEPENDENCIES

This list of dependencies are needed to build the project. These packages are
not part of the solution.

### Python dependencies

| Package      | Version |
| ------------ | ------- |
| cfnresponse  | ^1.1.2  |
| python       | ^3.11   |
| bandit       | ^1.7.7  |
| pip-audit    | ^2.7.2  |
| pip-licenses | ^4.3.4  |
| pytest       | ^8.0.2  |

### Typescript dependencies

| Package                          | Version          |
| -------------------------------- | ---------------- |
| @types/jest                      | ^29.5.12         |
| @types/node                      | 20.11.30         |
| aws-cdk                          | 2.135.0          |
| jest                             | ^29.7.0          |
| ts-jest                          | ^29.1.2          |
| ts-node                          | ^10.9.2          |
| typescript                       | ~5.4.3           |
| @aws-cdk/aws-lambda-python-alpha | ^2.135.0-alpha.0 |
| aws-cdk-lib                      | 2.206.0          |
| cdk-nag                          | ^2.37.55         |
| constructs                       | ^10.0.0          |
| source-map-support               | ^0.5.21          |

## APPENDIX

Please refer the [GLOSSARY](../GLOSSARY.md) before creating any configuration
files

## Security

See [CONTRIBUTING](../CONTRIBUTING.md#security-issue-notifications) for more
information.

## License

This project is licensed under the Apache-2.0 License.
