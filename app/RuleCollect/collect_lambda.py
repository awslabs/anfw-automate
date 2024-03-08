"""Collect Lambda - Gets the config from a S3. Triggered by event."""

# This file is part of anfw-automate. See LICENSE file for license information.

import os
import urllib.parse
import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.logging import correlation_paths
from botocore.config import Config
from lib.rule_config import ConfigEntry
from lib.log_handler import CustomerLogHandler, Level
from event_handler import EventHandler

logger = Logger()
tracer = Tracer()


# used the EventBridge correlation ID function decorator
@logger.inject_lambda_context(
    correlation_id_path=correlation_paths.EVENT_BRIDGE, log_event=True
)
@tracer.capture_lambda_handler
def handler(event, context):
    """Handler call from trigger."""
    logger.debug(f"Event Received:{event}")
    logger.debug("Loading RuleCollect function")
    lambda_region = os.getenv("LAMBDA_REGION", "eu-west-1")
    queue_name = os.getenv("QUEUE_NAME", "RuleCache.fifo")
    s3_assume_role = f'{os.getenv("XACCOUNT_ROLE")}'
    log_group_name = f'cw-{os.getenv("NAME_PREFIX")}-CustomerLog-{os.getenv("STAGE")}'
    logger.debug(
        f"Function executed with environment variables:"
        f"LAMBDA_REGION={lambda_region};FIFO_QUEUE_NAME={queue_name};"
        f"CROSS_ACCOUNT_ROLE={s3_assume_role}"
    )

    # find the type of event source
    if "source" in event.keys():
        source = event["source"]

    # CloudTrail event for VPC deletion
    if source == "aws.ec2":
        rule_event = "DeleteVpc"
        vpc_id = event["detail"]["requestParameters"]["vpcId"]
        account = event["detail"]["recipientAccountId"]
        region = event["detail"]["awsRegion"]
        logger.info(f"VPC delete event detected from {vpc_id}")
        eh = EventHandler(version=vpc_id)
        config = Config(retries={"max_attempts": 10, "mode": "adaptive"})

        # Assume the cross-account role and get credentials
        credentials = eh.assume_role_for_s3(
            account=account,
            region=lambda_region,
            config=config,
            rolename=s3_assume_role,
        )

        # Logger INIT with unique version ID
        logger.structure_logs(append=True, version=vpc_id)
        customer_log_handler = CustomerLogHandler(
            log_group_name=log_group_name,
            version=vpc_id,
            credentials=credentials,
        )
        log_stream_name = customer_log_handler.generate_log_stream_name()

        # Process event and send rules to SQS
        logger.info(f"DeleteVpc event detected from {vpc_id}")
        customer_log_handler.send_log_message(
            log_stream_name,
            f"DeleteVpc event detected from {vpc_id}",
            level=Level.INFO,
        )

        # Add empty/dummy config entry because no more data is available
        dummy = ConfigEntry(
            vpc=vpc_id, account=account, region=region, version="delete"
        )
        eh.send_to_sqs(
            config=dummy,
            event_type=rule_event,
            region=lambda_region,
            queuename=queue_name,
            log_stream_name=log_stream_name,
        )

    # EventBridge for s3 events
    if source == "aws.s3":
        # Get the object from the event and read the file
        account = event["account"]
        bucket = event["detail"]["bucket"]["name"]
        version = urllib.parse.unquote_plus(
            event["detail"]["object"]["version-id"], encoding="utf-8"
        )
        eh = EventHandler(version=version)
        config = Config(retries={"max_attempts": 10, "mode": "adaptive"})

        # Assume the cross-account role and get credentials
        credentials = eh.assume_role_for_s3(
            account=account,
            region=lambda_region,
            config=config,
            rolename=s3_assume_role,
        )

        # Logger INIT with unique version ID
        logger.structure_logs(append=True, version=version)
        customer_log_handler = CustomerLogHandler(
            log_group_name=log_group_name,
            version=version,
            credentials=credentials,
        )
        log_stream_name = customer_log_handler.generate_log_stream_name()

        logger.info(f"S3 event detected from {bucket}")
        customer_log_handler.send_log_message(
            log_stream_name,
            f"S3 event detected from {bucket}",
            level=Level.INFO,
        )
        event_type = event["detail"]["reason"]
        key = urllib.parse.unquote_plus(
            event["detail"]["object"]["key"], encoding="utf-8"
        )
        logger.info(f"Processing object: {key}")
        customer_log_handler.send_log_message(
            log_stream_name,
            f"Processing object: {key}",
            level=Level.INFO,
        )

        if eh.validate_file_name(input=key):
            # Get Region name of file name
            try:
                region = eh.get_region_from_string(key)
            except EventHandler.FormatError as fe:
                customer_log_handler.send_log_message(
                    log_stream_name,
                    fe,
                    level=Level.ERROR,
                )
                raise

            logger.debug(f"Processing rules for Account {account} in region {region}")
            customer_log_handler.send_log_message(
                log_stream_name,
                f"Processing rules for Account {account} in region {region}",
                level=Level.INFO,
            )

            # create client with assumed role
            try:
                s3 = boto3.client(
                    service_name="s3",
                    aws_access_key_id=credentials["AccessKeyId"],
                    aws_secret_access_key=credentials["SecretAccessKey"],
                    aws_session_token=credentials["SessionToken"],
                )
                logger.debug(f"Got S3 boto client for account {account}")
            except Exception as e:
                logger.critical(
                    f"Failed to get S3 boto client for account {account}: {e}"
                )
                customer_log_handler.send_log_message(
                    log_stream_name,
                    f"Please Contact Support: Unable to process rules for {account}.",
                    level=Level.ERROR,
                )
                raise

            # Possible events = Update, DeleteVpc, DeleteAccount, DeleteS3
            rule_event: str = ""
            rules: list = []
            if event_type == "DeleteObject":
                rule_event = "DeleteS3"
                # Add empty/dummy config entry because no more data is available
                rules.append(
                    ConfigEntry(
                        vpc="", account=account, region=region, version="delete"
                    )
                )
                customer_log_handler.send_log_message(
                    log_stream_name,
                    f"All rules for {account} in {region} will be deleted",
                    level=Level.INFO,
                )

            if event_type == "PutObject":
                rule_event = "Update"
                response = s3.get_object(Bucket=bucket, Key=key)
                data = response["Body"].read()
                logger.debug(f"Response Data: {data}")
                try:
                    rules, skipped_vpc = eh.get_policy_document(
                        data, account, region, credentials, key
                    )
                    logger.debug(f"Got policy document rules {rules}")
                    logger.debug(f"Fetched Rules {rules}")
                    if skipped_vpc:
                        for vpc in skipped_vpc:
                            customer_log_handler.send_log_message(
                                log_stream_name,
                                f"{vpc} rules skipped as it is not attached to TGW",
                                level=Level.WARN,
                            )
                except EventHandler.FormatError as fe:
                    customer_log_handler.send_log_message(
                        log_stream_name,
                        f"Invalid Format: {fe}",
                        level=Level.ERROR,
                    )
                    raise
                except EventHandler.InternalError as ie:
                    customer_log_handler.send_log_message(
                        log_stream_name,
                        f"Please Contact Support:{ie}",
                        level=Level.ERROR,
                    )
                    raise

            for rule in rules:
                eh.send_to_sqs(
                    config=rule,
                    event_type=rule_event,
                    region=lambda_region,
                    queuename=queue_name,
                    log_stream_name=log_stream_name,
                )
        else:
            logger.warn(
                f"Filename {key} not complaint with <region>-config.yaml pattern"
            )
            customer_log_handler.send_log_message(
                log_stream_name,
                f"Filename {key} dot complaint with <region>-config.yaml pattern.",
                level=Level.ERROR,
            )
    logger.info("Lambda execution done.")
    customer_log_handler.send_log_message(
        log_stream_name,
        f"All rules processed and sent to SQS for execution.",
        level=Level.INFO,
    )
