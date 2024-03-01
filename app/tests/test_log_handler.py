import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime
from log_handler import CustomerLogHandler, Level


class TestCustomerLogHandler(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Initialize the CustomerLogHandler with mock credentials
        cls.handler = CustomerLogHandler(
            log_group_name="test-log-group",
            credentials={
                "AccessKeyId": "mock_access_key",
                "SecretAccessKey": "mock_secret_key",
                "SessionToken": "mock_session_token",
            },
        )

    @patch("log_handler.boto3.client")
    def test_init(self, mock_boto3_client):
        # Test that the constructor sets up the necessary attributes
        handler = CustomerLogHandler(
            log_group_name="test-log-group",
            credentials={
                "AccessKeyId": "mock_access_key",
                "SecretAccessKey": "mock_secret_key",
                "SessionToken": "mock_session_token",
            },
        )

        self.assertEqual(handler.log_group_name, "test-log-group")
        self.assertIsNotNone(handler.logger)
        self.assertIsNone(handler.version)

        mock_boto3_client.assert_called_with(
            "logs",
            aws_access_key_id="mock_access_key",
            aws_secret_access_key="mock_secret_key",
            aws_session_token="mock_session_token",
        )

    @patch("log_handler.boto3.client")
    def test_send_log_message(self, mock_boto3_client):
        # Test sending log message
        log_stream_name = "test-log-stream"
        message = "Test message"
        level = Level.INFO

        # Mock the put_log_events method
        mock_log_events = MagicMock()
        mock_boto3_client.return_value.put_log_events = mock_log_events

        # Mock the _check_log_stream method
        mock_check_log_stream = MagicMock()
        self.handler._check_log_stream = mock_check_log_stream

        # Mock the _generate_time_stamp method
        mock_generate_time_stamp = MagicMock()
        mock_generate_time_stamp.return_value = int(datetime.now().timestamp() * 1000)
        self.handler._generate_time_stamp = mock_generate_time_stamp

        # Run the method
        self.handler.send_log_message(log_stream_name, message, level)

        # Assertions
        mock_check_log_stream.assert_called_with(log_stream_name)
        mock_generate_time_stamp.assert_called_once()

        mock_log_events.assert_called_with(
            logGroupName="test-log-group",
            logStreamName=log_stream_name,
            logEvents=[
                {
                    "timestamp": mock_generate_time_stamp.return_value,
                    "message": f'{{"level": "{level.name}", "message": "{message}"}}',
                }
            ],
        )

    # Add more tests for other methods as needed...


if __name__ == "__main__":
    unittest.main()
