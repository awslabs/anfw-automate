import unittest
from unittest.mock import MagicMock, patch
from RuleCollect.collect_lambda import handler
import json


class TestLambdaHandler(unittest.TestCase):

    with open(
        "./tests/sample_events/s3put.json", mode="r", encoding="utf-8"
    ) as s3eventfile:
        s3event = json.load(s3eventfile)
    with open(
        "./tests/sample_events/sample-vpc-delete-event.json",
        mode="r",
        encoding="utf-8",
    ) as delete_vpc_file:
        delete_vpc_event = json.load(delete_vpc_file)
    print("files loaded")

    @patch("collect_lambda.boto3.client")
    @patch("event_handler.EventHandler")
    @patch("log_handler.CustomerLogHandler")
    def test_handler_vpc_delete_event(
        self, mock_boto_client, mock_log_handler, mock_event_handler
    ):
        # Mocking necessary objects
        mock_boto_client.return_value = MagicMock()
        mock_event_handler_instance = mock_event_handler.return_value
        mock_log_handler_instance = mock_log_handler.return_value

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
            # Call the handler function with the mocked objects
            mock_context = MagicMock()
            handler(self.s3event, mock_context)

        # Assert that the necessary methods were called
        mock_event_handler.assert_called_once_with(version="0")
        mock_event_handler_instance.assume_role_for_s3.assert_called_once_with(
            account="your_expected_account",
            region="eu-west-1",  # Change to your expected region
            config=MagicMock(),
            rolename="your_expected_role",
        )
        mock_log_handler.assert_called_once_with(
            log_group_name="your_expected_log_group_name",
            version="your_expected_version",
            credentials=mock_event_handler_instance.assume_role_for_s3.return_value,
        )
        mock_log_handler_instance.send_log_message.assert_called_once_with(
            "your_expected_log_stream_name",
            "DeleteVpc event detected from your_expected_vpc_id",
            level="your_expected_log_level",
        )

        # Add more assertions based on your specific use case

    # Similar tests for S3 events can be added here


if __name__ == "__main__":
    unittest.main()
