## `global.json`
Global configuration is used by all stacks and to control the deployment of optional stacks. Create a configuration file by referring the [JSON schema](conf/schemas/global.json), the [sample config](conf/sample/global.json) and, parameter glossary below.

| Parameter                       | Datatype         | Description                                               |
|---------------------------------|------------------|-----------------------------------------------------------|
| `aws_organziation_scope`        | String           | AWS organization scope code (e.g., "xx").                 |
| `brand`                         | String           | Brand identifier (e.g., "yy").                            |
| `department`                    | String           | Department identifier (e.g., "zzz").                      |
| `project_name`                  | String           | Name of the project (e.g., "anfw").                       |
| `module_name`                   | String           | Name of the module (e.g., "automate").                    |
| `primary_region`                | String           | Primary AWS region for the project (e.g., "eu-west-1").   |
| `target_account_id`             | String           | AWS Account ID for the target environment.                 |
| `resource_account_id`           | String           | AWS Account ID for the resource environment.               |
| `delegated_admin_account_id`    | String           | AWS Account ID for delegated admin responsibilities.      |
| `organziation_ids`              | List of Strings  | List of AWS organization IDs associated with the project.  |
| `codestar_connection_arn`       | String           | ARN of AWS CodeStar Connection for the pipeline.           |
| `repo_name`                     | String           | Name of the repository (e.g., "org/repo").                |
| `repo_branch_name`              | String           | Name of the repository branch (e.g., "branchx").          |
| `auto_promote_pipeline`         | Boolean          | Indicates whether the pipeline should auto-promote.       |
| `auto_detect_changes`           | Boolean          | Indicates whether the pipeline should auto-detect changes. |
| `vpc_regions`                   | List of Strings  | List of regions where VPC stacks are deployed.     |
| `firewall_regions`              | List of Strings  | List of regions where firewall stacks are deployed.     |
| `app_regions`                   | List of Strings  | List of regions where application stacks are deployed.  |
| `deploy_stacksets`              | Boolean          | Indicates whether to deploy AWS CloudFormation StackSets in application stack  |

## `app.json`
Application configuration is used to deploy application stacks. Create a configuration file by referring the [JSON schema](conf/schemas/app.json), the [sample config](conf/sample/app.json) and, parameter glossary below.

> You must define configuration for each region you want to deploy the application. Region name must be double-quoted for safe YAML parsing. e.g. `"eu-west-1"`

| Parameter               | Datatype              | Description                                               |
|-------------------------|-----------------------|-----------------------------------------------------------|
| `vpc_id`                | String                | Unique identifier for the Virtual Private Cloud (VPC).     |
| `vpc_cidr`              | String                | CIDR block assigned to the VPC (e.g., "10.1.0.0/24").      |
| `internal_network_cidrs`| String                | Comma-separated CIDR blocks for internal network ranges. (e.g., "10.0.0.0/8,11.0.0.0/8").  |
| `supported_regions`     | List of Strings       | List of AWS regions supported by the solution for rule updates. The region should existing AWS Network Firewall and policy            |

## `stackset.json`
Stackset configuration is used to contol stackset deployment in the Delegated Administrator Account. Create a configuration file by referring the [JSON schema](conf/schemas/firewall.json), the [sample config](conf/sample/firewall.json) and, parameter glossary below.

> You must define configuration for each region you want to deploy the stackset. The regions should match the regions configured in `app.json` and region name must be double-quoted for safe YAML parsing. e.g. `"eu-west-1"`

| Parameter                          | Datatype          | Description                                               |
|------------------------------------|-------------------|-----------------------------------------------------------|
| `permission_model`                 | String            | Permission model for stack deployment (currently only "SERVICE_MANAGED" is supported). |
| `auto_deployment`                  | Boolean           | Indicates whether auto-deployment is enabled.              |
| `account_filter_type`              | String            | [AccountFilterType](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/account-level-targets.html#accountfiltertype) Type of account filter (e.g. "NONE").                     |
| `organizational_unit_ids`          | List of Strings   | List of organizational unit IDs associated with the region.|
| `failure_tolerance_percentage`     | Integer           | Percentage of failure tolerance during deployments.        |
| `max_concurrent_percentage`        | Integer           | Maximum percentage of concurrent deployments.              |
| `region_concurrency_type`          | String            | Type of region concurrency (e.g., "PARALLEL").             |
| `call_as`                          | String            | Indicates the role used to make the stack calls (e.g., "DELEGATED_ADMIN"). |
| `stack_regions`                    | List of Strings   | List of regions where stacks can be deployed.              |

## `vpc.json`
VPC configuration is used to deploy VPC setup required for AWS Network Firewall in a [Centralized AWS Network Firewall deployment model](https://aws.amazon.com/blogs/networking-and-content-delivery/deployment-models-for-aws-network-firewall/). Create a configuration file by referring the [JSON schema](conf/schemas/vpc.json), the [sample config](conf/sample/vpc.json) and, parameter glossary below.

> You must define configuration for each region you want to deploy the AWS Network Firewall. Region name must be double-quoted for safe YAML parsing. e.g. `"eu-west-1"`

| Parameter                   | Datatype          | Description                                               |
|-----------------------------|-------------------|-----------------------------------------------------------|
| `vpc_cidr`                  | String            | CIDR block assigned to the VPC.                            |
| `availability_zones`        | Map of Strings    | Mapping of Availability Zone names to their identifiers.   |
| `cidr_masks`                | Map of Integers   | Mapping of CIDR masks for different components.            |

## `firewall.json`
Firewall configuration is used to deploy AWS Network Firewall stacks. Create a configuration file by referring the [JSON schema](conf/schemas/firewall.json), the [sample config](conf/sample/firewall.json) and, parameter glossary below.

> You must define configuration for each region you want to deploy the AWS Network Firewall. Region name must be double-quoted for safe YAML parsing. e.g. `"eu-west-1"`

| Parameter                  | Datatype          | Description                                               |
|----------------------------|-------------------|-----------------------------------------------------------|
| `vpc_id`                   | String            | Unique identifier for the Virtual Private Cloud (VPC).     |
| `vpc_cidr`                 | String            | CIDR block assigned to the VPC (e.g., "10.1.0.0/24").      |
| `multi_az`                 | Boolean           | Indicates whether the VPC spans multiple Availability Zones. |
| `internet_gateway_id`      | String            | Unique identifier for the Internet Gateway.                |
| `internal_network_cidrs`   | String            | Comma-separated CIDR blocks for internal network ranges.   |
| `transit_gateway`          | String            | Identifier for the Transit Gateway.                         |
| `availability_zones`       | Map of Strings    | Mapping of Availability Zone names to their identifiers.   |
| `subnet_ids`               | Map of Strings    | Mapping of subnet names to their identifiers.              |




