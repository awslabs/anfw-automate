"""Unit tests for MutationCleaner.revert + baseline capture.

Covers:
- S3 config object deletion with retry (tolerate NoSuchKey)
- Network Firewall rule group deletion with retry (tolerate ResourceNotFoundException)
- Firewall policy restore to captured baseline
- Never touches stable/baseline resources
- Records failures after 3 attempts
- Idempotent revert (already-deleted artifacts)

**Validates: Requirements 10.1, 10.3, 10.4, 10.5, 10.8, 10.9**
**Property 10: Guaranteed mutation revert**
**Property 16: Stable-resource safety**
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch, call

import pytest
from botocore.exceptions import ClientError

from tests.integration.env.mutation_cleaner import (
    MutationCleaner,
    RevertResult,
    _MAX_RETRIES,
)
from tests.integration.env.run_scope import RunScope
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
    session.client.side_effect = lambda service: {
        "s3": MagicMock(),
        "network-firewall": MagicMock(),
    }[service]
    return session


@pytest.fixture
def cleaner(int_env: IntEnv, mock_session: MagicMock) -> MutationCleaner:
    """A MutationCleaner with mocked AWS clients."""
    return MutationCleaner(env=int_env, session=mock_session)


@pytest.fixture
def scope() -> RunScope:
    """A RunScope with sample tracked artifacts."""
    s = RunScope(run_id="int-abcdef01-1700000000")
    s.config_keys = [
        "int-abcdef01-1700000000/eu-west-1-config.yaml",
        "int-abcdef01-1700000000/us-east-1-config.yaml",
    ]
    s.rule_group_names = [
        "anfw-rules-int-abcdef01-1700000000",
        "anfw-custom-int-abcdef01-1700000000",
    ]
    return s


# ---------------------------------------------------------------------------
# RevertResult tests
# ---------------------------------------------------------------------------


class TestRevertResult:
    """Tests for the RevertResult dataclass."""

    def test_default_empty_failures(self):
        """Default failed_artifacts is empty list."""
        result = RevertResult(mutations_reverted=True, baseline_restored=True)
        assert result.failed_artifacts == []

    def test_with_failures(self):
        """Can record failed artifact names."""
        result = RevertResult(
            mutations_reverted=False,
            baseline_restored=True,
            failed_artifacts=["s3://bucket/key1", "rule-group:rg-1"],
        )
        assert len(result.failed_artifacts) == 2
        assert not result.mutations_reverted


# ---------------------------------------------------------------------------
# capture_baseline tests
# ---------------------------------------------------------------------------


class TestCaptureBaseline:
    """Tests for MutationCleaner.capture_baseline(). Req 10.8."""

    def test_captures_stateful_references(self, cleaner: MutationCleaner) -> None:
        """Should store the current stateful rule group references."""
        baseline_refs = [
            {"ResourceArn": "arn:aws:network-firewall:eu-west-1:123:stateful-rulegroup/stable-rg-1"},
            {"ResourceArn": "arn:aws:network-firewall:eu-west-1:123:stateful-rulegroup/stable-rg-2"},
        ]
        cleaner._nfw.describe_firewall_policy.return_value = {
            "FirewallPolicy": {
                "StatefulRuleGroupReferences": baseline_refs,
                "StatelessDefaultActions": ["aws:forward_to_sfe"],
                "StatelessFragmentDefaultActions": ["aws:forward_to_sfe"],
            },
            "UpdateToken": "token-123",
        }

        cleaner.capture_baseline()

        assert cleaner._baseline_rule_group_references == baseline_refs
        cleaner._nfw.describe_firewall_policy.assert_called_once_with(
            FirewallPolicyArn=cleaner._env.firewall_policy_arn
        )

    def test_captures_empty_references(self, cleaner: MutationCleaner) -> None:
        """Should handle a policy with no stateful references."""
        cleaner._nfw.describe_firewall_policy.return_value = {
            "FirewallPolicy": {
                "StatelessDefaultActions": ["aws:forward_to_sfe"],
                "StatelessFragmentDefaultActions": ["aws:forward_to_sfe"],
            },
            "UpdateToken": "token-456",
        }

        cleaner.capture_baseline()

        assert cleaner._baseline_rule_group_references == []


# ---------------------------------------------------------------------------
# S3 deletion tests
# ---------------------------------------------------------------------------


class TestS3Deletion:
    """Tests for S3 config object deletion within revert."""

    def test_deletes_all_config_keys(
        self, cleaner: MutationCleaner, scope: RunScope
    ) -> None:
        """Should call delete_object for each config key. Req 10.1."""
        # Set up baseline so restore works
        cleaner._baseline_rule_group_references = []
        cleaner._nfw.describe_firewall_policy.return_value = {
            "FirewallPolicy": {"StatelessDefaultActions": ["aws:forward_to_sfe"],
                               "StatelessFragmentDefaultActions": ["aws:forward_to_sfe"]},
            "UpdateToken": "token-abc",
        }
        cleaner._nfw.update_firewall_policy.return_value = {}

        result = cleaner.revert(scope)

        assert cleaner._s3.delete_object.call_count == 2
        calls = cleaner._s3.delete_object.call_args_list
        assert calls[0] == call(
            Bucket="int-config-bucket",
            Key="int-abcdef01-1700000000/eu-west-1-config.yaml",
        )
        assert calls[1] == call(
            Bucket="int-config-bucket",
            Key="int-abcdef01-1700000000/us-east-1-config.yaml",
        )

    def test_tolerates_no_such_key(
        self, cleaner: MutationCleaner
    ) -> None:
        """Should tolerate NoSuchKey (already deleted). Req 10.5."""
        cleaner._baseline_rule_group_references = []
        cleaner._nfw.describe_firewall_policy.return_value = {
            "FirewallPolicy": {"StatelessDefaultActions": ["aws:forward_to_sfe"],
                               "StatelessFragmentDefaultActions": ["aws:forward_to_sfe"]},
            "UpdateToken": "token-abc",
        }
        cleaner._nfw.update_firewall_policy.return_value = {}

        error_response = {"Error": {"Code": "NoSuchKey", "Message": "Not found"}}
        cleaner._s3.delete_object.side_effect = ClientError(error_response, "DeleteObject")

        scope = RunScope(
            run_id="int-abcdef01-1700000000",
            config_keys=["int-abcdef01-1700000000/gone.yaml"],
            rule_group_names=[],
        )

        result = cleaner.revert(scope)
        assert result.mutations_reverted is True
        assert "gone.yaml" not in str(result.failed_artifacts)

    @patch("tests.integration.env.mutation_cleaner.time.sleep")
    def test_retries_on_transient_error(
        self, mock_sleep: MagicMock, cleaner: MutationCleaner
    ) -> None:
        """Should retry up to 3 times on transient S3 errors. Req 10.9."""
        cleaner._baseline_rule_group_references = []
        cleaner._nfw.describe_firewall_policy.return_value = {
            "FirewallPolicy": {"StatelessDefaultActions": ["aws:forward_to_sfe"],
                               "StatelessFragmentDefaultActions": ["aws:forward_to_sfe"]},
            "UpdateToken": "token-abc",
        }
        cleaner._nfw.update_firewall_policy.return_value = {}

        error_response = {"Error": {"Code": "InternalError", "Message": "Oops"}}
        # Fail twice, succeed on third attempt
        cleaner._s3.delete_object.side_effect = [
            ClientError(error_response, "DeleteObject"),
            ClientError(error_response, "DeleteObject"),
            None,  # Success
        ]

        scope = RunScope(
            run_id="int-abcdef01-1700000000",
            config_keys=["int-abcdef01-1700000000/retry.yaml"],
            rule_group_names=[],
        )

        result = cleaner.revert(scope)
        assert result.mutations_reverted is True
        assert cleaner._s3.delete_object.call_count == 3
        assert mock_sleep.call_count == 2  # backoff between retries

    @patch("tests.integration.env.mutation_cleaner.time.sleep")
    def test_records_failure_after_max_retries(
        self, mock_sleep: MagicMock, cleaner: MutationCleaner
    ) -> None:
        """Should record failure after 3 failed attempts. Req 10.9."""
        cleaner._baseline_rule_group_references = []
        cleaner._nfw.describe_firewall_policy.return_value = {
            "FirewallPolicy": {"StatelessDefaultActions": ["aws:forward_to_sfe"],
                               "StatelessFragmentDefaultActions": ["aws:forward_to_sfe"]},
            "UpdateToken": "token-abc",
        }
        cleaner._nfw.update_firewall_policy.return_value = {}

        error_response = {"Error": {"Code": "AccessDenied", "Message": "Denied"}}
        cleaner._s3.delete_object.side_effect = ClientError(error_response, "DeleteObject")

        scope = RunScope(
            run_id="int-abcdef01-1700000000",
            config_keys=["int-abcdef01-1700000000/stuck.yaml"],
            rule_group_names=[],
        )

        result = cleaner.revert(scope)
        assert result.mutations_reverted is False
        assert len(result.failed_artifacts) == 1
        assert "stuck.yaml" in result.failed_artifacts[0]
        assert cleaner._s3.delete_object.call_count == _MAX_RETRIES


# ---------------------------------------------------------------------------
# Rule group deletion tests
# ---------------------------------------------------------------------------


class TestRuleGroupDeletion:
    """Tests for Network Firewall rule group deletion within revert."""

    def test_deletes_all_rule_groups(
        self, cleaner: MutationCleaner, scope: RunScope
    ) -> None:
        """Should call delete_rule_group for each tracked name. Req 10.1."""
        cleaner._baseline_rule_group_references = []
        cleaner._nfw.describe_firewall_policy.return_value = {
            "FirewallPolicy": {"StatelessDefaultActions": ["aws:forward_to_sfe"],
                               "StatelessFragmentDefaultActions": ["aws:forward_to_sfe"]},
            "UpdateToken": "token-abc",
        }
        cleaner._nfw.update_firewall_policy.return_value = {}
        cleaner._nfw.delete_rule_group.return_value = {}

        result = cleaner.revert(scope)

        assert cleaner._nfw.delete_rule_group.call_count == 2
        calls = cleaner._nfw.delete_rule_group.call_args_list
        assert calls[0] == call(
            RuleGroupName="anfw-rules-int-abcdef01-1700000000",
            Type="STATEFUL",
        )
        assert calls[1] == call(
            RuleGroupName="anfw-custom-int-abcdef01-1700000000",
            Type="STATEFUL",
        )

    def test_tolerates_resource_not_found(
        self, cleaner: MutationCleaner
    ) -> None:
        """Should tolerate ResourceNotFoundException (already deleted). Req 10.5."""
        cleaner._baseline_rule_group_references = []
        cleaner._nfw.describe_firewall_policy.return_value = {
            "FirewallPolicy": {"StatelessDefaultActions": ["aws:forward_to_sfe"],
                               "StatelessFragmentDefaultActions": ["aws:forward_to_sfe"]},
            "UpdateToken": "token-abc",
        }
        cleaner._nfw.update_firewall_policy.return_value = {}

        error_response = {
            "Error": {"Code": "ResourceNotFoundException", "Message": "Not found"}
        }
        cleaner._nfw.delete_rule_group.side_effect = ClientError(
            error_response, "DeleteRuleGroup"
        )

        scope = RunScope(
            run_id="int-abcdef01-1700000000",
            config_keys=[],
            rule_group_names=["gone-group-int-abcdef01-1700000000"],
        )

        result = cleaner.revert(scope)
        assert result.mutations_reverted is True
        assert "gone-group" not in str(result.failed_artifacts)

    @patch("tests.integration.env.mutation_cleaner.time.sleep")
    def test_retries_rule_group_deletion(
        self, mock_sleep: MagicMock, cleaner: MutationCleaner
    ) -> None:
        """Should retry rule group deletion up to 3 times. Req 10.9."""
        cleaner._baseline_rule_group_references = []
        cleaner._nfw.describe_firewall_policy.return_value = {
            "FirewallPolicy": {"StatelessDefaultActions": ["aws:forward_to_sfe"],
                               "StatelessFragmentDefaultActions": ["aws:forward_to_sfe"]},
            "UpdateToken": "token-abc",
        }
        cleaner._nfw.update_firewall_policy.return_value = {}

        error_response = {"Error": {"Code": "ThrottlingException", "Message": "Slow down"}}
        cleaner._nfw.delete_rule_group.side_effect = [
            ClientError(error_response, "DeleteRuleGroup"),
            None,  # Success on second attempt
        ]

        scope = RunScope(
            run_id="int-abcdef01-1700000000",
            config_keys=[],
            rule_group_names=["throttled-group-int-abcdef01-1700000000"],
        )

        result = cleaner.revert(scope)
        assert result.mutations_reverted is True
        assert cleaner._nfw.delete_rule_group.call_count == 2

    @patch("tests.integration.env.mutation_cleaner.time.sleep")
    def test_records_rule_group_failure(
        self, mock_sleep: MagicMock, cleaner: MutationCleaner
    ) -> None:
        """Should record failure for rule group after 3 attempts. Req 10.9."""
        cleaner._baseline_rule_group_references = []
        cleaner._nfw.describe_firewall_policy.return_value = {
            "FirewallPolicy": {"StatelessDefaultActions": ["aws:forward_to_sfe"],
                               "StatelessFragmentDefaultActions": ["aws:forward_to_sfe"]},
            "UpdateToken": "token-abc",
        }
        cleaner._nfw.update_firewall_policy.return_value = {}

        error_response = {"Error": {"Code": "InternalError", "Message": "Oops"}}
        cleaner._nfw.delete_rule_group.side_effect = ClientError(
            error_response, "DeleteRuleGroup"
        )

        scope = RunScope(
            run_id="int-abcdef01-1700000000",
            config_keys=[],
            rule_group_names=["broken-rg-int-abcdef01-1700000000"],
        )

        result = cleaner.revert(scope)
        assert result.mutations_reverted is False
        assert len(result.failed_artifacts) == 1
        assert "broken-rg" in result.failed_artifacts[0]
        assert cleaner._nfw.delete_rule_group.call_count == _MAX_RETRIES


# ---------------------------------------------------------------------------
# Baseline restore tests
# ---------------------------------------------------------------------------


class TestBaselineRestore:
    """Tests for firewall policy baseline restoration. Req 10.3."""

    def test_restores_policy_to_baseline(
        self, cleaner: MutationCleaner
    ) -> None:
        """Should call update_firewall_policy with baseline references. Req 10.3."""
        baseline_refs = [
            {"ResourceArn": "arn:aws:network-firewall:eu-west-1:123:stateful-rulegroup/stable-rg-1"},
        ]
        cleaner._baseline_rule_group_references = baseline_refs
        cleaner._nfw.describe_firewall_policy.return_value = {
            "FirewallPolicy": {
                "StatefulRuleGroupReferences": [
                    {"ResourceArn": "arn:aws:network-firewall:eu-west-1:123:stateful-rulegroup/stable-rg-1"},
                    {"ResourceArn": "arn:aws:network-firewall:eu-west-1:123:stateful-rulegroup/run-id-rg"},
                ],
                "StatelessDefaultActions": ["aws:forward_to_sfe"],
                "StatelessFragmentDefaultActions": ["aws:forward_to_sfe"],
            },
            "UpdateToken": "token-xyz",
        }
        cleaner._nfw.update_firewall_policy.return_value = {}

        scope = RunScope(
            run_id="int-abcdef01-1700000000",
            config_keys=[],
            rule_group_names=[],
        )

        result = cleaner.revert(scope)

        assert result.baseline_restored is True
        update_call = cleaner._nfw.update_firewall_policy.call_args
        # The policy passed should have the baseline references
        policy_arg = update_call[1]["FirewallPolicy"]
        assert policy_arg["StatefulRuleGroupReferences"] == baseline_refs
        assert update_call[1]["UpdateToken"] == "token-xyz"

    def test_preserves_stateless_settings(
        self, cleaner: MutationCleaner
    ) -> None:
        """Should preserve stateless default actions when restoring baseline."""
        cleaner._baseline_rule_group_references = []
        cleaner._nfw.describe_firewall_policy.return_value = {
            "FirewallPolicy": {
                "StatefulRuleGroupReferences": [
                    {"ResourceArn": "arn:aws:some-run-id-rg"},
                ],
                "StatelessDefaultActions": ["aws:forward_to_sfe"],
                "StatelessFragmentDefaultActions": ["aws:drop"],
                "StatelessRuleGroupReferences": [{"ResourceArn": "arn:stateless"}],
            },
            "UpdateToken": "token-preserve",
        }
        cleaner._nfw.update_firewall_policy.return_value = {}

        scope = RunScope(run_id="int-x-1", config_keys=[], rule_group_names=[])
        result = cleaner.revert(scope)

        assert result.baseline_restored is True
        policy_arg = cleaner._nfw.update_firewall_policy.call_args[1]["FirewallPolicy"]
        assert policy_arg["StatelessDefaultActions"] == ["aws:forward_to_sfe"]
        assert policy_arg["StatelessFragmentDefaultActions"] == ["aws:drop"]
        assert policy_arg["StatelessRuleGroupReferences"] == [{"ResourceArn": "arn:stateless"}]

    def test_returns_false_when_no_baseline_captured(
        self, cleaner: MutationCleaner
    ) -> None:
        """Should return baseline_restored=False if capture_baseline was never called."""
        scope = RunScope(run_id="int-x-1", config_keys=[], rule_group_names=[])
        result = cleaner.revert(scope)

        assert result.baseline_restored is False
        cleaner._nfw.update_firewall_policy.assert_not_called()

    @patch("tests.integration.env.mutation_cleaner.time.sleep")
    def test_retries_policy_restore_on_failure(
        self, mock_sleep: MagicMock, cleaner: MutationCleaner
    ) -> None:
        """Should retry policy restore up to 3 times. Req 10.9."""
        cleaner._baseline_rule_group_references = []

        error_response = {"Error": {"Code": "InvalidTokenException", "Message": "stale token"}}
        # describe succeeds, but update fails on first two, then succeeds
        cleaner._nfw.describe_firewall_policy.return_value = {
            "FirewallPolicy": {
                "StatelessDefaultActions": ["aws:forward_to_sfe"],
                "StatelessFragmentDefaultActions": ["aws:forward_to_sfe"],
            },
            "UpdateToken": "token-stale",
        }
        cleaner._nfw.update_firewall_policy.side_effect = [
            ClientError(error_response, "UpdateFirewallPolicy"),
            ClientError(error_response, "UpdateFirewallPolicy"),
            {},  # Success on third attempt
        ]

        scope = RunScope(run_id="int-x-1", config_keys=[], rule_group_names=[])
        result = cleaner.revert(scope)

        assert result.baseline_restored is True
        assert cleaner._nfw.update_firewall_policy.call_count == 3

    @patch("tests.integration.env.mutation_cleaner.time.sleep")
    def test_records_restore_failure_after_max_retries(
        self, mock_sleep: MagicMock, cleaner: MutationCleaner
    ) -> None:
        """Should return baseline_restored=False after 3 failed attempts."""
        cleaner._baseline_rule_group_references = []

        error_response = {"Error": {"Code": "InternalError", "Message": "server error"}}
        cleaner._nfw.describe_firewall_policy.return_value = {
            "FirewallPolicy": {
                "StatelessDefaultActions": ["aws:forward_to_sfe"],
                "StatelessFragmentDefaultActions": ["aws:forward_to_sfe"],
            },
            "UpdateToken": "token-x",
        }
        cleaner._nfw.update_firewall_policy.side_effect = ClientError(
            error_response, "UpdateFirewallPolicy"
        )

        scope = RunScope(run_id="int-x-1", config_keys=[], rule_group_names=[])
        result = cleaner.revert(scope)

        assert result.baseline_restored is False
        assert cleaner._nfw.update_firewall_policy.call_count == _MAX_RETRIES


# ---------------------------------------------------------------------------
# Integration / end-to-end revert tests
# ---------------------------------------------------------------------------


class TestRevertEndToEnd:
    """End-to-end tests for the full revert flow."""

    def test_full_revert_success(
        self, cleaner: MutationCleaner, scope: RunScope
    ) -> None:
        """All artifacts deleted + baseline restored = full success. Req 10.1, 10.3."""
        cleaner._baseline_rule_group_references = [
            {"ResourceArn": "arn:aws:network-firewall:eu-west-1:123:stateful-rulegroup/stable"},
        ]
        cleaner._nfw.describe_firewall_policy.return_value = {
            "FirewallPolicy": {
                "StatefulRuleGroupReferences": [
                    {"ResourceArn": "arn:aws:network-firewall:eu-west-1:123:stateful-rulegroup/stable"},
                    {"ResourceArn": "arn:aws:network-firewall:eu-west-1:123:stateful-rulegroup/run-rg"},
                ],
                "StatelessDefaultActions": ["aws:forward_to_sfe"],
                "StatelessFragmentDefaultActions": ["aws:forward_to_sfe"],
            },
            "UpdateToken": "token-full",
        }
        cleaner._nfw.update_firewall_policy.return_value = {}
        cleaner._nfw.delete_rule_group.return_value = {}

        result = cleaner.revert(scope)

        assert result.mutations_reverted is True
        assert result.baseline_restored is True
        assert result.failed_artifacts == []

    def test_revert_with_empty_scope(
        self, cleaner: MutationCleaner
    ) -> None:
        """Revert with no artifacts to delete should succeed cleanly."""
        cleaner._baseline_rule_group_references = []
        cleaner._nfw.describe_firewall_policy.return_value = {
            "FirewallPolicy": {
                "StatelessDefaultActions": ["aws:forward_to_sfe"],
                "StatelessFragmentDefaultActions": ["aws:forward_to_sfe"],
            },
            "UpdateToken": "token-empty",
        }
        cleaner._nfw.update_firewall_policy.return_value = {}

        scope = RunScope(run_id="int-abcdef01-1700000000")

        result = cleaner.revert(scope)

        assert result.mutations_reverted is True
        assert result.baseline_restored is True
        assert result.failed_artifacts == []
        cleaner._s3.delete_object.assert_not_called()
        cleaner._nfw.delete_rule_group.assert_not_called()

    @patch("tests.integration.env.mutation_cleaner.time.sleep")
    def test_partial_failure_records_all_failures(
        self, mock_sleep: MagicMock, cleaner: MutationCleaner
    ) -> None:
        """Should record all artifacts that fail after retries."""
        cleaner._baseline_rule_group_references = []
        cleaner._nfw.describe_firewall_policy.return_value = {
            "FirewallPolicy": {
                "StatelessDefaultActions": ["aws:forward_to_sfe"],
                "StatelessFragmentDefaultActions": ["aws:forward_to_sfe"],
            },
            "UpdateToken": "token-partial",
        }
        cleaner._nfw.update_firewall_policy.return_value = {}

        # S3 deletion fails permanently
        s3_error = {"Error": {"Code": "AccessDenied", "Message": "Denied"}}
        cleaner._s3.delete_object.side_effect = ClientError(s3_error, "DeleteObject")

        # Rule group deletion also fails permanently
        nfw_error = {"Error": {"Code": "InternalError", "Message": "Error"}}
        cleaner._nfw.delete_rule_group.side_effect = ClientError(nfw_error, "DeleteRuleGroup")

        scope = RunScope(
            run_id="int-abcdef01-1700000000",
            config_keys=["int-abcdef01-1700000000/fail1.yaml"],
            rule_group_names=["fail-rg-int-abcdef01-1700000000"],
        )

        result = cleaner.revert(scope)

        assert result.mutations_reverted is False
        assert len(result.failed_artifacts) == 2
        assert any("fail1.yaml" in f for f in result.failed_artifacts)
        assert any("fail-rg" in f for f in result.failed_artifacts)

    def test_never_touches_stable_resources(
        self, cleaner: MutationCleaner, int_env: IntEnv
    ) -> None:
        """Revert never deletes the policy itself or stable stacks. Req 10.4."""
        cleaner._baseline_rule_group_references = []
        cleaner._nfw.describe_firewall_policy.return_value = {
            "FirewallPolicy": {
                "StatelessDefaultActions": ["aws:forward_to_sfe"],
                "StatelessFragmentDefaultActions": ["aws:forward_to_sfe"],
            },
            "UpdateToken": "token-safe",
        }
        cleaner._nfw.update_firewall_policy.return_value = {}

        scope = RunScope(
            run_id="int-abcdef01-1700000000",
            config_keys=["int-abcdef01-1700000000/some.yaml"],
            rule_group_names=["run-rg-int-abcdef01-1700000000"],
        )
        cleaner._nfw.delete_rule_group.return_value = {}

        cleaner.revert(scope)

        # Verify: never called delete_firewall_policy, delete_firewall, or
        # any operation that would destroy stable resources
        assert not hasattr(cleaner._nfw, "delete_firewall_policy") or \
            not cleaner._nfw.delete_firewall_policy.called
        assert not hasattr(cleaner._nfw, "delete_firewall") or \
            not cleaner._nfw.delete_firewall.called

        # The only S3 delete was for the run-scoped key, not the bucket
        for c in cleaner._s3.delete_object.call_args_list:
            key = c[1]["Key"]
            assert int_env.run_id in key

        # The only rule group deletes were for run-scoped names
        for c in cleaner._nfw.delete_rule_group.call_args_list:
            name = c[1]["RuleGroupName"]
            assert int_env.run_id in name
