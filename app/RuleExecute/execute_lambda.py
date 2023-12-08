"""Execute Lambda - Applies the AWS Network Firewall rule changes. Triggered by event."""

# This file is part of anfw-automate. See LICENSE file for license information.

import os
import boto3
from aws_lambda_powertools import Logger, Tracer
from firewall_handler import FirewallRuleHandler
from lib.log_handler import CustomerLogHandler, Level
from botocore.config import Config

logger = Logger()
tracer = Tracer()

# customer_log_s3 = os.getenv("CUSTOMER_LOG_S3")
logger.debug("Loading RuleExecute function")


@tracer.capture_method
def assume_role_for_s3(
    account: str, region: str, config: object, rolename: str
) -> dict:
    """Request STS token for special access role.

    :returns: dict - credentials for the temporary role session"""
    try:
        sts_client = boto3.client("sts", region_name=region, config=config)
        logger.debug(f"Got STS client object back {str(sts_client)}")

        s3_assume_role_arn = f"arn:aws:iam::{account}:role/{rolename}"

        assumed_role_object = sts_client.assume_role(
            RoleArn=s3_assume_role_arn,
            RoleSessionName="CollectLambdaRuleAssumption",
        )
        logger.debug(f"Got credentials for  {s3_assume_role_arn} in account {account}")
        return assumed_role_object["Credentials"]
    except Exception as e:
        logger.critical(
            f"Failed to get credentials for role {s3_assume_role_arn} in account {account}: {e}"
        )
        raise e


@logger.inject_lambda_context(log_event=True)
@tracer.capture_lambda_handler
def handler(event, context):
    """Handler call from trigger."""
    logger.info(f"Event received: {event}")
    lambda_region = os.getenv("LAMBDA_REGION", "eu-west-1")
    log_group_name = f'cw-{os.getenv("NAME_PREFIX")}-CustomerLog-{os.getenv("STAGE")}'
    s3_assume_role = f'{os.getenv("XACCOUNT_ROLE")}'

    for record in event["Records"]:
        # Get the messages from the SQS event and creates/deletes the rules.
        event_type = record["messageAttributes"]["Event"]["stringValue"]
        region = record["messageAttributes"]["Region"]["stringValue"]
        account = record["messageAttributes"]["Account"]["stringValue"]
        version = record["messageAttributes"]["Version"]["stringValue"]
        log_stream_name = record["messageAttributes"]["LogstreamName"]["stringValue"]

        config = Config(retries={"max_attempts": 10, "mode": "adaptive"})
        # Assume the cross-account role and get credentials
        credentials = assume_role_for_s3(
            account=account,
            region=lambda_region,
            config=config,
            rolename=s3_assume_role,
        )

        # Logger INIT with unqiue ID
        logger.structure_logs(append=True, version=version)
        customer_log_handler = CustomerLogHandler(
            log_group_name=log_group_name,
            version=version,
            credentials=credentials,
        )

        fw = FirewallRuleHandler(region, context, customer_log_handler, log_stream_name)

        logger.info(f"Started processing rules for {account} in {region}")
        customer_log_handler.send_log_message(
            log_stream_name,
            f"Started processing rules for {account} in {region}",
            level=Level.INFO,
        )

        fw.json_to_rule(record["body"], event_type=event_type)
        fw.create_reserved_rule_group()
        logger.info(f"Rules processed successfully for {account} in {region}")
        customer_log_handler.send_log_message(
            log_stream_name,
            f"Rules processed successfully for {account} in {region}",
            level=Level.INFO,
        )
