from typing import Any
import os
from yaml import safe_load
import json
from RuleCollect.collect_lambda import handler
import unittest
from unittest.mock import patch, MagicMock
from unittest import TestCase, mock


class TestHandler(unittest.TestCase):

    def setUp(self) -> None:
        with open("./tests/sample_events/s3put.json") as s3eventfile:
            self.s3event = safe_load(s3eventfile)
        with open(
            "./tests/sample_events/sample-vpc-delete-event.json"
        ) as delete_vpc_file:
            self.delete_vpc_event = safe_load(delete_vpc_file)

    @patch("collect_lambda.boto3.client")
    @patch("event_handler.EventHandler")
    @patch("log_handler.CustomerLogHandler")
    @patch("event_handler.EventHandler.get_policy_document")
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
        # Mocking external dependencies
        # mock_s3_client = MagicMock()
        # mock_boto3_client.return_value = mock_s3_client

        mock_assume_role_for_s3.return_value = {
            "Credentials": {
                "AccessKeyId": "mock_access_key",
                "SecretAccessKey": "mock_secret_key",
                "SessionToken": "mock_session_token",
                "Expiration": "mock_expiration",
            }
        }

        def get_policy_document_side_effect(*args, **kwargs):
            return ["rule1", "rule2"], ["skipped_vpc1"]

        mock_get_policy_document.side_effect = get_policy_document_side_effect

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
