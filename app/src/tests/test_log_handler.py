import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from lib.log_handler import CustomerLogHandler, Level


class TestCustomerLogHandler(unittest.TestCase):

    # Set up the test case with mock credentials and log group name
    @patch("lib.log_handler.boto3.client")
    def setUp(self, mock_boto3_client):
        # Mock the boto3 client
        mock_boto3_client.return_value = MagicMock()

        # Initialize the CustomerLogHandler with mock credentials
        self.handler = CustomerLogHandler(
            log_group_name="test-log-group",
            credentials={
                "AccessKeyId": "mock_access_key",
                "SecretAccessKey": "mock_secret_key",  # nosec: Not a real key
                "SessionToken": "mock_session_token",
            },
        )

    def test_init(self):
        self.assertEqual(self.handler.log_group_name, "test-log-group")
        self.assertIsNotNone(self.handler.logger)
        self.assertIsNotNone(self.handler.s3client)
        self.assertIsNotNone(self.handler.logclient)

    def test_update_version(self):
        self.handler.update_version("1.0.0")
        self.assertEqual(self.handler.version, "1.0.0")

    def test_send_log_message(self):
        # Test sending log message
        log_stream_name = "test-log-stream"
        message = "Test message"
        level = Level.INFO

        # Mock the put_log_events method
        mock_log_events = MagicMock()
        self.handler.logclient.put_log_events = mock_log_events

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

    def test_export_logs_to_s3(self):
        log_stream_name = "test-log-stream"
        bucket_name = "XXXXXXXXXXX"

        # Mock the put_log_events method
        mock_log_events = MagicMock()
        self.handler.logclient.create_export_task = mock_log_events

        # Mock dates
        datetoday = int(round(datetime.now().timestamp() * 1000))
        start_date = datetime.now() - timedelta(29)
        date29daysback = int(round(start_date.timestamp() * 1000))

        self.handler.export_logs_to_s3(log_stream_name, bucket_name)

        mock_log_events.assert_called_with(
            taskName="NFW_Customer_Log_Export",
            logGroupName="test-log-group",
            logStreamNamePrefix=log_stream_name,
            fromTime=date29daysback,
            to=datetoday,
            destination=bucket_name,
            destinationPrefix=f"{log_stream_name}",
        )

    def test_generate_log_stream_name(self):
        datetoday_var = int(round(datetime.now().timestamp() * 1000))
        log_stream_name_var = datetime.now().strftime("%Y/%m/%d/%H/%M")

        self.assertEqual(
            self.handler.generate_log_stream_name(),
            f"{log_stream_name_var}/{datetoday_var}",
        )


if __name__ == "__main__":
    unittest.main()
