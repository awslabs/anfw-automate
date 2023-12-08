"""Log Handler for CloudWacht Logs."""

# This file is part of anfw-automate. See LICENSE file for license information.

import re
import boto3
import yaml
from aws_lambda_powertools import Logger, Tracer
from jsonschema import validate, ValidationError
from botocore.config import Config
from lib.rule_config import ConfigEntry


class EventHandler:
    """Process and validate the events"""

    def __init__(
        self,
        version: str = None,  # Default value set to None if not provided
    ) -> None:
        self.logger = Logger(child=True)
        self.version = version

    def get_region_from_string(self, object_key: str) -> str:
        """Takes the file name returns the region in the name"""
        regex = rf"(us(-gov)?|ap|ca|cn|eu|sa)-(central|(north|south)?(east|west)?)-\d"
        matches = re.search(regex, object_key)
        try:
            return matches[0]
        except Exception as e:
            self.logger.warn(f"Invalid AWS Region name in filename {object_key}: {e}")
            raise self.FormatError(f"Invalid AWS Region name in filename: {object_key}")

    def validate_file_name(self, input: str) -> bool:
        """Takes the filename/key and validates if <region>-config.yaml"""
        regex = rf"((us(-gov)?|ap|ca|cn|eu|sa)-(central|(north|south)?(east|west)?)-\d)-config.(yaml|yml)"
        matches = re.search(regex, input)
        # If name fetch with thr regex
        if matches is not None:
            return True
        else:
            return False

    def assume_role_for_s3(
        self, account: str, region: str, config: object, rolename: str
    ) -> dict:
        """Request STS token for special access role.

        :returns: dict - credentials for the temporary role session"""
        try:
            sts_client = boto3.client("sts", region_name=region, config=config)
            self.logger.debug(f"Got STS client object back {str(sts_client)}")

            s3_assume_role_arn = f"arn:aws:iam::{account}:role/{rolename}"

            assumed_role_object = sts_client.assume_role(
                RoleArn=s3_assume_role_arn,
                RoleSessionName="CollectLambdaRuleAssumption",
            )
            self.logger.debug(
                f"Got credentials for  {s3_assume_role_arn} in account {account}"
            )
            return assumed_role_object["Credentials"]
        except Exception as e:
            self.logger.critical(
                f"Failed to get credentials for role {s3_assume_role_arn} in account {account}: {e}"
            )
            raise e

    def _is_vpc_attached_to_transit_gateway(self, client: object, vpc_id: str) -> bool:
        """Request Transit Gateway Attachment IDs for VPC ID

        :returns: bool - True if transit gateway attachments are found"""
        attachments = []
        next_token = None

        # Retrieve all transit gateway attachments using paginated API calls
        while True:
            try:
                params = {
                    "Filters": [
                        {"Name": "resource-id", "Values": [vpc_id]},
                    ]
                }

                if next_token:
                    params["NextToken"] = next_token

                response = client.describe_transit_gateway_attachments(**params)
                attachments.extend(response.get("TransitGatewayAttachments", []))

                # Check if there are more pages of results
                next_token = response.get("NextToken")
                if not next_token:
                    break
            except Exception as e:
                raise e

        # Check if the VPC is attached to the Transit Gateway
        return True if len(attachments) > 0 else False

    # @tracer.capture_method
    def get_policy_document(
        self, doc: str, account: str, region: str, credentials: dict, key: str
    ) -> list:
        """Read and validates the policy document
        :returns: list - processed rules for complaint rules
        :throws: InternalError and FormatError if validation fails
        """

        policies: list = []
        skipped_vpc: list = []

        # Load schema file
        try:
            with open("schema.json", mode="r", encoding="utf-8") as f:
                schema = f.read()
            data: dict = yaml.safe_load(doc)
        except Exception as e:
            self.logger.critical(f"Error in Schema file format: {e}")
            raise self.InternalError(f"Failed to load schema validation file")

        # Validate config file strcuture with defined schema
        try:
            validate(data, yaml.safe_load(schema))
        except ValidationError as ve:
            self.logger.warn(f"Config file {key} not compliant with schema: {ve}")
            raise self.FormatError(f"Config file {key} not compliant with schema")
        except Exception as e:
            self.logger.critical(
                f"Internal Error Validating the config file {key}: {e}"
            )
            raise self.InternalError(f"Internal Error validating the config file {key}")

        # Get rules for each VPC policy
        for policy in data["Config"]:
            # Get the vpc CIDR with the assumed role
            try:
                ec2 = boto3.resource(
                    "ec2",
                    region_name=region,
                    aws_access_key_id=credentials["AccessKeyId"],
                    aws_secret_access_key=credentials["SecretAccessKey"],
                    aws_session_token=credentials["SessionToken"],
                )
                self.logger.debug(f"Got EC2 boto3 resource")

                ec2_client = boto3.client(
                    "ec2",
                    region_name=region,
                    aws_access_key_id=credentials["AccessKeyId"],
                    aws_secret_access_key=credentials["SecretAccessKey"],
                    aws_session_token=credentials["SessionToken"],
                )
                self.logger.debug(f"Got EC2 boto3 client")
            except Exception as e:
                self.logger.critical(f"Unable to get boto3 client or resource: {e}")
                raise self.InternalError(
                    f"Internal Error getting ec2 boto3 client or resource"
                )

            # Get VPC CIDR Block if VPC ID is valid
            try:
                vpc_id = policy["VPC"]
                vpc = ec2.Vpc(vpc_id)
                entry = ConfigEntry(vpc_id, account, region, data["Version"])
                entry.ip_set_space = vpc.cidr_block
                self.logger.debug(f"Got cidr block for {vpc_id}")
            except Exception as e:
                self.logger.warn(f"Invalid VPC id {vpc_id}: {e}")
                raise self.FormatError(f"Invalid VPC id {vpc_id}")

            # Generate rules only when VPC is attached to a Transit Gateway
            if self._is_vpc_attached_to_transit_gateway(ec2_client, vpc_id):
                self.logger.debug(f"Generating rules for VPC {vpc_id}")
                for prop in policy["Properties"]:
                    for rule in list(prop.values())[0]:
                        try:
                            rule_key = list(prop.keys())[0].lower()
                            self.logger.debug(f"rulekey: {rule_key}")
                            entry.add_rule_entry(
                                rule_key=rule_key,
                                rule=rule,
                            )
                        except ConfigEntry.FormatError as fe:
                            self.logger.warn(
                                f"Invalid format in rule {rule_key}:{rule} for {vpc_id}: {fe}"
                            )
                            raise self.FormatError(
                                f"Invalid format in rule {rule_key}:{rule} for {vpc_id}"
                            )
                        except ConfigEntry.NotSupportedProtocol as nse:
                            self.logger.warn(
                                f"Unsupported Protocol in rule {rule_key}:{rule} for {vpc_id}: {nse}"
                            )
                            raise self.FormatError(
                                f"Unsupported Protocol in rule {rule_key}:{rule} for {vpc_id}"
                            )
                        except Exception as e:
                            self.logger.critical(
                                f"Internal Error processing {rule_key}:{rule} for {vpc_id}: {e}"
                            )
                            raise self.InternalError(
                                f"Internal Error processing {rule_key}:{rule} for {vpc_id}"
                            )
                policies.append(entry)
            else:
                self.logger.debug(
                    f"Ignoring rules for {vpc_id} as it is not attached to TGW"
                )
                skipped_vpc.append(vpc_id)
        return policies, skipped_vpc

    # @tracer.capture_method
    def send_to_sqs(
        self,
        config: ConfigEntry,
        region: str,
        queuename: str,
        event_type: str,
        log_stream_name: str,
    ) -> None:
        """Send the ConfigEntry instance to SQS as message."""

        sqs = boto3.resource("sqs", region_name=region)
        queue = sqs.get_queue_by_name(QueueName=queuename)
        # get the object as json
        object_json = config.get_json()
        try:
            queue.send_message(
                MessageGroupId=config.account,
                MessageBody=object_json,
                MessageAttributes={
                    "Event": {"StringValue": event_type, "DataType": "String"},
                    "Account": {"StringValue": config.account, "DataType": "String"},
                    "Region": {"StringValue": config.region, "DataType": "String"},
                    "LogstreamName": {
                        "StringValue": log_stream_name,
                        "DataType": "String",
                    },
                    "Version": {"StringValue": self.version, "DataType": "String"},
                },
            )
            self.logger.info(
                f"Sent Rules to SQS for vpc-{config.vpc} in account {config.account}"
            )

        except Exception as e:
            self.logger.critical(f"Failed to send SQS message for processing: {e}")
            raise self.InternalError(f"Internal Error sending rules for processing")

    class InternalError(Exception):
        """Exception for unknown internal error"""

        pass

    class FormatError(Exception):
        """Exception for invalid format"""

        pass
