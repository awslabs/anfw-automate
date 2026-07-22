"""Unit tests for RunSweeper backstop.

Covers:
- S3 object discovery and deletion of aged artifacts
- NFW rule group discovery and deletion of aged artifacts
- Epoch parsing from run-id format in keys and names
- Never touches stable/baseline resources (no deletion of non-matching artifacts)
- Tolerates already-deleted artifacts
- Error recording

**Validates: Requirement 10.7**
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import time

import pytest
from botocore.exceptions import ClientError

from tests.integration.env.run_sweeper import (
    RunSweeper,
    SweepResult,
    _RUN_ID_PATTERN,
    _TWENTY_FOUR_HOURS_SECONDS,
)
from tests.integration.env.stable import IntEnv


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
    """A mocked boto3.Session."""
    session = MagicMock()
    s3_client = MagicMock()
    nfw_client = MagicMock()
    session.client.side_effect = lambda service: {
        "s3": s3_client,
        "network-firewall": nfw_client,
    }[service]
    return session


@pytest.fixture
def sweeper(int_env: IntEnv, mock_session: MagicMock) -> RunSweeper:
    """A RunSweeper with mocked AWS clients."""
    return RunSweeper(env=int_env, session=mock_session)


# ---------------------------------------------------------------------------
# SweepResult tests
# ---------------------------------------------------------------------------


class TestSweepResult:
    """Tests for the SweepResult dataclass."""

    def test_defaults_are_empty_lists(self):
        """Default fields are all empty lists."""
        result = SweepResult()
        assert result.deleted_keys == []
        assert result.deleted_rule_groups == []
        assert result.errors == []

    def test_with_values(self):
        """Can construct with populated fields."""
        result = SweepResult(
            deleted_keys=["int-aabb0011-1000/eu-west-1-config.yaml"],
            deleted_rule_groups=["rg-int-aabb0011-1000"],
            errors=["some error"],
        )
        assert len(result.deleted_keys) == 1
        assert len(result.deleted_rule_groups) == 1
        assert len(result.errors) == 1


# ---------------------------------------------------------------------------
# Epoch extraction tests
# ---------------------------------------------------------------------------


class TestEpochExtraction:
    """Tests for run-id epoch parsing logic."""

    def test_extracts_epoch_from_s3_key(self, sweeper: RunSweeper) -> None:
        """Should extract epoch from key like int-<sha>-<epoch>/file."""
        epoch = sweeper._extract_epoch_from_key(
            "int-abcdef01-1700000000/eu-west-1-config.yaml"
        )
        assert epoch == 1700000000

    def test_extracts_epoch_from_key_with_disambiguator(self, sweeper: RunSweeper) -> None:
        """Should extract epoch from key with disambiguator."""
        epoch = sweeper._extract_epoch_from_key(
            "int-abcdef01-1700000000-1/eu-west-1-config.yaml"
        )
        assert epoch == 1700000000

    def test_returns_none_for_non_matching_key(self, sweeper: RunSweeper) -> None:
        """Should return None for keys that don't match run-id pattern."""
        assert sweeper._extract_epoch_from_key("stable/config.yaml") is None
        assert sweeper._extract_epoch_from_key("some-random-key") is None

    def test_extracts_epoch_from_rule_group_name(self, sweeper: RunSweeper) -> None:
        """Should extract epoch from name like prefix-int-<sha>-<epoch>."""
        epoch = sweeper._extract_epoch_from_name(
            "anfw-rules-int-abcdef01-1700000000"
        )
        assert epoch == 1700000000

    def test_extracts_epoch_from_name_with_disambiguator(self, sweeper: RunSweeper) -> None:
        """Should extract epoch from name with disambiguator."""
        epoch = sweeper._extract_epoch_from_name(
            "anfw-rules-int-abcdef01-1700000000-2"
        )
        assert epoch == 1700000000

    def test_returns_none_for_non_matching_name(self, sweeper: RunSweeper) -> None:
        """Should return None for names that don't match run-id pattern."""
        assert sweeper._extract_epoch_from_name("stable-policy-group") is None
        assert sweeper._extract_epoch_from_name("baseline-reserved") is None


# ---------------------------------------------------------------------------
# S3 sweep tests
# ---------------------------------------------------------------------------


class TestS3Sweep:
    """Tests for S3 config object sweeping."""

    def test_deletes_aged_s3_objects(self, sweeper: RunSweeper) -> None:
        """Should delete S3 objects older than 24h. Req 10.7."""
        now = int(time.time())
        old_epoch = now - _TWENTY_FOUR_HOURS_SECONDS - 3600  # 25h ago

        # Set up paginator mock
        paginator_mock = MagicMock()
        sweeper._s3.get_paginator.return_value = paginator_mock
        paginator_mock.paginate.return_value = [
            {
                "Contents": [
                    {"Key": f"int-aabbccdd-{old_epoch}/eu-west-1-config.yaml"},
                    {"Key": f"int-aabbccdd-{old_epoch}/us-east-1-config.yaml"},
                ]
            }
        ]

        # NFW returns no rule groups
        nfw_paginator = MagicMock()
        sweeper._nfw.get_paginator.return_value = nfw_paginator
        nfw_paginator.paginate.return_value = [{"RuleGroups": []}]

        result = sweeper.sweep()

        assert len(result.deleted_keys) == 2
        assert sweeper._s3.delete_object.call_count == 2
        assert result.errors == []

    def test_skips_recent_s3_objects(self, sweeper: RunSweeper) -> None:
        """Should NOT delete S3 objects that are less than 24h old."""
        now = int(time.time())
        recent_epoch = now - 3600  # 1h ago (still fresh)

        paginator_mock = MagicMock()
        sweeper._s3.get_paginator.return_value = paginator_mock
        paginator_mock.paginate.return_value = [
            {
                "Contents": [
                    {"Key": f"int-aabbccdd-{recent_epoch}/eu-west-1-config.yaml"},
                ]
            }
        ]

        nfw_paginator = MagicMock()
        sweeper._nfw.get_paginator.return_value = nfw_paginator
        nfw_paginator.paginate.return_value = [{"RuleGroups": []}]

        result = sweeper.sweep()

        assert result.deleted_keys == []
        sweeper._s3.delete_object.assert_not_called()

    def test_skips_non_run_id_s3_objects(self, sweeper: RunSweeper) -> None:
        """Should skip S3 objects that don't match the run-id pattern."""
        paginator_mock = MagicMock()
        sweeper._s3.get_paginator.return_value = paginator_mock
        paginator_mock.paginate.return_value = [
            {
                "Contents": [
                    {"Key": "int-not-a-valid-runid/config.yaml"},
                ]
            }
        ]

        nfw_paginator = MagicMock()
        sweeper._nfw.get_paginator.return_value = nfw_paginator
        nfw_paginator.paginate.return_value = [{"RuleGroups": []}]

        result = sweeper.sweep()

        assert result.deleted_keys == []
        sweeper._s3.delete_object.assert_not_called()

    def test_tolerates_already_deleted_s3_object(self, sweeper: RunSweeper) -> None:
        """Should tolerate NoSuchKey on deletion (already gone)."""
        now = int(time.time())
        old_epoch = now - _TWENTY_FOUR_HOURS_SECONDS - 3600

        paginator_mock = MagicMock()
        sweeper._s3.get_paginator.return_value = paginator_mock
        paginator_mock.paginate.return_value = [
            {
                "Contents": [
                    {"Key": f"int-aabbccdd-{old_epoch}/gone.yaml"},
                ]
            }
        ]

        nfw_paginator = MagicMock()
        sweeper._nfw.get_paginator.return_value = nfw_paginator
        nfw_paginator.paginate.return_value = [{"RuleGroups": []}]

        error_response = {"Error": {"Code": "NoSuchKey", "Message": "Not found"}}
        sweeper._s3.delete_object.side_effect = ClientError(
            error_response, "DeleteObject"
        )

        result = sweeper.sweep()

        # NoSuchKey is not an error — the artifact is already gone
        assert result.errors == []
        assert result.deleted_keys == []

    def test_records_s3_deletion_error(self, sweeper: RunSweeper) -> None:
        """Should record errors when S3 deletion fails for non-404 reasons."""
        now = int(time.time())
        old_epoch = now - _TWENTY_FOUR_HOURS_SECONDS - 3600

        paginator_mock = MagicMock()
        sweeper._s3.get_paginator.return_value = paginator_mock
        paginator_mock.paginate.return_value = [
            {
                "Contents": [
                    {"Key": f"int-aabbccdd-{old_epoch}/stuck.yaml"},
                ]
            }
        ]

        nfw_paginator = MagicMock()
        sweeper._nfw.get_paginator.return_value = nfw_paginator
        nfw_paginator.paginate.return_value = [{"RuleGroups": []}]

        error_response = {"Error": {"Code": "AccessDenied", "Message": "Denied"}}
        sweeper._s3.delete_object.side_effect = ClientError(
            error_response, "DeleteObject"
        )

        result = sweeper.sweep()

        assert len(result.errors) == 1
        assert "stuck.yaml" in result.errors[0]
        assert result.deleted_keys == []

    def test_handles_empty_s3_bucket(self, sweeper: RunSweeper) -> None:
        """Should handle bucket with no matching objects gracefully."""
        paginator_mock = MagicMock()
        sweeper._s3.get_paginator.return_value = paginator_mock
        paginator_mock.paginate.return_value = [{}]  # No "Contents" key

        nfw_paginator = MagicMock()
        sweeper._nfw.get_paginator.return_value = nfw_paginator
        nfw_paginator.paginate.return_value = [{"RuleGroups": []}]

        result = sweeper.sweep()

        assert result.deleted_keys == []
        assert result.errors == []

    def test_records_error_when_s3_list_fails(self, sweeper: RunSweeper) -> None:
        """Should record error when S3 list_objects_v2 fails."""
        paginator_mock = MagicMock()
        sweeper._s3.get_paginator.return_value = paginator_mock
        error_response = {"Error": {"Code": "AccessDenied", "Message": "No access"}}
        paginator_mock.paginate.return_value.__iter__ = MagicMock(
            side_effect=ClientError(error_response, "ListObjectsV2")
        )

        nfw_paginator = MagicMock()
        sweeper._nfw.get_paginator.return_value = nfw_paginator
        nfw_paginator.paginate.return_value = [{"RuleGroups": []}]

        result = sweeper.sweep()

        assert len(result.errors) == 1
        assert "Failed to list S3 objects" in result.errors[0]


# ---------------------------------------------------------------------------
# NFW rule group sweep tests
# ---------------------------------------------------------------------------


class TestRuleGroupSweep:
    """Tests for Network Firewall rule group sweeping."""

    def test_deletes_aged_rule_groups(self, sweeper: RunSweeper) -> None:
        """Should delete rule groups older than 24h. Req 10.7."""
        now = int(time.time())
        old_epoch = now - _TWENTY_FOUR_HOURS_SECONDS - 3600  # 25h ago

        # S3 returns nothing
        s3_paginator = MagicMock()
        sweeper._s3.get_paginator.return_value = s3_paginator
        s3_paginator.paginate.return_value = [{}]

        # NFW returns aged rule groups
        nfw_paginator = MagicMock()
        sweeper._nfw.get_paginator.return_value = nfw_paginator
        nfw_paginator.paginate.return_value = [
            {
                "RuleGroups": [
                    {
                        "Name": f"anfw-rules-int-aabbccdd-{old_epoch}",
                        "Arn": f"arn:aws:network-firewall:eu-west-1:123:stateful-rulegroup/anfw-rules-int-aabbccdd-{old_epoch}",
                    },
                    {
                        "Name": f"anfw-custom-int-11223344-{old_epoch}",
                        "Arn": f"arn:aws:network-firewall:eu-west-1:123:stateful-rulegroup/anfw-custom-int-11223344-{old_epoch}",
                    },
                ]
            }
        ]

        result = sweeper.sweep()

        assert len(result.deleted_rule_groups) == 2
        assert sweeper._nfw.delete_rule_group.call_count == 2
        assert result.errors == []

    def test_skips_recent_rule_groups(self, sweeper: RunSweeper) -> None:
        """Should NOT delete rule groups less than 24h old."""
        now = int(time.time())
        recent_epoch = now - 3600  # 1h ago

        s3_paginator = MagicMock()
        sweeper._s3.get_paginator.return_value = s3_paginator
        s3_paginator.paginate.return_value = [{}]

        nfw_paginator = MagicMock()
        sweeper._nfw.get_paginator.return_value = nfw_paginator
        nfw_paginator.paginate.return_value = [
            {
                "RuleGroups": [
                    {
                        "Name": f"anfw-rules-int-aabbccdd-{recent_epoch}",
                        "Arn": "arn:...",
                    },
                ]
            }
        ]

        result = sweeper.sweep()

        assert result.deleted_rule_groups == []
        sweeper._nfw.delete_rule_group.assert_not_called()

    def test_skips_stable_rule_groups(self, sweeper: RunSweeper) -> None:
        """Should never touch rule groups without the int- run-id pattern."""
        s3_paginator = MagicMock()
        sweeper._s3.get_paginator.return_value = s3_paginator
        s3_paginator.paginate.return_value = [{}]

        nfw_paginator = MagicMock()
        sweeper._nfw.get_paginator.return_value = nfw_paginator
        nfw_paginator.paginate.return_value = [
            {
                "RuleGroups": [
                    # These do NOT contain 'int-' so won't even be listed
                    {"Name": "stable-baseline-rules", "Arn": "arn:..."},
                    {"Name": "production-default-deny", "Arn": "arn:..."},
                ]
            }
        ]

        result = sweeper.sweep()

        assert result.deleted_rule_groups == []
        sweeper._nfw.delete_rule_group.assert_not_called()

    def test_tolerates_already_deleted_rule_group(self, sweeper: RunSweeper) -> None:
        """Should tolerate ResourceNotFoundException (already gone)."""
        now = int(time.time())
        old_epoch = now - _TWENTY_FOUR_HOURS_SECONDS - 3600

        s3_paginator = MagicMock()
        sweeper._s3.get_paginator.return_value = s3_paginator
        s3_paginator.paginate.return_value = [{}]

        nfw_paginator = MagicMock()
        sweeper._nfw.get_paginator.return_value = nfw_paginator
        nfw_paginator.paginate.return_value = [
            {
                "RuleGroups": [
                    {
                        "Name": f"anfw-int-aabbccdd-{old_epoch}",
                        "Arn": "arn:...",
                    },
                ]
            }
        ]

        error_response = {
            "Error": {"Code": "ResourceNotFoundException", "Message": "Not found"}
        }
        sweeper._nfw.delete_rule_group.side_effect = ClientError(
            error_response, "DeleteRuleGroup"
        )

        result = sweeper.sweep()

        # ResourceNotFoundException is not an error — artifact is gone
        assert result.errors == []
        assert result.deleted_rule_groups == []

    def test_records_rule_group_deletion_error(self, sweeper: RunSweeper) -> None:
        """Should record errors when deletion fails for non-NotFound reasons."""
        now = int(time.time())
        old_epoch = now - _TWENTY_FOUR_HOURS_SECONDS - 3600

        s3_paginator = MagicMock()
        sweeper._s3.get_paginator.return_value = s3_paginator
        s3_paginator.paginate.return_value = [{}]

        nfw_paginator = MagicMock()
        sweeper._nfw.get_paginator.return_value = nfw_paginator
        nfw_paginator.paginate.return_value = [
            {
                "RuleGroups": [
                    {
                        "Name": f"anfw-int-aabbccdd-{old_epoch}",
                        "Arn": "arn:...",
                    },
                ]
            }
        ]

        error_response = {"Error": {"Code": "ThrottlingException", "Message": "Slow"}}
        sweeper._nfw.delete_rule_group.side_effect = ClientError(
            error_response, "DeleteRuleGroup"
        )

        result = sweeper.sweep()

        assert len(result.errors) == 1
        assert "anfw-int-aabbccdd" in result.errors[0]
        assert result.deleted_rule_groups == []

    def test_records_error_when_list_rule_groups_fails(self, sweeper: RunSweeper) -> None:
        """Should record error when list_rule_groups fails."""
        s3_paginator = MagicMock()
        sweeper._s3.get_paginator.return_value = s3_paginator
        s3_paginator.paginate.return_value = [{}]

        nfw_paginator = MagicMock()
        sweeper._nfw.get_paginator.return_value = nfw_paginator
        error_response = {"Error": {"Code": "AccessDenied", "Message": "No access"}}
        nfw_paginator.paginate.return_value.__iter__ = MagicMock(
            side_effect=ClientError(error_response, "ListRuleGroups")
        )

        result = sweeper.sweep()

        assert len(result.errors) == 1
        assert "Failed to list NFW rule groups" in result.errors[0]


# ---------------------------------------------------------------------------
# End-to-end sweep tests
# ---------------------------------------------------------------------------


class TestSweepEndToEnd:
    """End-to-end tests for the full sweep flow."""

    def test_mixed_aged_and_recent_artifacts(self, sweeper: RunSweeper) -> None:
        """Should delete only aged artifacts and leave recent ones."""
        now = int(time.time())
        old_epoch = now - _TWENTY_FOUR_HOURS_SECONDS - 3600  # 25h ago
        recent_epoch = now - 3600  # 1h ago

        s3_paginator = MagicMock()
        sweeper._s3.get_paginator.return_value = s3_paginator
        s3_paginator.paginate.return_value = [
            {
                "Contents": [
                    {"Key": f"int-aabbccdd-{old_epoch}/eu-west-1-config.yaml"},
                    {"Key": f"int-11223344-{recent_epoch}/us-east-1-config.yaml"},
                ]
            }
        ]

        nfw_paginator = MagicMock()
        sweeper._nfw.get_paginator.return_value = nfw_paginator
        nfw_paginator.paginate.return_value = [
            {
                "RuleGroups": [
                    {
                        "Name": f"anfw-int-aabbccdd-{old_epoch}",
                        "Arn": "arn:...",
                    },
                    {
                        "Name": f"anfw-int-11223344-{recent_epoch}",
                        "Arn": "arn:...",
                    },
                ]
            }
        ]

        result = sweeper.sweep()

        # Only old artifacts should be deleted
        assert len(result.deleted_keys) == 1
        assert str(old_epoch) in result.deleted_keys[0]

        assert len(result.deleted_rule_groups) == 1
        assert str(old_epoch) in result.deleted_rule_groups[0]

        # Exactly 1 S3 delete and 1 NFW delete
        assert sweeper._s3.delete_object.call_count == 1
        assert sweeper._nfw.delete_rule_group.call_count == 1

    def test_no_artifacts_found(self, sweeper: RunSweeper) -> None:
        """Should return empty result when no artifacts exist."""
        s3_paginator = MagicMock()
        sweeper._s3.get_paginator.return_value = s3_paginator
        s3_paginator.paginate.return_value = [{}]

        nfw_paginator = MagicMock()
        sweeper._nfw.get_paginator.return_value = nfw_paginator
        nfw_paginator.paginate.return_value = [{"RuleGroups": []}]

        result = sweeper.sweep()

        assert result.deleted_keys == []
        assert result.deleted_rule_groups == []
        assert result.errors == []

    def test_never_deletes_stable_resources(self, sweeper: RunSweeper) -> None:
        """Sweep never deletes the firewall policy, bucket, or stable stacks."""
        now = int(time.time())
        old_epoch = now - _TWENTY_FOUR_HOURS_SECONDS - 3600

        s3_paginator = MagicMock()
        sweeper._s3.get_paginator.return_value = s3_paginator
        s3_paginator.paginate.return_value = [
            {
                "Contents": [
                    {"Key": f"int-aabbccdd-{old_epoch}/eu-west-1-config.yaml"},
                ]
            }
        ]

        nfw_paginator = MagicMock()
        sweeper._nfw.get_paginator.return_value = nfw_paginator
        nfw_paginator.paginate.return_value = [
            {
                "RuleGroups": [
                    {
                        "Name": f"anfw-int-aabbccdd-{old_epoch}",
                        "Arn": "arn:...",
                    },
                ]
            }
        ]

        result = sweeper.sweep()

        # Verify NO calls to delete the bucket, policy, or firewall
        sweeper._s3.delete_bucket.assert_not_called()
        sweeper._nfw.delete_firewall_policy.assert_not_called()
        sweeper._nfw.delete_firewall.assert_not_called()

        # Verify S3 delete was only for the run-id-scoped key
        for c in sweeper._s3.delete_object.call_args_list:
            key = c[1]["Key"]
            assert "int-" in key
            assert str(old_epoch) in key

        # Verify NFW delete was only for the run-id-scoped group
        for c in sweeper._nfw.delete_rule_group.call_args_list:
            name = c[1]["RuleGroupName"]
            assert "int-" in name


# ---------------------------------------------------------------------------
# Run-id pattern tests
# ---------------------------------------------------------------------------


class TestRunIdPattern:
    """Tests for the _RUN_ID_PATTERN regex."""

    def test_matches_standard_run_id(self):
        """Should match int-<8hex>-<epoch>."""
        m = _RUN_ID_PATTERN.fullmatch("int-abcdef01-1700000000")
        assert m is not None
        assert m.group(1) == "1700000000"

    def test_matches_run_id_with_disambiguator(self):
        """Should match int-<8hex>-<epoch>-<number>."""
        m = _RUN_ID_PATTERN.fullmatch("int-abcdef01-1700000000-1")
        assert m is not None
        assert m.group(1) == "1700000000"

    def test_does_not_match_non_run_id(self):
        """Should not match strings that aren't run-ids."""
        assert _RUN_ID_PATTERN.fullmatch("stable-baseline") is None
        assert _RUN_ID_PATTERN.fullmatch("int-short-123") is None
        assert _RUN_ID_PATTERN.fullmatch("int-ABCDEF01-123") is None  # uppercase

    def test_search_finds_embedded_run_id(self):
        """Should find run-id pattern within a longer name."""
        m = _RUN_ID_PATTERN.search("anfw-rules-int-aabbccdd-1700000000")
        assert m is not None
        assert m.group(1) == "1700000000"
