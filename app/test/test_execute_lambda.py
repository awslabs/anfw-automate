from unittest.mock import patch, MagicMock
from unittest import TestCase
import os
from yaml import safe_load
import json
from RuleExecute.execute_lambda import handler, assume_role_for_s3


allowed_event_types = ["Update", "DeleteVpc", "DeleteS3", "DeleteAccount"]


test_event = {
    "Records": [
        {
            "messageId": "90341a79-a1a6-4f95-91d0-2cd99bd084b2",
            "body": '{"VPC": "0922083e651e7c675", "Account": "164602662208", "Region": "eu-west-1", "CIDR": "10.10.0.0/24", "Rules": {"164602662208-0922083e651e7c675-96ccf8d27f": "pass tls $a1646026622080922083e651e7c675 any -> $EXTERNAL_NET any (tls.sni; dotprefix; content:\\\\".amazonaws.com\\\\"; endswith; priority:1;flow:to_server, established; sid:65731; rev:1; metadata: rule_name 164602662208-0922083e651e7c675-96ccf8d27f;)", "164602662208-0922083e651e7c675-9773e15683": "pass tls $a1646026622080922083e651e7c675 any -> $EXTERNAL_NET any (tls.sni; dotprefix; content:\\\\".example.com\\\\"; endswith; priority:1;flow:to_server, established; sid:853129; rev:1; metadata: rule_name 164602662208-0922083e651e7c675-9773e15683;)", "164602662208-0922083e651e7c675-39e4a33c8a": "pass http $a1646026622080922083e651e7c675 any -> $EXTERNAL_NET any (http.host; content:\\\\"google.com\\\\"; startswith; endswith; priority:1;flow:to_server, established; sid:341833; rev:1; metadata: rule_name 164602662208-0922083e651e7c675-39e4a33c8a;)", "164602662208-0922083e651e7c675-ab670070c7": "pass http $a1646026622080922083e651e7c675 any -> $EXTERNAL_NET any (http.host; content:\\\\"helpdomain.org\\\\"; startswith; endswith; priority:1;flow:to_server, established; sid:279682; rev:1; metadata: rule_name 164602662208-0922083e651e7c675-ab670070c7;)", "164602662208-0922083e651e7c675-ebd1db72a6": "pass http $a1646026622080922083e651e7c675 any -> $EXTERNAL_NET any (http.host; content:\\\\".amazon.com\\\\"; startswith; endswith; flow:to_server, established;priority:1; sid:269674; rev:1; metadata: rule_name 164602662208-0922083e651e7c675-ebd1db72a6;)", "164602662208-0922083e651e7c675-51449db790": "pass tls $a1646026622080922083e651e7c675 any -> $EXTERNAL_NET any (tls.sni; dotprefix; content:\\\\".facebook.com\\\\"; endswith; flow:to_server, established;priority:1; sid:796342; rev:1; metadata: rule_name 164602662208-0922083e651e7c675-51449db790;)"}}',
            "messageAttributes": {
                "Account": {
                    "stringValue": "164602662208",
                    "stringListValues": [],
                    "binaryListValues": [],
                    "dataType": "String",
                },
                "Version": {
                    "stringValue": "0.2.0",
                    "stringListValues": [],
                    "binaryListValues": [],
                    "dataType": "String",
                },
                "Event": {
                    "stringValue": "Update",
                    "stringListValues": [],
                    "binaryListValues": [],
                    "dataType": "String",
                },
                "Region": {
                    "stringValue": "eu-west-1",
                    "stringListValues": [],
                    "binaryListValues": [],
                    "dataType": "String",
                },
                "LogstreamName": {
                    "stringValue": "Something",
                    "stringListValues": [],
                    "binaryListValues": [],
                    "dataType": "String",
                },
            },
            "eventSource": "aws:sqs",
            "eventSourceARN": "arn:aws:sqs:eu-west-1:868363312618:sqs-pp-nfwffm-proxy-local-LambdaSQS.fifo",
            "awsRegion": "eu-west-1",
        }
    ]
}

test_response_assume_role = {
    "Credentials": {
        "AccessKeyId": "string",
        "SecretAccessKey": "string",
        "SessionToken": "string",
        "Expiration": "something",
    },
    "AssumedRoleUser": {"AssumedRoleId": "string", "Arn": "string"},
    "PackedPolicySize": 123,
    "SourceIdentity": "string",
}


class Boto3Client:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def assume_role(self, *args, **kwargs):
        return test_response_assume_role

    def put_log_events(self, *args, **kwargs):
        pass

    class exceptions:
        class ResourceAlreadyExistsException(BaseException):
            def __init__(self) -> None:
                pass


class MockFirewallHandler(MagicMock):
    def __init__(self, *args, **kwargs) -> None:
        pass

    def json_to_rule(self, json_message: str, event_type: str):
        # Test if input is correct
        assert json_message == test_event["Records"][0]["body"]  # nosec
        # Just cross check from data above
        assert event_type in allowed_event_types  # nosec

    def create_reserved_rule_group(self):
        pass


class LambdaContext:
    function_name = "Test Function"
    memory_limit_in_mb = "0"
    invoked_function_arn = "aws::test"
    aws_request_id = "42"


@patch("boto3.client", Boto3Client)
@patch.dict(os.environ, {"CUSTOMER_LOG_S3": "DemoGroup"})
@patch.dict(os.environ, {"LAMBDA_REGION": "test-region"})
@patch.dict(os.environ, {"NAME_PREFIX": "Test"})
@patch.dict(os.environ, {"XACCOUNT_ROLE": "TestAccount"})
@patch("RuleExecute.execute_lambda.CustomerLogHandler", MagicMock)
@patch("RuleExecute.execute_lambda.FirewallRuleHandler", MockFirewallHandler)
class TestFirewallRuleHandler(TestCase):
    def test_handler(self):
        context = LambdaContext()
        handler(test_event, context)
        # Check if called
        MagicMock.assert_called(MockFirewallHandler)

    def test_assume_role_for_s3(self):
        credentials = assume_role_for_s3(
            account="012345678901", region="eu-test-1", config=None, rolename="TestRole"
        )
        self.assertEqual(credentials, test_response_assume_role["Credentials"])
