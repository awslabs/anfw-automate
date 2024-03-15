import os
import yaml
import unittest
from unittest.mock import MagicMock, patch
from RuleCollect.event_handler import EventHandler


# Mock sts response
def get_sts_creds():
    sts_credentials = {
        "AccessKeyId": "mock_access_key_id",
        "SecretAccessKey": "mock_secret_access_key",
        "SessionToken": "mock_session_token",
    }

    return {"Credentials": sts_credentials}


def load_yaml_to_string() -> str:
    with open(
        "./tests/sample_events/{AWS-Region}-config.yaml", mode="r", encoding="utf-8"
    ) as file:
        # Load YAML data from file
        yaml_data = yaml.safe_load(file)

        # Convert YAML data to string
        yaml_string = yaml.dump(yaml_data)
    return yaml_string


class TestEventHandler(unittest.TestCase):
    """Test event handler library"""

    def setUp(self):
        self.handler = EventHandler(version="1.0")

    def test_init(self):
        self.assertIsNotNone(self.handler.version)
        self.assertIsNotNone(self.handler.logger)

    def test_get_region_from_string(self):
        region = self.handler.get_region_from_string("us-east-1-config.yaml")
        self.assertEqual(region, "us-east-1")

        with self.assertRaises(EventHandler.FormatError):
            self.handler.get_region_from_string("invalid-filename.yaml")

    def test_validate_file_name(self):
        valid_filename = "us-east-1-config.yaml"
        invalid_filename = "invalid-filename.yaml"

        self.assertTrue(self.handler.validate_file_name(valid_filename))
        self.assertFalse(self.handler.validate_file_name(invalid_filename))

    @patch("RuleCollect.event_handler.boto3.client")
    def test_assume_role_for_s3(self, mock_boto3_client):
        # Mocking boto3.client() to return a MagicMock object
        mock_sts_client = MagicMock()
        mock_boto3_client.return_value = mock_sts_client

        # Define your test inputs
        account = "your_account"
        region = "your_region"
        config = MagicMock()
        rolename = "your_rolename"

        # Mocking the assume_role() method of the STS client
        mock_sts_client.assume_role.return_value = get_sts_creds()

        # Call the method to test
        result = self.handler.assume_role_for_s3(account, region, config, rolename)

        # Assertions
        self.assertEqual(result, get_sts_creds()["Credentials"])
        mock_boto3_client.assert_called_once_with(
            "sts", region_name=region, config=config
        )
        mock_sts_client.assume_role.assert_called_once_with(
            RoleArn=f"arn:aws:iam::{account}:role/{rolename}",
            RoleSessionName="CollectLambdaRuleAssumption",
        )

    @patch("RuleCollect.event_handler.boto3.resource")
    def test_send_to_sqs(self, mock_boto3):
        # Mocking ConfigEntry
        config = MagicMock()
        config.get_json.return_value = '{"example_key": "example_value"}'
        config.account = "example_account"
        config.region = "example_region"
        config.vpc = "example_vpc"

        # Mocking logger
        mock_logger = MagicMock()
        self.handler.logger = mock_logger

        # Mocking boto3 calls
        mock_queue = MagicMock()
        mock_queue.send_message.return_value = None
        mock_sqs = MagicMock()
        mock_sqs.get_queue_by_name.return_value = mock_queue
        mock_boto3.return_value = mock_sqs

        # Calling the method
        self.handler.send_to_sqs(
            config, "us-west-1", "example_queue", "example_event", "example_log_stream"
        )

        # Assertions
        mock_logger.info.assert_called_once_with(
            "Sent Rules to SQS for vpc-example_vpc in account example_account"
        )
        mock_queue.send_message.assert_called_once_with(
            MessageGroupId="example_account",
            MessageBody='{"example_key": "example_value"}',
            MessageAttributes={
                "Event": {"StringValue": "example_event", "DataType": "String"},
                "Account": {"StringValue": "example_account", "DataType": "String"},
                "Region": {"StringValue": "example_region", "DataType": "String"},
                "LogstreamName": {
                    "StringValue": "example_log_stream",
                    "DataType": "String",
                },
                "Version": {"StringValue": self.handler.version, "DataType": "String"},
            },
        )

    @patch("RuleCollect.event_handler.boto3.client")
    @patch("RuleCollect.event_handler.boto3.resource")
    @patch("RuleCollect.event_handler.EventHandler._is_vpc_attached_to_transit_gateway")
    def test_get_policy_document(
        self, mock_is_vpc_attached, mock_boto_resource, mock_boto_client
    ):
        # Mocking dependencies
        mock_boto_resource.return_value = MagicMock()
        mock_boto_client.return_value = MagicMock()
        mock_is_vpc_attached.return_value = True

        # Mocking logger
        mock_logger = MagicMock()
        self.handler.logger = mock_logger

        # Mocking data
        # Load data from a local YAML file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        yaml_file_path = os.path.join(
            current_dir, "sample_events/us-east-1-config.yaml"
        )
        with open(yaml_file_path, mode="r", encoding="utf-8") as f:
            doc = f.read()

        # doc = '{"Config": [{"VPC": "vpc_id", "Properties": [{"Key": ["Value"]}]}]}'
        account = "112233445566"
        region = "test_region"
        credentials = {
            "AccessKeyId": "test_access_key",
            "SecretAccessKey": "test_secret_key",
            "SessionToken": "test_session_token",
        }
        key = "test_key"

        # Calling the function to be tested
        result, skipped_vpc = self.handler.get_policy_document(
            doc, account, region, credentials, key
        )

        # Get the number of items in Config from the YAML document
        config_data = yaml.safe_load(doc)
        num_config_items = len(config_data["Config"])

        # Assertion
        self.assertEqual(len(result), num_config_items)
        self.assertEqual(len(skipped_vpc), 0)  # Assuming no VPCs were skipped


if __name__ == "__main__":
    unittest.main()
