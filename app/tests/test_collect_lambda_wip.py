import datetime
import io
from typing import Any
import os
import json
import yaml
from RuleCollect.collect_lambda import handler
from RuleCollect.event_handler import EventHandler

import unittest
from unittest.mock import patch, MagicMock
from unittest import TestCase, mock


class TestHandler(unittest.TestCase):

    def setUp(self) -> None:

        with open("./tests/sample_events/s3put.json") as s3eventfile:
            self.s3event = yaml.safe_load(s3eventfile)
        with open(
            "./tests/sample_events/sample-vpc-delete-event.json"
        ) as delete_vpc_file:
            self.delete_vpc_event = yaml.safe_load(delete_vpc_file)
        with open(
            "./tests/sample_events/eu-west-1-config.yaml", "r", encoding="utf-8"
        ) as file:
            self.s3_config = yaml.safe_load(file)

    @patch("collect_lambda.boto3.client")
    @patch("event_handler.EventHandler")
    @patch("log_handler.CustomerLogHandler")
    @patch("RuleCollect.event_handler.EventHandler.get_policy_document")
    @patch("event_handler.EventHandler.assume_role_for_s3")
    @patch("log_handler.CustomerLogHandler._check_log_stream")
    def test_handler(
        self,
        mock_boto3_client,
        mock_event_handler,
        mock_customer_log_handler,
        mock_get_policy_document,
        mock_assume_role_for_s3,
        mock__check_log_stream,
    ):
        mock_assume_role_for_s3.return_value = {
            "Credentials": {
                "AccessKeyId": "mock_access_key",
                "SecretAccessKey": "mock_secret_key",  # nosec: Not a real key
                "SessionToken": "mock_session_token",
                "Expiration": "mock_expiration",
            }
        }

        mock_s3_response = {
            "Body": MagicMock(
                spec=io.BytesIO,
                read=lambda x: yaml.dump(self.s3_config).encode("utf-8"),
            ),
            "ContentType": "application/x-yaml",
            "LastModified": datetime.datetime(2022, 1, 1, 0, 0, 0),
            "Metadata": {"some_key": "some_value"},
            "ContentLength": len(yaml.dump(self.s3_config)),
            "ETag": "etag123",
        }

        mock_s3_client = MagicMock()
        mock_boto3_client.return_value = mock_s3_client
        mock_s3_client.get_object.return_value = mock_s3_response

        mock_get_policy_document.return_value = ["rule1", "rule2"], ["skipped_vpc1"]

        # Mocking environment variables
        with patch.dict(
            "collect_lambda.os.environ",
            {
                "LAMBDA_REGION": "eu-west-1",
                "QUEUE_NAME": "RuleCache.fifo",
                "XACCOUNT_ROLE": "your_role_value",
                "NAME_PREFIX": "your_name_prefix",
                "STAGE": "your_stage_value",
            },
        ):
            # Mocking the Lambda context
            mock_lambda_context = MagicMock()

            # Calling the handler function
            handler(self.s3event, mock_lambda_context)

        # Check if methods in EventHandler are called
        mock_event_handler_instance = mock_event_handler.return_value

        # # Assume that 'assume_role_for_s3' is a method in EventHandler
        # mock_event_handler_instance.assume_role_for_s3.assert_called_once_with(
        #     account="your_account_value",
        #     region="eu-west-1",
        #     config=MagicMock(),
        #     rolename="your_role_value",
        # )

        # # Assume that 'send_to_sqs' is a method in EventHandler
        # mock_event_handler_instance.send_to_sqs.assert_called_once_with(
        #     config=MagicMock(),
        #     event_type="your_event_type_value",
        #     region="eu-west-1",
        #     queuename="RuleCache.fifo",
        #     log_stream_name="your_log_stream_name_value",
        # )


if __name__ == "__main__":
    unittest.main()
