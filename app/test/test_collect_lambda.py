from typing import Any
from unittest.mock import patch, MagicMock
from unittest import TestCase
import os
from yaml import safe_load
import json
from RuleCollect.collect_lambda import handler


class LambdaContext:
    function_name = "Test Function"
    memory_limit_in_mb = "0"
    invoked_function_arn = "aws::test"
    aws_request_id = "42"


class MockEventHandler(MagicMock):
    def __init__(self, *args: Any, **kw: Any) -> None:
        super().__init__(*args, **kw)

    class InternalError(Exception):
        """Exception for invalid format"""

        pass

    class PermissionError(Exception):
        """Exception for invalid format"""

        pass

    class FormatError(Exception):
        """Exception for invalid format"""

        pass

    def get_policy_document(self, *args, **kwargs):
        policies = ("testdata", "testdata2")
        skipped_vpc = ("testdata", "testdata2")
        return policies, skipped_vpc


@patch("RuleCollect.collect_lambda.CustomerLogHandler", MagicMock)
@patch("RuleCollect.collect_lambda.EventHandler", MockEventHandler)
class TestFirewallRuleHandler(TestCase):
    def setUp(self) -> None:
        with open("./tests/sample_events/s3put.json") as s3eventfile:
            self.s3event = safe_load(s3eventfile)
        with open("./tests/sample_events/sample-vpc-delete-event.json") as delete_vpc_file:
            self.delete_vpc_event = safe_load(delete_vpc_file)

    def test_handler(self):
        context = LambdaContext()
        handler(self.s3event, context)

        handler(self.delete_vpc_event, context)
