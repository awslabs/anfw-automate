import ipaddress
import os
import random
import re
import boto3
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
        print(yaml_string)
    return yaml_string


class TestEventHandler(unittest.TestCase):
    """Test event handler library"""

    def setUp(self):
        self.handler = EventHandler(version="1.0")

    def test_init(self):
        self.assertIsNotNone(self.handler.version)

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
        mock_sts_client = MagicMock()
        mock_boto3_client.return_value = mock_sts_client

        mock_sts_client.assume_role.return_value = get_sts_creds()

        account = "123456789012"
        region = "us-west-2"
        config = MagicMock()
        rolename = "mock_role_name"

        credentials = self.handler.assume_role_for_s3(account, region, config, rolename)

        assert credentials["AccessKeyId"] == "mock_access_key_id"
        assert credentials["SecretAccessKey"] == "mock_secret_access_key"
        assert credentials["SessionToken"] == "mock_session_token"

    @patch("RuleCollect.event_handler.boto3.client")
    def test__is_vpc_attached_to_transit_gateway(self, mock_boto3_client):
        mock_ec2_client = MagicMock()
        mock_boto3_client.return_value = mock_ec2_client

        mock_ec2_client.describe_transit_gateway_attachments.return_value = {
            "TransitGatewayAttachments": [{"AttachmentId": "attachment_1"}]
        }

        vpc_id = "vpc-12345678"

        result = self.handler._is_vpc_attached_to_transit_gateway(
            mock_ec2_client, vpc_id
        )

        assert result is True

    @patch("RuleCollect.event_handler.boto3.resource")
    @patch("RuleCollect.event_handler.boto3.client")
    def test_send_to_sqs(self, mock_boto3_client, mock_boto3_resource):
        mock_sqs_resource = MagicMock()
        mock_queue = MagicMock()
        mock_sqs_resource.get_queue_by_name.return_value = mock_queue
        mock_boto3_resource.return_value = mock_sqs_resource

        config_entry = MagicMock()
        config_entry.account = "mock_account"
        config_entry.region = "us-west-2"
        config_entry.vpc = "vpc-12345678"
        config_entry.get_json.return_value = "{}"

        self.handler.send_to_sqs(
            config_entry, "us-west-2", "mock_queue", "mock_event", "mock_log_stream"
        )

        mock_queue.send_message.assert_called_once_with(
            MessageGroupId="mock_account",
            MessageBody="{}",
            MessageAttributes={
                "Event": {"StringValue": "mock_event", "DataType": "String"},
                "Account": {"StringValue": "mock_account", "DataType": "String"},
                "Region": {"StringValue": "us-west-2", "DataType": "String"},
                "LogstreamName": {
                    "StringValue": "mock_log_stream",
                    "DataType": "String",
                },
                "Version": {"StringValue": "1.0", "DataType": "String"},
            },
        )

    @patch("RuleCollect.event_handler.boto3.client")
    @patch("RuleCollect.event_handler.boto3.resource")
    @patch("RuleCollect.event_handler.EventHandler._is_vpc_attached_to_transit_gateway")
    def test_get_policy_document(
        self,
        mock_boto3_client,
        mock_boto3_resource,
        mock_is_vpc_attached_to_transit_gateway,
    ):

        def generate_random_cidr():
            return str(ipaddress.IPv4Network(random.randint(0, 2**32), strict=False))

        # Mocking data and variables
        mock_data: str = load_yaml_to_string()
        mock_sts_credentials = get_sts_creds()

        # Mocking boto3 response for vpc
        mock_vpc = MagicMock()
        mock_vpc.id = "mock-vpc-id"
        mock_vpc.cidr_block = property(generate_random_cidr)
        mock_boto3_resource.return_value.Vpc.return_value = mock_vpc

        mock_ec2_client = MagicMock()
        mock_boto3_client.return_value = mock_ec2_client

        mock_is_vpc_attached_to_transit_gateway.return_value = True

        # Call the function
        policies, skipped_vpc = self.handler.get_policy_document(
            mock_data, "mock_account", "us-west-2", mock_sts_credentials, "mock_key"
        )

        # Assert the logging
        self.handler.logger.debug.assert_called_once_with("Got EC2 boto3 resource")
        self.handler.logger.debug.assert_called_once_with("Got EC2 boto3 client")
        # Assert the logging
        self.handler.logger.debug.assert_called_once_with(
            f"Got cidr block for {mock_vpc.id}"
        )

        # # Assertions
        # assert len(policies) == 1
        # assert len(skipped_vpc) == 0
        # assert policies[0].ip_set_space == "10.0.0.0/16"
        # assert policies[0].account == "mock_account"
        # assert policies[0].region == "us-west-2"
        # assert policies[0].version == "1.0"
        # assert policies[0].rules == {
        #     "ruletype1": ["rule1", "rule2"],
        #     "ruletype2": ["rule3", "rule4"],
        # }
        # mock_open.assert_called_once_with(
        #     os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.json"),
        #     mode="r",
        #     encoding="utf-8",
        # )
        # mock_yaml_load.assert_called_once_with("mock_doc")
        # mock_validate.assert_called_once()
        # mock_ec2_resource.Vpc.assert_called_once_with("vpc-12345678")
        # mock_sts_client.assume_role.assert_called_once_with(
        #     RoleArn="arn:aws:iam::mock_account:role/mock_role_name",
        #     RoleSessionName="CollectLambdaRuleAssumption",
        # )


if __name__ == "__main__":
    unittest.main()
