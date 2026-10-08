from typing import Any
from unittest.mock import patch, MagicMock
from unittest import TestCase
import os
from yaml import safe_load
import json
from botocore.exceptions import ClientError
from RuleExecute.firewall_handler import (
    FirewallRuleHandler,
    RULEGROUP_OWNER_TAG_KEY,
    RULEGROUP_OWNER_TAG_VALUE,
    RULEGROUP_STAGE_TAG_KEY,
)
from lib.rule_config import DefaultDenyRules

# ARNs used across the mocked state. Both ARN *names* (the segment after "/")
# carry a rule-order suffix because _get_all_groups scopes discovered groups by
# that suffix: "-strict" under STRICT_ORDER and "-action" under
# DEFAULT_ACTION_ORDER.
FIRST_GROUP_ARN = "0123/first_group-strict"
SECOND_GROUP_ARN = "0123/second_group-action"

# Set the state initially -> fixture
first_rule_state = {
    "UpdateToken": "update_token_string",
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
        "RuleGroupName": "first_group-strict",
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
        "RuleGroupName": "second_group-action",
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
        # Per-ARN tag store used by list_tags_for_resource / tag_resource so
        # tests can assert on the self-healing ownership-tag backfill.
        self.resource_tags: dict = {}

    def update_rule_group(self, *args, **kwargs):
        # API call to change the rule group
        # Check missing
        rule_group = kwargs["RuleGroup"]
        if kwargs["RuleGroupArn"] == FIRST_GROUP_ARN:
            first_rule_state["RuleGroup"] = rule_group

        if kwargs["RuleGroupArn"] == SECOND_GROUP_ARN:
            second_rule_state["RuleGroup"] = rule_group

    def create_rule_group(self, *args, **kwargs):
        # Return a freshly minted ARN; name carries the active rule-order suffix.
        return {
            "RuleGroupResponse": {
                "RuleGroupArn": f"0123/{kwargs['RuleGroupName']}",
            },
        }

    def list_tags_for_resource(self, *args, **kwargs):
        return {"Tags": self.resource_tags.get(kwargs["ResourceArn"], [])}

    def tag_resource(self, *args, **kwargs):
        arn = kwargs["ResourceArn"]
        existing = {t["Key"]: t["Value"] for t in self.resource_tags.get(arn, [])}
        for tag in kwargs["Tags"]:
            existing[tag["Key"]] = tag["Value"]
        self.resource_tags[arn] = [
            {"Key": k, "Value": v} for k, v in existing.items()
        ]

    def update_firewall_policy(self, *args, **kwargs):
        pass

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
        if kwargs["RuleGroupArn"] == FIRST_GROUP_ARN:
            return first_rule_state
        if kwargs["RuleGroupArn"] == SECOND_GROUP_ARN:
            return second_rule_state

    def describe_firewall_policy(self, *args, **kwargs):
        # _get_all_groups now discovers groups by walking the policy's stateful
        # references rather than listing every rule group in the account. Both
        # ARN names carry a rule-order suffix; _get_all_groups scopes by it.
        return {
            "UpdateToken": "policy_update_token",
            "FirewallPolicy": {
                "StatefulRuleGroupReferences": [
                    {"ResourceArn": FIRST_GROUP_ARN},
                    {"ResourceArn": SECOND_GROUP_ARN},
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


@patch.dict(
    os.environ,
    {
        "POLICY_ARNS": '{"eu-west-1": ["arn:aws:network-firewall:eu-west-1:account-id:policy/policy-id-1"], "eu-central-1": ["arn:aws:network-firewall:eu-central-1:account-id:policy/policy-id-2"]}',
        "SUPPORTED_REGIONS": "eu-west-1, eu-central-1",
        "CUSTOMER_LOG_GROUP": "DemoGroup",
        "RULE_ORDER": "STRICT_ORDER",
    },
)
@patch("boto3.client", MockAWSSevice)
class TestFirewallRuleHandler(TestCase):
    def load_default_deny(self) -> list:
        with open("./data/global_rules.yaml", "r") as d:
            default_deny_config = DefaultDenyRules(**safe_load(d))
        return default_deny_config.Rules

    def test_init(self):
        test_fw_handler = FirewallRuleHandler("eu-west-1", {}, None, "log")
        # Tests
        self.assertIsInstance(test_fw_handler, FirewallRuleHandler)
        # Check if the default rule are loaded correctly from the file
        self.assertEqual(test_fw_handler.default_deny_rules, self.load_default_deny())
        # Check if the _get_all_policies returns the right arn's

        self.assertEqual(
            test_fw_handler.policy_collection,
            {"arn:aws:network-firewall:eu-west-1:account-id:policy/policy-id-1"},
        )

        # Check if the _get_all_groups returns the right arn's. Under
        # STRICT_ORDER only the "-strict" group is in scope, even though the
        # policy references both groups.
        self.assertEqual(
            test_fw_handler.rule_group_collection,
            ({FIRST_GROUP_ARN}),
        )

    def test_get_rule_entries(self):
        test_fw_handler = FirewallRuleHandler("eu-west-1", {}, None, "log")

        rules, token = test_fw_handler._get_rule_entries()
        # Prepare the rule collection entries
        test_rule_1 = {
            "RuleGroupARN": FIRST_GROUP_ARN,
            "RuleString": first_rule_state["RuleGroup"]["RulesSource"]["RulesString"],
        }
        test_rule_2 = {
            "RuleGroupARN": SECOND_GROUP_ARN,
            "RuleString": second_rule_state["RuleGroup"]["RulesSource"]["RulesString"],
        }
        # Test function
        # Assuming smallest_group is the value you want to check
        if test_fw_handler.rule_order == "STRICT_ORDER":
            self.assertIn(test_rule_1, rules)
        else:
            # Do something else or assert a different condition
            self.assertIn(test_rule_2, rules)

    def test_json_to_rule(self):
        log_handler = MagicMock()
        test_fw_handler = FirewallRuleHandler("eu-west-1", {}, log_handler, "log")
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
        test_fw_handler = FirewallRuleHandler("eu-west-1", {}, None, "log")
        smallest_group = test_fw_handler._get_rule_group()

        # Assuming smallest_group is the value you want to check
        if test_fw_handler.rule_order == "STRICT_ORDER":
            self.assertEqual(smallest_group, FIRST_GROUP_ARN)
        else:
            self.assertEqual(smallest_group, SECOND_GROUP_ARN)

    def test_create_new_policy(self):
        test_fw_handler = FirewallRuleHandler("eu-west-1", {}, None, "log")
        test_name = "Test"
        response = test_fw_handler._create_new_policy(
            policy_name=test_name, rule_arn="0123/test_group"
        )
        self.assertEqual(test_name, response)

    def test_check_rule_status(self):
        test_fw_handler = FirewallRuleHandler("eu-west-1", {}, None, "log")
        result = test_fw_handler._check_rule_status("TestRule")
        # Return true if the group was deleted
        self.assertIs(result, True)

    def test_arn_to_name(self):
        test_fw_handler = FirewallRuleHandler("eu-west-1", {}, None, "log")
        name = test_fw_handler._arn_to_name(
            "arn::network-firewall:eu-west-1:123456789012:stateful-rulegroup/TestName"
        )
        self.assertEqual(name, "TestName")

    def test_generate_random_name(self):
        test_fw_handler = FirewallRuleHandler("eu-west-1", {}, None, "log")
        name = test_fw_handler._generate_random_name()
        self.assertRegex(name, r"[0-9]{9,32}")

    def test_get_rule_name_from_rule_string(self):
        test_fw_handler = FirewallRuleHandler("eu-west-1", {}, None, "log")
        rule = """123456789011-abcdfg12345690001-123456789D": "pass tls $a123456789010abcdfg12345690001 any -> $EXTERNAL_NET any (tls.sni; dotprefix; content:'.test2.test'; endswith; priority:1;flow:to_server, established; sid:65731; rev:1; metadata: rule_name 123456789011-abcdfg12345690001-123456789D;)"""
        response = test_fw_handler._get_rule_name_from_rule_string(rule)
        self.assertEqual(response, "123456789011-abcdfg12345690001-123456789D")


def _client_error(code: str) -> ClientError:
    """Build a real botocore ClientError (the production code catches this type,
    not the MockAWSSevice inner exceptions)."""
    return ClientError({"Error": {"Code": code, "Message": "boom"}}, "Operation")


class _NfwDouble:
    """Minimal, record-and-replay stand-in for the network-firewall client used
    to drive _get_all_groups / _ensure_group_tags down specific branches.

    Only the methods those two functions call are implemented. Everything is
    configured per-test so each branch is isolated.
    """

    def __init__(
        self,
        policies: dict | None = None,
        describe_policy_error: bool = False,
        tags_by_arn: dict | None = None,
        tag_error_arns: set | None = None,
    ) -> None:
        # policy_arn -> list of stateful references ({"ResourceArn": ...})
        self._policies = policies or {}
        self._describe_policy_error = describe_policy_error
        # arn -> list of {"Key","Value"} currently on the resource
        self._tags = {k: list(v) for k, v in (tags_by_arn or {}).items()}
        self._tag_error_arns = tag_error_arns or set()
        self.tag_calls: list = []
        self.list_tag_calls: list = []

    def describe_firewall_policy(self, FirewallPolicyArn, **kwargs):
        if self._describe_policy_error:
            raise _client_error("InternalServerError")
        return {
            "UpdateToken": "t",
            "FirewallPolicy": {
                "StatefulRuleGroupReferences": self._policies.get(
                    FirewallPolicyArn, []
                )
            },
        }

    def list_tags_for_resource(self, ResourceArn, **kwargs):
        self.list_tag_calls.append(ResourceArn)
        return {"Tags": self._tags.get(ResourceArn, [])}

    def tag_resource(self, ResourceArn, Tags, **kwargs):
        if ResourceArn in self._tag_error_arns:
            raise _client_error("AccessDeniedException")
        self.tag_calls.append((ResourceArn, Tags))
        merged = {t["Key"]: t["Value"] for t in self._tags.get(ResourceArn, [])}
        for t in Tags:
            merged[t["Key"]] = t["Value"]
        self._tags[ResourceArn] = [{"Key": k, "Value": v} for k, v in merged.items()]


@patch.dict(
    os.environ,
    {
        "POLICY_ARNS": '{"eu-west-1": ["arn:aws:network-firewall:eu-west-1:account-id:policy/policy-id-1"], "eu-central-1": ["arn:aws:network-firewall:eu-central-1:account-id:policy/policy-id-2"]}',
        "SUPPORTED_REGIONS": "eu-west-1, eu-central-1",
        "CUSTOMER_LOG_GROUP": "DemoGroup",
        "RULE_ORDER": "STRICT_ORDER",
        "STAGE": "int",
    },
)
@patch("boto3.client", MockAWSSevice)
class TestGetAllGroupsDiscovery(TestCase):
    """Covers the policy-walk discovery in _get_all_groups and the self-healing
    ownership tagging in _ensure_group_tags."""

    def _handler(self) -> FirewallRuleHandler:
        # Build with the shared mock, then override _nfw per test.
        return FirewallRuleHandler("eu-west-1", {}, None, "log")

    def test_discovers_only_strict_groups_under_strict_order(self):
        """Policy references a strict and an action group; STRICT_ORDER keeps the
        strict one only."""
        h = self._handler()
        policy_arn = next(iter(h.policy_collection))
        h._nfw = _NfwDouble(
            policies={
                policy_arn: [
                    {"ResourceArn": "0123/g-strict"},
                    {"ResourceArn": "0123/g-action"},
                ]
            }
        )
        h.rule_order = "STRICT_ORDER"
        self.assertEqual(h._get_all_groups(), {"0123/g-strict"})

    def test_discovers_only_action_groups_under_default_action_order(self):
        h = self._handler()
        policy_arn = next(iter(h.policy_collection))
        h._nfw = _NfwDouble(
            policies={
                policy_arn: [
                    {"ResourceArn": "0123/g-strict"},
                    {"ResourceArn": "0123/g-action"},
                ]
            }
        )
        h.rule_order = "DEFAULT_ACTION_ORDER"
        self.assertEqual(h._get_all_groups(), {"0123/g-action"})

    def test_aggregates_across_multiple_policies(self):
        h = self._handler()
        # Two policies in the collection, each contributing one in-scope group.
        h.policy_collection = {"p1", "p2"}
        h._nfw = _NfwDouble(
            policies={
                "p1": [{"ResourceArn": "0123/a-strict"}],
                "p2": [{"ResourceArn": "0123/b-strict"}],
            }
        )
        h.rule_order = "STRICT_ORDER"
        self.assertEqual(h._get_all_groups(), {"0123/a-strict", "0123/b-strict"})

    def test_reference_without_resource_arn_is_skipped(self):
        h = self._handler()
        policy_arn = next(iter(h.policy_collection))
        h._nfw = _NfwDouble(
            policies={
                policy_arn: [
                    {"Priority": 10},  # no ResourceArn
                    {"ResourceArn": "0123/keep-strict"},
                ]
            }
        )
        h.rule_order = "STRICT_ORDER"
        self.assertEqual(h._get_all_groups(), {"0123/keep-strict"})

    def test_policy_with_no_stateful_references_yields_empty(self):
        h = self._handler()
        policy_arn = next(iter(h.policy_collection))
        h._nfw = _NfwDouble(policies={policy_arn: []})
        h.rule_order = "STRICT_ORDER"
        self.assertEqual(h._get_all_groups(), set())

    def test_describe_policy_failure_is_swallowed_and_skipped(self):
        """A failed describe_firewall_policy must not raise; discovery continues
        and simply yields nothing for that policy."""
        h = self._handler()
        h.policy_collection = {"p1"}
        h._nfw = _NfwDouble(describe_policy_error=True)
        h.rule_order = "STRICT_ORDER"
        # Must not raise, and the broken policy contributes no groups.
        self.assertEqual(h._get_all_groups(), set())

    def test_ensure_group_tags_backfills_missing_tags(self):
        h = self._handler()
        double = _NfwDouble(tags_by_arn={"0123/untagged-strict": []})
        h._nfw = double
        h._ensure_group_tags({"0123/untagged-strict"})
        self.assertEqual(len(double.tag_calls), 1)
        arn, tags = double.tag_calls[0]
        self.assertEqual(arn, "0123/untagged-strict")
        tag_map = {t["Key"]: t["Value"] for t in tags}
        self.assertEqual(tag_map[RULEGROUP_OWNER_TAG_KEY], RULEGROUP_OWNER_TAG_VALUE)
        self.assertEqual(tag_map[RULEGROUP_STAGE_TAG_KEY], "int")

    def test_ensure_group_tags_skips_already_tagged_group(self):
        h = self._handler()
        double = _NfwDouble(
            tags_by_arn={
                "0123/tagged-strict": [
                    {"Key": RULEGROUP_OWNER_TAG_KEY, "Value": RULEGROUP_OWNER_TAG_VALUE},
                    {"Key": RULEGROUP_STAGE_TAG_KEY, "Value": "int"},
                ]
            }
        )
        h._nfw = double
        h._ensure_group_tags({"0123/tagged-strict"})
        self.assertEqual(double.tag_calls, [])

    def test_ensure_group_tags_empty_set_is_noop(self):
        h = self._handler()
        double = _NfwDouble()
        h._nfw = double
        h._ensure_group_tags(set())
        self.assertEqual(double.list_tag_calls, [])
        self.assertEqual(double.tag_calls, [])

    def test_ensure_group_tags_swallows_tagging_errors(self):
        """Tagging must never break rule processing: a tag_resource failure is
        logged and swallowed."""
        h = self._handler()
        double = _NfwDouble(
            tags_by_arn={"0123/boom-strict": []},
            tag_error_arns={"0123/boom-strict"},
        )
        h._nfw = double
        # Must not raise.
        h._ensure_group_tags({"0123/boom-strict"})
        self.assertEqual(double.tag_calls, [])

    def test_get_all_groups_invokes_tag_backfill(self):
        """End-to-end: discovery tags each discovered in-scope group that is
        missing ownership tags."""
        h = self._handler()
        policy_arn = next(iter(h.policy_collection))
        double = _NfwDouble(
            policies={policy_arn: [{"ResourceArn": "0123/fresh-strict"}]},
            tags_by_arn={"0123/fresh-strict": []},
        )
        h._nfw = double
        h.rule_order = "STRICT_ORDER"
        result = h._get_all_groups()
        self.assertEqual(result, {"0123/fresh-strict"})
        self.assertEqual([a for a, _ in double.tag_calls], ["0123/fresh-strict"])
