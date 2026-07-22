"""Unit tests for FirewallInspector.

Covers:
- list_rule_group_names: filtering by run_id, pagination, empty results
- rule_names_in_group: parsing metadata rule_name from Suricata rules
- reserved_group_exists: detecting '-reserved' rule groups
- Error propagation from NFW client

**Validates: Requirements 9.1, 9.9**
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from tests.integration.env.stable import IntEnv
from tests.integration.harness.firewall_inspector import (
    FirewallInspector,
    _RULE_NAME_PATTERN,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def int_env() -> IntEnv:
    """A minimal IntEnv for testing."""
    return IntEnv(
        run_id="int-abcdef01-1700000000",
        account_id="123456789012",
        region="eu-west-1",
        config_bucket="int-config-bucket",
        vpc_id="vpc-abc123",
        firewall_policy_arn="arn:aws:network-firewall:eu-west-1:123456789012:firewall-policy/int-policy",
        xaccount_role_arn="arn:aws:iam::123456789012:role/xaccount-role",
        event_bus_arn="arn:aws:events:eu-west-1:123456789012:event-bus/config-bus",
    )


@pytest.fixture
def mock_session() -> MagicMock:
    """A mocked boto3.Session that returns a mock NFW client."""
    session = MagicMock()
    nfw_client = MagicMock()
    session.client.return_value = nfw_client
    return session


@pytest.fixture
def inspector(int_env: IntEnv, mock_session: MagicMock) -> FirewallInspector:
    """A FirewallInspector with a mocked NFW client."""
    return FirewallInspector(env=int_env, session=mock_session)


@pytest.fixture
def nfw_client(inspector: FirewallInspector) -> MagicMock:
    """Direct access to the mocked NFW client."""
    return inspector._nfw


# ---------------------------------------------------------------------------
# list_rule_group_names tests
# ---------------------------------------------------------------------------


class TestListRuleGroupNames:
    """Tests for FirewallInspector.list_rule_group_names."""

    def test_returns_groups_matching_run_id(self, inspector, nfw_client):
        """Should return only rule group names containing the run_id."""
        run_id = "int-abcdef01-1700000000"
        paginator = MagicMock()
        nfw_client.get_paginator.return_value = paginator
        paginator.paginate.return_value = [
            {
                "RuleGroups": [
                    {"Name": f"anfw-rules-{run_id}", "Arn": "arn:...1"},
                    {"Name": "anfw-rules-int-other-1699999999", "Arn": "arn:...2"},
                    {"Name": f"anfw-custom-{run_id}", "Arn": "arn:...3"},
                ]
            }
        ]

        result = inspector.list_rule_group_names(run_id)

        assert result == [f"anfw-rules-{run_id}", f"anfw-custom-{run_id}"]
        nfw_client.get_paginator.assert_called_once_with("list_rule_groups")
        paginator.paginate.assert_called_once_with(Type="STATEFUL")

    def test_returns_empty_list_when_no_match(self, inspector, nfw_client):
        """Should return empty list when no groups contain the run_id."""
        paginator = MagicMock()
        nfw_client.get_paginator.return_value = paginator
        paginator.paginate.return_value = [
            {
                "RuleGroups": [
                    {"Name": "anfw-rules-int-other-1699999999", "Arn": "arn:...1"},
                    {"Name": "anfw-stable-baseline", "Arn": "arn:...2"},
                ]
            }
        ]

        result = inspector.list_rule_group_names("int-ffffffff-9999999999")

        assert result == []

    def test_handles_multiple_pages(self, inspector, nfw_client):
        """Should paginate through multiple pages and collect all matches."""
        run_id = "int-aabb0011-1700000000"
        paginator = MagicMock()
        nfw_client.get_paginator.return_value = paginator
        paginator.paginate.return_value = [
            {
                "RuleGroups": [
                    {"Name": f"anfw-rules-{run_id}", "Arn": "arn:...1"},
                ]
            },
            {
                "RuleGroups": [
                    {"Name": f"anfw-custom-{run_id}", "Arn": "arn:...2"},
                ]
            },
        ]

        result = inspector.list_rule_group_names(run_id)

        assert len(result) == 2
        assert f"anfw-rules-{run_id}" in result
        assert f"anfw-custom-{run_id}" in result

    def test_handles_empty_rule_groups_list(self, inspector, nfw_client):
        """Should return empty list when no rule groups exist at all."""
        paginator = MagicMock()
        nfw_client.get_paginator.return_value = paginator
        paginator.paginate.return_value = [{"RuleGroups": []}]

        result = inspector.list_rule_group_names("int-abcdef01-1700000000")

        assert result == []

    def test_raises_on_client_error(self, inspector, nfw_client):
        """Should propagate ClientError from NFW list_rule_groups."""
        paginator = MagicMock()
        nfw_client.get_paginator.return_value = paginator
        paginator.paginate.side_effect = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
            "ListRuleGroups",
        )

        with pytest.raises(ClientError):
            inspector.list_rule_group_names("int-abcdef01-1700000000")


# ---------------------------------------------------------------------------
# rule_names_in_group tests
# ---------------------------------------------------------------------------


class TestRuleNamesInGroup:
    """Tests for FirewallInspector.rule_names_in_group."""

    def test_parses_rule_names_from_metadata(self, inspector, nfw_client):
        """Should extract rule_name from Suricata metadata in each rule."""
        rules_string = (
            'pass tls $HOME_NET any -> $EXTERNAL_NET any '
            '(tls.sni; content:"example.com"; startswith; nocase; '
            'metadata: rule_name 123456789012-abc123def4-a1b2c3d4e5; sid:1000001; rev:1;)\n'
            'pass tls $HOME_NET any -> $EXTERNAL_NET any '
            '(tls.sni; content:"test.org"; startswith; nocase; '
            'metadata: rule_name 123456789012-abc123def4-f6g7h8i9j0; sid:1000002; rev:1;)\n'
        )
        nfw_client.describe_rule_group.return_value = {
            "RuleGroup": {
                "RulesSource": {
                    "RulesString": rules_string,
                }
            },
            "RuleGroupResponse": {"RuleGroupName": "test-group"},
        }

        result = inspector.rule_names_in_group("test-group")

        assert result == [
            "123456789012-abc123def4-a1b2c3d4e5",
            "123456789012-abc123def4-f6g7h8i9j0",
        ]
        nfw_client.describe_rule_group.assert_called_once_with(
            RuleGroupName="test-group",
            Type="STATEFUL",
        )

    def test_returns_empty_when_no_rules_string(self, inspector, nfw_client):
        """Should return empty list when RulesString is absent."""
        nfw_client.describe_rule_group.return_value = {
            "RuleGroup": {
                "RulesSource": {}
            },
            "RuleGroupResponse": {"RuleGroupName": "empty-group"},
        }

        result = inspector.rule_names_in_group("empty-group")

        assert result == []

    def test_returns_empty_when_rules_have_no_metadata(self, inspector, nfw_client):
        """Should return empty list when rules lack metadata: rule_name."""
        rules_string = (
            'pass tls $HOME_NET any -> $EXTERNAL_NET any '
            '(tls.sni; content:"example.com"; sid:1000001; rev:1;)\n'
        )
        nfw_client.describe_rule_group.return_value = {
            "RuleGroup": {
                "RulesSource": {
                    "RulesString": rules_string,
                }
            },
            "RuleGroupResponse": {"RuleGroupName": "no-meta-group"},
        }

        result = inspector.rule_names_in_group("no-meta-group")

        assert result == []

    def test_skips_comment_lines(self, inspector, nfw_client):
        """Should skip comment lines starting with #."""
        rules_string = (
            '# This is a comment with metadata: rule_name fake-name;\n'
            'pass tls $HOME_NET any -> $EXTERNAL_NET any '
            '(tls.sni; content:"real.com"; startswith; nocase; '
            'metadata: rule_name real-rule-name; sid:1000001; rev:1;)\n'
        )
        nfw_client.describe_rule_group.return_value = {
            "RuleGroup": {
                "RulesSource": {
                    "RulesString": rules_string,
                }
            },
            "RuleGroupResponse": {"RuleGroupName": "comment-group"},
        }

        result = inspector.rule_names_in_group("comment-group")

        assert result == ["real-rule-name"]

    def test_raises_on_client_error(self, inspector, nfw_client):
        """Should propagate ClientError from describe_rule_group."""
        nfw_client.describe_rule_group.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Not found"}},
            "DescribeRuleGroup",
        )

        with pytest.raises(ClientError):
            inspector.rule_names_in_group("nonexistent-group")


# ---------------------------------------------------------------------------
# reserved_group_exists tests
# ---------------------------------------------------------------------------


class TestReservedGroupExists:
    """Tests for FirewallInspector.reserved_group_exists."""

    def test_returns_true_when_reserved_group_found(self, inspector, nfw_client):
        """Should return True if any group name contains '-reserved'."""
        paginator = MagicMock()
        nfw_client.get_paginator.return_value = paginator
        paginator.paginate.return_value = [
            {
                "RuleGroups": [
                    {"Name": "anfw-rules-int-abc-1700000000", "Arn": "arn:...1"},
                    {"Name": "anfw-default-deny-reserved", "Arn": "arn:...2"},
                ]
            }
        ]

        assert inspector.reserved_group_exists() is True

    def test_returns_false_when_no_reserved_group(self, inspector, nfw_client):
        """Should return False if no group name contains '-reserved'."""
        paginator = MagicMock()
        nfw_client.get_paginator.return_value = paginator
        paginator.paginate.return_value = [
            {
                "RuleGroups": [
                    {"Name": "anfw-rules-int-abc-1700000000", "Arn": "arn:...1"},
                    {"Name": "anfw-custom-rules", "Arn": "arn:...2"},
                ]
            }
        ]

        assert inspector.reserved_group_exists() is False

    def test_handles_empty_rule_groups(self, inspector, nfw_client):
        """Should return False when no rule groups exist."""
        paginator = MagicMock()
        nfw_client.get_paginator.return_value = paginator
        paginator.paginate.return_value = [{"RuleGroups": []}]

        assert inspector.reserved_group_exists() is False

    def test_handles_multiple_pages(self, inspector, nfw_client):
        """Should find reserved group across multiple pages."""
        paginator = MagicMock()
        nfw_client.get_paginator.return_value = paginator
        paginator.paginate.return_value = [
            {
                "RuleGroups": [
                    {"Name": "anfw-rules-normal", "Arn": "arn:...1"},
                ]
            },
            {
                "RuleGroups": [
                    {"Name": "anfw-policy-reserved", "Arn": "arn:...2"},
                ]
            },
        ]

        assert inspector.reserved_group_exists() is True

    def test_raises_on_client_error(self, inspector, nfw_client):
        """Should propagate ClientError from list_rule_groups."""
        paginator = MagicMock()
        nfw_client.get_paginator.return_value = paginator
        paginator.paginate.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "Oops"}},
            "ListRuleGroups",
        )

        with pytest.raises(ClientError):
            inspector.reserved_group_exists()


# ---------------------------------------------------------------------------
# Regex pattern tests
# ---------------------------------------------------------------------------


class TestRuleNamePattern:
    """Tests for the _RULE_NAME_PATTERN regex."""

    def test_matches_standard_metadata_format(self):
        """Should match rule_name within a metadata keyword."""
        line = (
            'pass tls $HOME_NET any -> $EXTERNAL_NET any '
            '(tls.sni; content:"x.com"; metadata: rule_name 123-abc-def; sid:1;)'
        )
        match = _RULE_NAME_PATTERN.search(line)
        assert match is not None
        assert match.group(1).strip() == "123-abc-def"

    def test_matches_with_multiple_metadata_fields(self):
        """Should match rule_name when other metadata fields are present."""
        line = (
            'pass tls $HOME_NET any -> $EXTERNAL_NET any '
            '(metadata: created_at 2024-01-01, rule_name my-rule-123; sid:1;)'
        )
        match = _RULE_NAME_PATTERN.search(line)
        assert match is not None
        assert match.group(1).strip() == "my-rule-123"

    def test_no_match_without_rule_name(self):
        """Should not match when metadata lacks rule_name."""
        line = (
            'pass tls $HOME_NET any -> $EXTERNAL_NET any '
            '(metadata: created_at 2024-01-01; sid:1;)'
        )
        match = _RULE_NAME_PATTERN.search(line)
        assert match is None
