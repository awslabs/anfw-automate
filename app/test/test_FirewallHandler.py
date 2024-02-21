from typing import Any
from unittest.mock import patch, MagicMock
from unittest import TestCase
import os
from yaml import safe_load
import json
from RuleExecute.firewall_handler import FirewallRuleHandler
from lib.rule_config import DefaultDenyRules

# Set the state initially -> fixture
first_rule_state = {
    "UpdateToken": "update_toke_sting",
    "RuleGroup": {
        "RuleVariables": {
            "IPSets": {
                "a123456789010abcdfg12345690001": {
                    "Definition": [
                        "10.10.0.0/24",
                    ]
                }
            },
        },
        "ReferenceSets": {"IPSetReferences": {"string": {"ReferenceArn": "string"}}},
        "RulesSource": {
            "RulesString": """pass tls $a123456789010abcdfg12345690001 any -> $EXTERNAL_NET any (tls.sni; dotprefix; content: ".test.test"; endswith; priority: 1;flow:to_server, established; sid: 301711; rev: 1; metadata: rule_name 123456789010-abcdfg12345690001-123456789a;)""",
        },
    },
    "RuleGroupResponse": {
        "Capacity": 10,
        "ConsumedCapacity": 2,
        "RuleGroupStatus": "ACTIVE",
        "RuleGroupName": "first_group",
    },
}

second_rule_state = {
    "UpdateToken": "update_toke_sting",
    "RuleGroup": {
        "RuleVariables": {
            "IPSets": {
                "a123456789010abcdfg12345690001": {
                    "Definition": [
                        "10.10.0.0/24",
                    ]
                }
            },
        },
        "ReferenceSets": {"IPSetReferences": {"string": {"ReferenceArn": "string"}}},
        "RulesSource": {
            "RulesString": """pass tls $a123456789010abcdfg12345690001 any -> $EXTERNAL_NET any (tls.sni; dotprefix; content: ".test.unittest"; endswith; priority: 1;flow:to_server, established; sid: 630925; rev: 1; metadata: rule_name 123456789010-abcdfg12345690001-123456789b;)""",
        },
    },
    "RuleGroupResponse": {
        "Capacity": 10,
        "ConsumedCapacity": 1,
        "RuleGroupStatus": "ACTIVE",
        "RuleGroupName": "second_group",
    },
}


class MockAWSSevice(MagicMock):
    """Class us used to mock mainly the Network Firewall API via boto3.
    The returns are not complete to maintain a readability.
    The mock functions will not return the full dict of available data.
    Please check the the boto3 documentation
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.next_token_group = True
        self.next_token_policy = True
        self.exception_flag = True

    def update_rule_group(self, *args, **kwargs):
        # API call to change the rule group
        # Check missing
        rule_group = kwargs["RuleGroup"]
        if kwargs["RuleGroupArn"] == "0123/first_group":
            first_rule_state["RuleGroup"] = rule_group

        if kwargs["RuleGroupArn"] == "0123/second_group":
            second_rule_state["RuleGroup"] = rule_group

    def list_rule_groups(self, *args, **kwargs):
        if self.next_token_group:
            # First run with NextToken
            self.next_token_group = False
            return {
                "NextToken": "string",
                "RuleGroups": [
                    {"Name": "name_string", "Arn": "0123/first_group"},
                ],
            }
        else:
            self.next_token_group = True
            # Second run without the NextToken
            return {
                "RuleGroups": [
                    {"Name": "name_string", "Arn": "0123/second_group"},
                ],
            }

    def list_firewall_policies(self, *args, **kwargs):
        """Simulate the API for the network firewall."""
        if self.next_token_policy:
            # First run with NextToken
            self.next_token_policy = False
            return {
                "NextToken": "string",
                "FirewallPolicies": [
                    {"Name": "name_string", "Arn": "0123/first_policy"},
                ],
            }
        else:
            # reset
            self.next_token_policy = True
            # Second run without the NextToken
            return {
                "FirewallPolicies": [
                    {"Name": "name_string_2", "Arn": "0123/second_policy"},
                ],
            }

    def describe_rule_group(self, *args, **kwargs):
        if kwargs["RuleGroupArn"] == "0123/first_group":
            return first_rule_state
        if kwargs["RuleGroupArn"] == "0123/second_group":
            return second_rule_state

    def describe_firewall_policy(self, *args, **kwargs):
        return {
            "FirewallPolicy": {
                "StatelessRuleGroupReferences": [
                    {"ResourceArn": "0123/first_group", "Priority": 10},
                ]
            },
        }

    def delete_rule_group(self, *args, **kwargs):
        pass

    def create_firewall_policy(self, *args, **kwargs):
        return {
            "FirewallPolicyResponse": {
                "FirewallPolicyArn": kwargs["FirewallPolicyName"],
            },
        }

    def describe_rule_group_metadata(self, *args, **kwargs):
        if self.exception_flag:
            # Return the metadata in the first request
            self.exception_flag = False
            return {"RuleGroupArn": kwargs["RuleGroupArn"], "Type": "STATEFUL"}
        else:
            # Return the exception to identity that the rule group was deleted
            raise self.exceptions.ResourceNotFoundException

    class exceptions:
        # Just for catching failed Token styles
        class InvalidTokenException(BaseException):
            def __init__(self) -> None:
                pass

        class ResourceNotFoundException(BaseException):
            def __init__(self) -> None:
                pass


@patch.dict(os.environ, {"SUPPORTED_REGIONS": "eu-west-1, eu-central-1"})
@patch.dict(os.environ, {"CUSTOMER_LOG_GROUP": "DemoGroup"})
@patch("boto3.client", MockAWSSevice)
class TestFirewallRuleHandler(TestCase):
    def load_default_deny(self) -> list:
        with open("data/defaultdeny.yaml", "r") as d:
            default_deny_config = DefaultDenyRules(**safe_load(d))
        return default_deny_config.Rules

    def test_init(self):
        test_fw_handler = FirewallRuleHandler("eu-west-1", {}, None, "log", "1.0")
        # Tests
        self.assertIsInstance(test_fw_handler, FirewallRuleHandler)
        # Check if the default rule are loaded correctly from the file
        self.assertEqual(test_fw_handler.default_deny_rules, self.load_default_deny())
        # Check if the _get_all_policies returns the right arn's
        self.assertEqual(
            test_fw_handler.policy_collection,
            ({"0123/first_policy", "0123/second_policy"}),
        )
        # Check if the _get_all_groups returns the right arn's
        self.assertEqual(
            test_fw_handler.rule_group_collection,
            ({"0123/second_group", "0123/first_group"}),
        )

    def test_get_rule_entries(self):
        test_fw_handler = FirewallRuleHandler("eu-west-1", {}, None, "log", "1.0")

        rules, token = test_fw_handler._get_rule_entries()
        # Prepare the rule collection entries
        test_rule_1 = {
            "RuleGroupARN": "0123/"
            + first_rule_state["RuleGroupResponse"]["RuleGroupName"],
            "RuleString": first_rule_state["RuleGroup"]["RulesSource"]["RulesString"],
        }
        test_rule_2 = {
            "RuleGroupARN": "0123/"
            + second_rule_state["RuleGroupResponse"]["RuleGroupName"],
            "RuleString": second_rule_state["RuleGroup"]["RulesSource"]["RulesString"],
        }
        # Test function
        self.assertIn(test_rule_1, rules)
        self.assertIn(test_rule_2, rules)
        # self.assertListEqual(rules, seq)
        self.assertEqual(token, "update_toke_sting")

    def test_json_to_rule(self):
        log_handler = MagicMock()
        test_fw_handler = FirewallRuleHandler(
            "eu-west-1", {}, log_handler, "log", "1.0"
        )
        data = {
            "VPC": "abcdfg12345690001",
            "Account": "123456789010",
            "Region": "eu-west-1",
            "CIDR": "10.10.0.0/24",
            "Rules": {
                "123456789011-abcdfg12345690001-123456789D": "pass tls $a123456789010abcdfg12345690001 any -> $EXTERNAL_NET any (tls.sni; dotprefix; content:'.test2.test'; endswith; priority:1;flow:to_server, established; sid:65731; rev:1; metadata: rule_name 123456789011-abcdfg12345690001-123456789D;)",
                "123456789011-abcdfg12345690001-123456789K": "pass tls $a123456789010abcdfg12345690001 any -> $EXTERNAL_NET any (tls.sni; dotprefix; content:'.test3.test'; endswith; priority:1;flow:to_server, established; sid:853129; rev:1; metadata: rule_name 123456789011-abcdfg12345690001-123456789K;)",
            },
        }
        # Update rule
        test_fw_handler.json_to_rule(json_message=json.dumps(data), event_type="Update")
        # DeleteVpc
        test_fw_handler.json_to_rule(
            json_message=json.dumps(data), event_type="DeleteVpc"
        )
        # DeleteS3
        test_fw_handler.json_to_rule(
            json_message=json.dumps(data), event_type="DeleteS3"
        )
        # DeleteAccount
        test_fw_handler.json_to_rule(
            json_message=json.dumps(data), event_type="DeleteAccount"
        )

    def test_get_rule_group(self):
        test_fw_handler = FirewallRuleHandler("eu-west-1", {}, None, "log", "1.0")
        smallest_group = test_fw_handler._get_rule_group()
        self.assertEqual(smallest_group, "0123/second_group")

    def test_create_new_policy(self):
        test_fw_handler = FirewallRuleHandler("eu-west-1", {}, None, "log", "1.0")
        test_name = "Test"
        response = test_fw_handler._create_new_policy(
            policy_name=test_name, rule_arn="0123/test_group"
        )
        self.assertEqual(test_name, response)

    def test_check_rule_status(self):
        test_fw_handler = FirewallRuleHandler("eu-west-1", {}, None, "log", "1.0")
        result = test_fw_handler._check_rule_status("TestRule")
        # Return true if the group was deleted
        self.assertIs(result, True)

    def test_arn_to_name(self):
        test_fw_handler = FirewallRuleHandler("eu-west-1", {}, None, "log", "1.0")
        name = test_fw_handler._arn_to_name(
            "arn::network-firewall:eu-west-1:123456789012:stateful-rulegroup/TestName"
        )
        self.assertEqual(name, "TestName")

    def test_generate_random_name(self):
        test_fw_handler = FirewallRuleHandler("eu-west-1", {}, None, "log", "1.0")
        name = test_fw_handler._generate_random_name()
        self.assertRegex(name, r"[0-9]{9,32}")

    def test_get_rule_name_from_rule_string(self):
        test_fw_handler = FirewallRuleHandler("eu-west-1", {}, None, "log", "1.0")
        rule = """123456789011-abcdfg12345690001-123456789D": "pass tls $a123456789010abcdfg12345690001 any -> $EXTERNAL_NET any (tls.sni; dotprefix; content:'.test2.test'; endswith; priority:1;flow:to_server, established; sid:65731; rev:1; metadata: rule_name 123456789011-abcdfg12345690001-123456789D;)"""
        response = test_fw_handler._get_rule_name_from_rule_string(rule)
        self.assertEqual(response, "123456789011-abcdfg12345690001-123456789D")
