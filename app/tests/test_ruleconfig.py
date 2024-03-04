from typing import Any
from unittest.mock import patch, MagicMock
from unittest import TestCase
import os
from yaml import safe_load
import json
from lib.rule_config import ConfigEntry, Protocols, DefaultDenyRules

test_vpc = "vpc-123123123123"
test_account = "123456789012"
test_region = "eu-central-1"
test_version = "1.0"


class TestConfigEntry(TestCase):

    def setUp(self) -> None:
        self.config_entry = ConfigEntry(
            test_vpc, test_account, test_region, test_version
        )

    def test_init(self):
        self.assertEqual(self.config_entry.vpc, test_vpc.replace("vpc-", ""))
        self.assertNotEqual(self.config_entry.vpc, test_vpc)
        self.assertEqual(self.config_entry.account, test_account)
        self.assertEqual(self.config_entry.region, test_region)
        self.assertEqual(self.config_entry.version, test_version)
        with open("data/protocols.yaml", "r") as p:
            protocol_config = Protocols(**safe_load(p))
            self.assertEqual(
                self.config_entry.custom_rule_protocols,
                protocol_config.CustomRuleProtocols,
            )
            self.assertEqual(
                self.config_entry.predefined_rule_protocols,
                protocol_config.PredfinedRuleProtocols,
            )

        with open("data/reserved_rules.yaml", "r") as d:
            default_deny_config = DefaultDenyRules(**safe_load(d))
            self.assertEqual(
                self.config_entry.default_deny_rules, default_deny_config.Rules
            )

    def random_helper(self, *args, **kwarg):
        return 10

    @patch("random.randrange", random_helper)
    def test_rule_entry_predefinde(self):
        # Test predefined
        self.config_entry.add_rule_entry(rule_key="https", rule=".amazonaws.com")
        test_generated_rules = {"123456789012-123123123123-96ccf8d27f"}
        test_rule = {
            "123456789012-123123123123-96ccf8d27f": 'pass tls $a123456789012123123123123 any -> $EXTERNAL_NET any (tls.sni; dotprefix; content:".amazonaws.com"; endswith; priority:1;flow:to_server, established; sid:10; rev:1; metadata: rule_name 123456789012-123123123123-96ccf8d27f;)'
        }
        self.assertEqual(self.config_entry.rules, test_rule)
        self.assertEqual(self.config_entry.generated_rules, test_generated_rules)
        ## Exceptions
        with self.assertRaises(self.config_entry.FormatError):
            self.config_entry.add_rule_entry(rule_key="So3thing", rule=".amazonaws.com")
        # test standard protocol but special port
        self.config_entry.add_rule_entry(rule_key="https", rule="special:4443")
        test_rule = {
            "123456789012-123123123123-96ccf8d27f": 'pass tls $a123456789012123123123123 any -> $EXTERNAL_NET any (tls.sni; dotprefix; content:".amazonaws.com"; endswith; priority:1;flow:to_server, established; sid:10; rev:1; metadata: rule_name 123456789012-123123123123-96ccf8d27f;)',
            "123456789012-123123123123-e68594a8cb": 'pass tls $a123456789012123123123123 any -> $EXTERNAL_NET 4443 (tls.sni; content:"special"; startswith; endswith; priority:1;flow:to_server, established; sid:10; rev:1; metadata: rule_name 123456789012-123123123123-e68594a8cb;)',
        }
        self.assertEqual(self.config_entry.rules, test_rule)
        # test non-port definition
        self.config_entry.add_rule_entry(rule_key="https", rule="special:not-a-port")
        test_rule = {
            "123456789012-123123123123-96ccf8d27f": 'pass tls $a123456789012123123123123 any -> $EXTERNAL_NET any (tls.sni; dotprefix; content:".amazonaws.com"; endswith; priority:1;flow:to_server, established; sid:10; rev:1; metadata: rule_name 123456789012-123123123123-96ccf8d27f;)',
            "123456789012-123123123123-e68594a8cb": 'pass tls $a123456789012123123123123 any -> $EXTERNAL_NET 4443 (tls.sni; content:"special"; startswith; endswith; priority:1;flow:to_server, established; sid:10; rev:1; metadata: rule_name 123456789012-123123123123-e68594a8cb;)',
            "123456789012-123123123123-c0f6b7d7f2": 'pass tls $a123456789012123123123123 any -> $EXTERNAL_NET any (tls.sni; content:"special:not-a-port"; startswith; endswith; priority:1;flow:to_server, established; sid:10; rev:1; metadata: rule_name 123456789012-123123123123-c0f6b7d7f2;)',
        }
        self.assertEqual(self.config_entry.rules, test_rule)

    @patch("random.randrange", random_helper)
    def test_rule_entry_custom(self):
        # Test custom
        self.config_entry.add_rule_entry(
            rule_key="custom",
            rule='pass http $a123456789012123123123123 any -> $EXTERNAL_NET any (http.host; content:".amazon.com"; startswith; endswith; flow:to_server, established;)',
        )
        test_generated_rule = {"123456789012-123123123123-2726ee0a97"}
        test_rule = {
            "123456789012-123123123123-2726ee0a97": 'pass http $a123456789012123123123123 any -> $EXTERNAL_NET any (http.host; content:".amazon.com"; startswith; endswith; flow:to_server, established;priority:1; sid:10; rev:1; metadata: rule_name 123456789012-123123123123-2726ee0a97;)'
        }
        self.assertEqual(self.config_entry.rules, test_rule)
        self.assertEqual(self.config_entry.generated_rules, test_generated_rule)
        ## Exceptions
        bad_test_rule = """pass http $a123456789012123123123123 any -> $EXTERNAL_NET any (http.host; content:".amazon.com"; startswith; endswith; flow:to_server, established; priority:1; sid:10; rev:1; metadata: rule_name meta-data-not-allowed;)"""
        with self.assertRaises(self.config_entry.FormatError):
            self.config_entry.add_rule_entry(rule_key="custom", rule=str(bad_test_rule))
        bad_test_rule_bad_proto = """pass http $a123456789012123123123123 any -> $EXTERNAL_NET any (bad.bad; content:".amazon.com"; startswith; endswith; flow:to_server, established;)"""
        with self.assertRaises(self.config_entry.NotSupportedProtocol):
            self.config_entry.add_rule_entry(
                rule_key="custom", rule=str(bad_test_rule_bad_proto)
            )
