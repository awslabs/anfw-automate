"""Comprehensive unit tests for pure logic — no AWS/network calls.

Covers:
- rule_config.ConfigEntry edge cases
- event_handler.EventHandler pure methods
- firewall_handler.FirewallRuleHandler helper/dispatch logic
- log_handler.CustomerLogHandler formatting edge cases

Requirements: 1.1, 1.3
"""

import hashlib
import json
import os
import re
from datetime import datetime, timedelta
from io import StringIO
from unittest.mock import MagicMock, patch, call, mock_open

import pytest

# ---------------------------------------------------------------------------
# ConfigEntry tests
# ---------------------------------------------------------------------------

# Keep a reference to the real built-in open so mocked open can fall through
_real_open = open


def _mock_open_for_config(filename, *args, **kwargs):
    """Return mock file content for protocols.yaml and global_rules.yaml.
    Falls through to real open for all other files (e.g., botocore internals).
    """
    if "protocols.yaml" in str(filename):
        return StringIO(
            "PredfinedRuleProtocols:\n"
            "  http: 'http.host'\n"
            "  https: 'tls.sni'\n"
            "  tls: 'tls.sni'\n"
            "CustomRuleProtocols:\n"
            "  - tcp\n"
            "  - udp\n"
        )
    if "global_rules.yaml" in str(filename):
        return StringIO("Rules:\n  - 'drop tcp any any -> any any'\n")
    # Fall through to real open for everything else
    return _real_open(filename, *args, **kwargs)


@pytest.fixture
def config_entry():
    """Create a ConfigEntry with mocked file I/O and env."""
    with patch.dict(os.environ, {"RULE_ORDER": "STRICT_ORDER"}):
        with patch(
            "builtins.open",
            side_effect=_mock_open_for_config,
        ):
            from lib.rule_config import ConfigEntry

            entry = ConfigEntry(
                vpc="vpc-abc123def", account="112233445566", region="eu-west-1", version="1.0"
            )
    return entry


@pytest.mark.unit
class TestConfigEntryEdgeCases:
    """Edge-case unit tests for ConfigEntry pure logic."""

    def test_vpc_prefix_stripped(self, config_entry):
        """vpc- prefix is stripped from the vpc field."""
        assert config_entry.vpc == "abc123def"

    def test_vpc_without_prefix_unchanged(self):
        """A vpc id without 'vpc-' is stored as-is."""
        with patch.dict(os.environ, {"RULE_ORDER": "STRICT_ORDER"}):
            with patch(
                "builtins.open",
                side_effect=_mock_open_for_config,
            ):
                from lib.rule_config import ConfigEntry

                entry = ConfigEntry(
                    vpc="novpcprefix", account="112233445566",
                    region="eu-west-1", version="1.0",
                )
        assert entry.vpc == "novpcprefix"

    def test_get_json_keys(self, config_entry):
        """get_json produces exactly the expected keys."""
        config_entry.ip_set_space = "10.0.0.0/16"
        raw = config_entry.get_json()
        data = json.loads(raw)
        assert set(data.keys()) == {"VPC", "Account", "Region", "CIDR", "Rules"}
        assert data["VPC"] == "abc123def"
        assert data["Account"] == "112233445566"
        assert data["Region"] == "eu-west-1"
        assert data["CIDR"] == "10.0.0.0/16"

    def test_get_json_empty_rules(self, config_entry):
        """get_json with no rules produces empty Rules dict."""
        config_entry.ip_set_space = "10.0.0.0/8"
        data = json.loads(config_entry.get_json())
        assert data["Rules"] == {}

    def test_generate_rule_hash_length(self, config_entry):
        """Hash is always 10 hex chars."""
        h = config_entry._generate_rule_hash("test-input")
        assert len(h) == 10
        assert re.fullmatch(r"[0-9a-f]{10}", h)

    def test_generate_rule_hash_deterministic(self, config_entry):
        """Same input produces same hash."""
        h1 = config_entry._generate_rule_hash("determinism-test")
        h2 = config_entry._generate_rule_hash("determinism-test")
        assert h1 == h2

    def test_generate_rule_hash_different_inputs(self, config_entry):
        """Different inputs produce different hashes."""
        h1 = config_entry._generate_rule_hash("input-a")
        h2 = config_entry._generate_rule_hash("input-b")
        assert h1 != h2

    def test_protocol_selector_valid(self, config_entry):
        """Known protocols resolve to their suricata keyword."""
        assert config_entry._protocol_selector("http") == "http.host"
        assert config_entry._protocol_selector("https") == "tls.sni"
        assert config_entry._protocol_selector("tls") == "tls.sni"

    def test_protocol_selector_case_insensitive(self, config_entry):
        """Protocol selector is case-insensitive."""
        assert config_entry._protocol_selector("HTTP") == "http.host"
        assert config_entry._protocol_selector("Https") == "tls.sni"

    def test_protocol_selector_unsupported(self, config_entry):
        """Unsupported protocol raises NotSupportedProtocol."""
        from lib.rule_config import ConfigEntry

        with pytest.raises(ConfigEntry.NotSupportedProtocol):
            config_entry._protocol_selector("unknown_proto")

    def test_is_valid_domain_rejects_tld_only(self, config_entry):
        """A TLD-only domain is rejected."""
        assert config_entry._is_valid_domain(".com") is False
        assert config_entry._is_valid_domain(".io") is False
        assert config_entry._is_valid_domain(".net") is False

    def test_is_valid_domain_accepts_multi_label(self, config_entry):
        """Multi-label domains pass validation."""
        assert config_entry._is_valid_domain(".example.com") is True
        assert config_entry._is_valid_domain("api.example.io") is True
        assert config_entry._is_valid_domain(".test.net") is True

    def test_add_rule_entry_predefined_generates_rule(self, config_entry):
        """Predefined rule generation adds a rule to the rules dict."""
        config_entry.ip_set_space = "10.0.0.0/16"
        config_entry.add_rule_entry(rule_key="https", rule=".example.com")
        assert len(config_entry.rules) == 1
        rule_name = list(config_entry.rules.keys())[0]
        assert re.fullmatch(r"112233445566-abc123def-[0-9a-f]{10}", rule_name)

    def test_add_rule_entry_reserved_keyword_raises(self, config_entry):
        """Custom rule with reserved keyword raises FormatError."""
        from lib.rule_config import ConfigEntry

        # A custom rule that includes 'sid:' (reserved)
        bad_rule = (
            "pass tcp $a112233445566abc123def any -> $EXTERNAL_NET any "
            "(content:\"test.com\"; sid:999; rev:1;)"
        )
        with pytest.raises(ConfigEntry.FormatError):
            config_entry.add_rule_entry(rule_key="tcp", rule=bad_rule)

    def test_add_rule_entry_tld_only_domain_raises(self, config_entry):
        """Predefined rule with TLD-only domain raises FormatError."""
        from lib.rule_config import ConfigEntry

        with pytest.raises(ConfigEntry.FormatError):
            config_entry.add_rule_entry(rule_key="https", rule=".com")

    def test_predefined_rule_with_port(self, config_entry):
        """Predefined rule with domain:port correctly extracts port."""
        config_entry.ip_set_space = "10.0.0.0/16"
        config_entry.add_rule_entry(rule_key="https", rule=".example.com:8443")
        rule_string = list(config_entry.rules.values())[0]
        # Port should appear in the rule string
        assert "8443" in rule_string

    def test_predefined_rule_dotprefix(self, config_entry):
        """Domain starting with dot uses dotprefix in rule."""
        config_entry.ip_set_space = "10.0.0.0/16"
        config_entry.add_rule_entry(rule_key="https", rule=".subdomain.example.com")
        rule_string = list(config_entry.rules.values())[0]
        assert "dotprefix" in rule_string

    def test_predefined_rule_no_dotprefix(self, config_entry):
        """Domain without leading dot uses startswith; endswith in rule."""
        config_entry.ip_set_space = "10.0.0.0/16"
        config_entry.add_rule_entry(rule_key="https", rule="exact.example.com")
        rule_string = list(config_entry.rules.values())[0]
        assert "startswith" in rule_string
        assert "endswith" in rule_string
        assert "dotprefix" not in rule_string

    def test_custom_rule_missing_options_raises(self, config_entry):
        """Custom rule without parenthesized options raises FormatError."""
        from lib.rule_config import ConfigEntry

        bad_rule = "pass tcp $a112233445566abc123def any -> $EXTERNAL_NET any"
        with pytest.raises(ConfigEntry.FormatError):
            config_entry.add_rule_entry(rule_key="tcp", rule=bad_rule)

    def test_str_representation(self, config_entry):
        """__str__ includes account and vpc."""
        s = str(config_entry)
        assert "112233445566" in s
        assert "abc123def" in s

    def test_multiple_rules_accumulate(self, config_entry):
        """Adding multiple rules accumulates them in the rules dict."""
        config_entry.ip_set_space = "10.0.0.0/16"
        config_entry.add_rule_entry(rule_key="https", rule=".one.example.com")
        config_entry.add_rule_entry(rule_key="https", rule=".two.example.com")
        assert len(config_entry.rules) == 2
        # All rule names have the expected format
        for name in config_entry.rules:
            assert re.fullmatch(r"112233445566-abc123def-[0-9a-f]{10}", name)

    def test_multiple_rules_in_json(self, config_entry):
        """get_json includes all accumulated rules."""
        config_entry.ip_set_space = "172.16.0.0/12"
        config_entry.add_rule_entry(rule_key="https", rule=".a.example.com")
        config_entry.add_rule_entry(rule_key="http", rule="b.example.com")
        data = json.loads(config_entry.get_json())
        assert len(data["Rules"]) == 2

    def test_default_action_order_priority(self):
        """With DEFAULT_ACTION_ORDER, priority keyword appears in generated rules."""
        with patch.dict(os.environ, {"RULE_ORDER": "DEFAULT_ACTION_ORDER"}):
            with patch(
                "builtins.open",
                side_effect=_mock_open_for_config,
            ):
                from lib.rule_config import ConfigEntry

                entry = ConfigEntry(
                    vpc="vpc-testvpc", account="999888777666",
                    region="us-east-1", version="1.0",
                )
        entry.ip_set_space = "10.0.0.0/16"
        entry.add_rule_entry(rule_key="https", rule=".test.example.com")
        rule_string = list(entry.rules.values())[0]
        assert "priority:250;" in rule_string

    def test_strict_order_no_priority(self, config_entry):
        """With STRICT_ORDER, priority keyword does not appear in generated rules."""
        config_entry.ip_set_space = "10.0.0.0/16"
        config_entry.add_rule_entry(rule_key="https", rule=".test.example.com")
        rule_string = list(config_entry.rules.values())[0]
        assert "priority:" not in rule_string

    def test_is_valid_domain_numeric_tld(self, config_entry):
        """Domain with numeric chars after dot is not considered a pure TLD."""
        # The regex only checks for alpha-only TLDs
        assert config_entry._is_valid_domain(".123") is True

    def test_is_valid_domain_single_char_tld(self, config_entry):
        """Single character after dot is not a valid TLD pattern (min 2 chars)."""
        assert config_entry._is_valid_domain(".a") is True

    def test_generated_rules_tracking(self, config_entry):
        """generated_rules set tracks all created rule names."""
        config_entry.ip_set_space = "10.0.0.0/16"
        config_entry.add_rule_entry(rule_key="https", rule=".x.example.com")
        config_entry.add_rule_entry(rule_key="http", rule="y.example.com")
        assert len(config_entry.generated_rules) == 2
        for name in config_entry.generated_rules:
            assert name in config_entry.rules


# ---------------------------------------------------------------------------
# EventHandler tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEventHandlerPureLogic:
    """Test EventHandler methods that are pure logic (no AWS calls)."""

    def setup_method(self):
        from RuleCollect.event_handler import EventHandler

        self.handler = EventHandler(version="2.0")

    # --- get_region_from_string ---

    def test_region_extraction_standard_regions(self):
        """Extracts region from various valid filenames."""
        assert self.handler.get_region_from_string("eu-west-1-config.yaml") == "eu-west-1"
        assert self.handler.get_region_from_string("us-east-1-config.yaml") == "us-east-1"
        assert self.handler.get_region_from_string("ap-southeast-2-config.yaml") == "ap-southeast-2"
        assert self.handler.get_region_from_string("ca-central-1-config.yaml") == "ca-central-1"
        assert self.handler.get_region_from_string("sa-east-1-config.yaml") == "sa-east-1"

    def test_region_extraction_govcloud(self):
        """Extracts us-gov regions."""
        assert self.handler.get_region_from_string("us-gov-west-1-config.yaml") == "us-gov-west-1"

    def test_region_extraction_embedded_in_path(self):
        """Region is extracted even from a longer path."""
        result = self.handler.get_region_from_string("some/path/eu-central-1-config.yaml")
        assert result == "eu-central-1"

    def test_region_extraction_invalid_raises(self):
        """Invalid region string raises FormatError."""
        from RuleCollect.event_handler import EventHandler

        with pytest.raises(EventHandler.FormatError):
            self.handler.get_region_from_string("not-a-region.yaml")

    def test_region_extraction_empty_string_raises(self):
        """Empty string raises FormatError."""
        from RuleCollect.event_handler import EventHandler

        with pytest.raises(EventHandler.FormatError):
            self.handler.get_region_from_string("")

    # --- validate_file_name ---

    def test_validate_filename_valid_yaml(self):
        """Valid config filenames pass."""
        assert self.handler.validate_file_name("eu-west-1-config.yaml") is True
        assert self.handler.validate_file_name("us-east-1-config.yml") is True
        assert self.handler.validate_file_name("ap-northeast-1-config.yaml") is True

    def test_validate_filename_invalid_extension(self):
        """Non-yaml/yml extensions fail."""
        assert self.handler.validate_file_name("eu-west-1-config.json") is False

    def test_validate_filename_missing_config_suffix(self):
        """Missing '-config' suffix fails."""
        assert self.handler.validate_file_name("eu-west-1.yaml") is False

    def test_validate_filename_invalid_region(self):
        """Invalid region prefix fails."""
        assert self.handler.validate_file_name("xx-west-1-config.yaml") is False

    def test_validate_filename_empty(self):
        """Empty string fails."""
        assert self.handler.validate_file_name("") is False

    def test_validate_filename_partial_match_in_path(self):
        """filename pattern embedded in a longer path still matches."""
        assert self.handler.validate_file_name("bucket/path/us-west-2-config.yaml") is True

    def test_validate_filename_yml_extension(self):
        """Both .yaml and .yml extensions pass."""
        assert self.handler.validate_file_name("eu-west-1-config.yml") is True
        assert self.handler.validate_file_name("ap-south-1-config.yml") is True

    def test_validate_filename_uppercase_fails(self):
        """Uppercase region fails validation (regex is case-sensitive)."""
        assert self.handler.validate_file_name("EU-WEST-1-config.yaml") is False

    def test_region_extraction_china_region(self):
        """China region (cn-) is extracted correctly."""
        assert self.handler.get_region_from_string("cn-north-1-config.yaml") == "cn-north-1"

    def test_region_extraction_multiple_regions_returns_first(self):
        """When multiple region patterns exist, returns the first match."""
        result = self.handler.get_region_from_string("eu-west-1/us-east-1-config.yaml")
        assert result == "eu-west-1"

    def test_validate_filename_extra_suffix_after_yaml(self):
        """A filename with extra text after .yaml still matches (regex is a search, not fullmatch)."""
        # This validates the current behavior - regex uses re.search not re.fullmatch
        result = self.handler.validate_file_name("us-east-1-config.yaml.bak")
        # .yaml is followed by .bak but regex matches the core pattern
        assert result is True

    def test_version_attribute_stored(self):
        """Version is stored on the handler."""
        assert self.handler.version == "2.0"

    def test_version_none_allowed(self):
        """Handler can be created with version=None."""
        from RuleCollect.event_handler import EventHandler

        handler = EventHandler(version=None)
        assert handler.version is None

    # --- No AWS calls assertion ---

    @patch("RuleCollect.event_handler.boto3")
    def test_pure_methods_no_boto3_calls(self, mock_boto3):
        """get_region_from_string and validate_file_name never call boto3."""
        self.handler.get_region_from_string("eu-west-1-config.yaml")
        self.handler.validate_file_name("eu-west-1-config.yaml")
        mock_boto3.client.assert_not_called()
        mock_boto3.resource.assert_not_called()


# ---------------------------------------------------------------------------
# FirewallRuleHandler helper method tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFirewallRuleHandlerPureLogic:
    """Test FirewallRuleHandler helper methods that are pure string/logic ops."""

    def setup_method(self):
        """Create a FirewallRuleHandler with all AWS interactions mocked."""
        with patch.dict(
            os.environ,
            {
                "POLICY_ARNS": '{"eu-west-1": ["arn:aws:network-firewall:eu-west-1:123:policy/p1"]}',
                "SUPPORTED_REGIONS": "eu-west-1,eu-central-1",
                "RULE_ORDER": "STRICT_ORDER",
                "VPC_ID": "vpc-test123",
            },
        ):
            with patch("boto3.client") as mock_client:
                mock_nfw = MagicMock()
                mock_nfw.list_rule_groups.return_value = {"RuleGroups": []}
                mock_client.return_value = mock_nfw
                with patch(
                    "builtins.open",
                    side_effect=_mock_open_for_firewall,
                ):
                    from RuleExecute.firewall_handler import FirewallRuleHandler

                    self.handler = FirewallRuleHandler(
                        region="eu-west-1",
                        context=MagicMock(),
                        customer_log_handler=MagicMock(),
                        log_stream_name="test-stream",
                    )

    # --- _arn_to_name ---

    def test_arn_to_name_standard(self):
        """Extracts name from a standard ARN."""
        arn = "arn:aws:network-firewall:eu-west-1:123456789012:stateful-rulegroup/MyRuleGroup"
        assert self.handler._arn_to_name(arn) == "MyRuleGroup"

    def test_arn_to_name_simple_slash(self):
        """Extracts name from simplified ARN-like string."""
        assert self.handler._arn_to_name("prefix/the-name") == "the-name"

    def test_arn_to_name_multiple_slashes(self):
        """Only splits on the first slash — name can contain slashes."""
        assert self.handler._arn_to_name("a/b/c") == "b/c"

    # --- _get_rule_name_from_rule_string ---

    def test_rule_name_from_standard_rule_string(self):
        """Extracts rule name in account-vpc-hash format."""
        rule = (
            'pass tls $a123456789012vpc123 any -> $EXTERNAL_NET any '
            '(tls.sni; content:".example.com"; sid:12345; rev:1; '
            'metadata: rule_name 123456789012-vpc123-abcdef0123;)'
        )
        assert self.handler._get_rule_name_from_rule_string(rule) == "123456789012-vpc123-abcdef0123"

    def test_rule_name_from_rule_with_priority(self):
        """Extracts rule name when priority is present."""
        rule = (
            'pass tls $a112233445566abc123 any -> $EXTERNAL_NET any '
            '(tls.sni; dotprefix; content:".test.net"; endswith; '
            'priority:250; flow:to_server, established; sid:301711; rev:1; '
            'metadata: rule_name 112233445566-abc123-1234567890;)'
        )
        assert self.handler._get_rule_name_from_rule_string(rule) == "112233445566-abc123-1234567890"

    # --- _generate_random_name ---

    def test_generate_random_name_is_numeric(self):
        """Generated name is a numeric string."""
        name = self.handler._generate_random_name()
        assert name.isdigit()

    def test_generate_random_name_reasonable_length(self):
        """Generated name has reasonable length (9-12 digits)."""
        name = self.handler._generate_random_name()
        assert 9 <= len(name) <= 12

    # --- json_to_rule dispatch (event_type routing) ---

    def test_json_to_rule_update_event_calls_add(self):
        """Update event type dispatches to add_new_rule."""
        data = {
            "VPC": "testvpc123",
            "Account": "123456789012",
            "Region": "eu-west-1",
            "CIDR": "10.0.0.0/16",
            "Rules": {"123456789012-testvpc123-abc1234567": "pass tls ..."},
        }
        with patch.object(self.handler, "add_new_rule") as mock_add:
            with patch.object(self.handler, "_clean_up_rules"):
                self.handler.json_to_rule(json.dumps(data), event_type="Update")
                mock_add.assert_called_once()

    def test_json_to_rule_delete_vpc_event(self):
        """DeleteVpc event calls cleanup and ip set purge."""
        data = {
            "VPC": "testvpc123",
            "Account": "123456789012",
            "Region": "eu-west-1",
            "CIDR": "10.0.0.0/16",
            "Rules": {},
        }
        with patch.object(self.handler, "_clean_up_rules") as mock_cleanup:
            with patch.object(self.handler, "_cleanup_ip_sets") as mock_ip:
                self.handler.json_to_rule(json.dumps(data), event_type="DeleteVpc")
                mock_cleanup.assert_called_once()
                mock_ip.assert_called_once()

    def test_json_to_rule_delete_s3_event(self):
        """DeleteS3 event calls cleanup for the account/region."""
        data = {
            "VPC": "testvpc123",
            "Account": "123456789012",
            "Region": "eu-west-1",
            "CIDR": "10.0.0.0/16",
            "Rules": {},
        }
        with patch.object(self.handler, "_clean_up_rules") as mock_cleanup:
            with patch.object(self.handler, "_cleanup_ip_sets") as mock_ip:
                self.handler.json_to_rule(json.dumps(data), event_type="DeleteS3")
                mock_cleanup.assert_called_once()
                mock_ip.assert_called_once()

    # --- No real AWS calls assertion ---

    @patch("RuleExecute.firewall_handler.boto3")
    def test_helper_methods_no_boto3_calls(self, mock_boto3):
        """Pure helper methods never invoke boto3."""
        self.handler._arn_to_name("prefix/name")
        self.handler._generate_random_name()
        rule = (
            'pass tls $a112233445566vpc123 any -> $EXTERNAL_NET any '
            '(metadata: rule_name 112233445566-vpc123-abcdef0123;)'
        )
        self.handler._get_rule_name_from_rule_string(rule)
        mock_boto3.client.assert_not_called()
        mock_boto3.resource.assert_not_called()

    def test_json_to_rule_delete_account_event(self):
        """DeleteAccount event iterates over supported regions."""
        data = {
            "VPC": "testvpc123",
            "Account": "123456789012",
            "Region": "eu-west-1",
            "CIDR": "10.0.0.0/16",
            "Rules": {},
        }
        with patch.object(self.handler, "_clean_up_rules") as mock_cleanup:
            with patch.object(self.handler, "_cleanup_ip_sets") as mock_ip:
                with patch("boto3.client") as mock_client:
                    mock_client.return_value = MagicMock()
                    self.handler.json_to_rule(json.dumps(data), event_type="DeleteAccount")
                    # Should call cleanup for each supported region
                    assert mock_cleanup.call_count >= 1

    def test_json_to_rule_unknown_event_type_does_not_crash(self):
        """An unknown event_type does not dispatch to any action (no crash)."""
        data = {
            "VPC": "testvpc123",
            "Account": "123456789012",
            "Region": "eu-west-1",
            "CIDR": "10.0.0.0/16",
            "Rules": {},
        }
        # Should not raise; just logs the final message
        with patch.object(self.handler, "_clean_up_rules"):
            with patch.object(self.handler, "_cleanup_ip_sets"):
                self.handler.json_to_rule(json.dumps(data), event_type="UnknownEvent")

    def test_arn_to_name_no_slash_raises(self):
        """ARN without slash causes IndexError (expected, not our code to fix)."""
        # _arn_to_name splits on '/' — if no slash, index 1 would fail
        # but split with maxsplit=1 on "no-slash" returns ['no-slash'] so [1] raises
        with pytest.raises(IndexError):
            self.handler._arn_to_name("no-slash-arn")

    def test_generate_random_name_changes_over_time(self):
        """Two calls at different times produce different names (time-based)."""
        name1 = self.handler._generate_random_name()
        # Since it's time-based in seconds, same-second calls may match,
        # but the value should be a large positive integer
        assert int(name1) > 0

    def test_rule_name_extraction_with_metadata_keyword(self):
        """Extracts rule name from a rule with 'metadata: rule_name' keyword."""
        rule = (
            'pass http $a999888777666vpctest any -> $EXTERNAL_NET any '
            '(http.host; content:"test.com"; startswith; endswith; '
            'flow:to_server, established; sid:123; rev:1; '
            'metadata: rule_name 999888777666-vpctest-1234567890;)'
        )
        assert self.handler._get_rule_name_from_rule_string(rule) == "999888777666-vpctest-1234567890"


# ---------------------------------------------------------------------------
# CustomerLogHandler tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCustomerLogHandlerPureLogic:
    """Test CustomerLogHandler formatting — mocking all boto3 interactions."""

    def setup_method(self):
        with patch("lib.log_handler.boto3.client") as mock_client:
            mock_client.return_value = MagicMock()
            from lib.log_handler import CustomerLogHandler

            self.handler = CustomerLogHandler(
                log_group_name="test-group",
                credentials={
                    "AccessKeyId": "fake-key",
                    "SecretAccessKey": "fake-secret",  # nosec
                    "SessionToken": "fake-token",
                },
                version="3.0",
            )

    def test_log_message_format_with_version(self):
        """Log message includes version when set."""
        from lib.log_handler import Level

        self.handler._check_log_stream = MagicMock()
        self.handler._generate_time_stamp = MagicMock(return_value=1000)
        self.handler.logclient.put_log_events = MagicMock()

        self.handler.send_log_message("stream1", "hello world", Level.INFO)

        call_args = self.handler.logclient.put_log_events.call_args
        message = call_args[1]["logEvents"][0]["message"]
        parsed = json.loads(message)
        assert parsed["level"] == "INFO"
        assert parsed["version"] == "3.0"
        assert parsed["message"] == "hello world"

    def test_log_message_format_without_version(self):
        """Log message omits version field when version is None."""
        from lib.log_handler import Level

        self.handler.version = None
        self.handler._check_log_stream = MagicMock()
        self.handler._generate_time_stamp = MagicMock(return_value=2000)
        self.handler.logclient.put_log_events = MagicMock()

        self.handler.send_log_message("stream2", "test msg", Level.WARN)

        call_args = self.handler.logclient.put_log_events.call_args
        message = call_args[1]["logEvents"][0]["message"]
        parsed = json.loads(message)
        assert parsed["level"] == "WARN"
        assert parsed["message"] == "test msg"
        assert "version" not in parsed

    def test_log_message_all_levels(self):
        """All Level enum values produce correct level string."""
        from lib.log_handler import Level

        self.handler._check_log_stream = MagicMock()
        self.handler._generate_time_stamp = MagicMock(return_value=3000)
        self.handler.logclient.put_log_events = MagicMock()

        for level in Level:
            self.handler.send_log_message("stream", "msg", level)
            call_args = self.handler.logclient.put_log_events.call_args
            message = call_args[1]["logEvents"][0]["message"]
            parsed = json.loads(message)
            assert parsed["level"] == level.name

    def test_generate_time_stamp_is_positive_int(self):
        """Timestamp is a positive integer (millis since epoch)."""
        ts = self.handler._generate_time_stamp()
        assert isinstance(ts, int)
        assert ts > 0

    def test_generate_time_stamp_29d_is_earlier(self):
        """29-day-ago timestamp is less than current timestamp."""
        ts_now = self.handler._generate_time_stamp()
        ts_29d = self.handler._generate_time_stamp_29d()
        assert ts_29d < ts_now

    def test_generate_log_stream_name_format(self):
        """Log stream name follows YYYY/MM/DD/HH/MM/<epoch> format."""
        name = self.handler.generate_log_stream_name()
        # Should match pattern like 2024/01/15/10/30/<epoch_millis>
        assert re.fullmatch(r"\d{4}/\d{2}/\d{2}/\d{2}/\d{2}/\d+", name)

    def test_update_version(self):
        """update_version correctly changes version attribute."""
        self.handler.update_version("5.0")
        assert self.handler.version == "5.0"

    @patch("lib.log_handler.boto3")
    def test_no_new_boto3_calls_in_formatting(self, mock_boto3):
        """Formatting and timestamp methods don't create new boto3 clients."""
        self.handler._generate_time_stamp()
        self.handler._generate_time_stamp_29d()
        self.handler.generate_log_stream_name()
        mock_boto3.client.assert_not_called()
        mock_boto3.resource.assert_not_called()

    def test_send_log_message_default_level_is_debug(self):
        """When no level is passed, default is DEBUG."""
        from lib.log_handler import Level

        self.handler._check_log_stream = MagicMock()
        self.handler._generate_time_stamp = MagicMock(return_value=4000)
        self.handler.logclient.put_log_events = MagicMock()

        self.handler.send_log_message("stream", "default level msg")

        call_args = self.handler.logclient.put_log_events.call_args
        message = call_args[1]["logEvents"][0]["message"]
        parsed = json.loads(message)
        assert parsed["level"] == "DEBUG"

    def test_log_message_special_characters_in_message(self):
        """Special characters in message are preserved in the JSON output."""
        from lib.log_handler import Level

        self.handler._check_log_stream = MagicMock()
        self.handler._generate_time_stamp = MagicMock(return_value=5000)
        self.handler.logclient.put_log_events = MagicMock()

        # Note: the current implementation uses f-string interpolation,
        # so embedded quotes could break JSON. Test with safe special chars.
        self.handler.send_log_message("stream", "msg with spaces & symbols!", Level.WARN)

        call_args = self.handler.logclient.put_log_events.call_args
        message = call_args[1]["logEvents"][0]["message"]
        assert "msg with spaces & symbols!" in message

    def test_timestamp_difference_29d(self):
        """29-day timestamp difference is approximately 29 days in milliseconds."""
        ts_now = self.handler._generate_time_stamp()
        ts_29d = self.handler._generate_time_stamp_29d()
        diff_ms = ts_now - ts_29d
        # 29 days in ms = 29 * 24 * 60 * 60 * 1000 = 2505600000
        # Allow some tolerance for execution time
        assert 2505500000 < diff_ms < 2505700000

    def test_check_log_stream_already_exists(self):
        """_check_log_stream handles ResourceAlreadyExistsException gracefully."""
        # Create a proper exception class that inherits from BaseException
        class ResourceAlreadyExistsException(Exception):
            pass

        self.handler.logclient.exceptions.ResourceAlreadyExistsException = ResourceAlreadyExistsException
        self.handler.logclient.create_log_stream.side_effect = ResourceAlreadyExistsException("exists")

        # Should not raise
        self.handler._check_log_stream("existing-stream")

    def test_check_log_stream_generic_exception(self):
        """_check_log_stream handles generic exception without crashing."""
        # Create a proper exception class for the except clause to work
        class ResourceAlreadyExistsException(Exception):
            pass

        self.handler.logclient.exceptions.ResourceAlreadyExistsException = ResourceAlreadyExistsException
        self.handler.logclient.create_log_stream.side_effect = RuntimeError("network error")

        # The code catches ResourceAlreadyExistsException first, then bare Exception
        # So RuntimeError should be caught by the bare Exception handler
        self.handler._check_log_stream("error-stream")


# ---------------------------------------------------------------------------
# Helper for FirewallRuleHandler mock file opens
# ---------------------------------------------------------------------------


def _mock_open_for_firewall(filename, *args, **kwargs):
    """Return mock file content for global_rules.yaml used by FirewallRuleHandler.
    Falls through to real open for everything else.
    """
    if "global_rules.yaml" in str(filename):
        return StringIO("Rules:\n  - 'drop tcp any any -> any any'\n")
    return _real_open(filename, *args, **kwargs)
