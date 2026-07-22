"""Unit tests for RunScope + Run_Id scheme.

Covers:
- Run_Id format validation (int-<8hex>-<epoch>)
- Name length ≤128 chars
- Alphanumeric + hyphens only
- Abort if SHA unavailable
- Collision disambiguation
- S3 key embedding
- Rule group name embedding and truncation

Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8
"""

from __future__ import annotations

import re
import subprocess
from unittest.mock import patch

import pytest

from tests.integration.env.run_scope import (
    RunIdError,
    RunScope,
    _compute_run_id,
    _get_git_shortsha,
    _VALID_NAME_RE,
    _MAX_NAME_LENGTH,
    reset_collision_counter,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clean_collision_counter():
    """Reset the collision counter before each test."""
    reset_collision_counter()
    yield
    reset_collision_counter()


# ---------------------------------------------------------------------------
# _get_git_shortsha tests
# ---------------------------------------------------------------------------


class TestGetGitShortsha:
    """Tests for _get_git_shortsha helper."""

    def test_returns_8_hex_chars(self):
        """SHA should be exactly 8 lowercase hex characters."""
        sha = _get_git_shortsha()
        assert re.fullmatch(r"[0-9a-f]{8}", sha), f"Got: {sha}"

    def test_raises_on_git_not_found(self):
        """Should raise RunIdError when git is not on PATH."""
        with patch(
            "tests.integration.env.run_scope.subprocess.run",
            side_effect=FileNotFoundError("git not found"),
        ):
            with pytest.raises(RunIdError, match="git SHA unavailable"):
                _get_git_shortsha()

    def test_raises_on_git_timeout(self):
        """Should raise RunIdError when git times out."""
        with patch(
            "tests.integration.env.run_scope.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="git", timeout=10),
        ):
            with pytest.raises(RunIdError, match="git SHA unavailable"):
                _get_git_shortsha()

    def test_raises_on_nonzero_exit(self):
        """Should raise RunIdError when git rev-parse fails."""
        mock_result = subprocess.CompletedProcess(
            args=["git"], returncode=128, stdout="", stderr="fatal: not a repo"
        )
        with patch(
            "tests.integration.env.run_scope.subprocess.run",
            return_value=mock_result,
        ):
            with pytest.raises(RunIdError, match="git rev-parse failed"):
                _get_git_shortsha()


# ---------------------------------------------------------------------------
# _compute_run_id tests
# ---------------------------------------------------------------------------


class TestComputeRunId:
    """Tests for _compute_run_id."""

    def test_basic_format(self):
        """Run_Id should be int-<8hex>-<epoch>."""
        run_id = _compute_run_id("abcd1234", 1700000000)
        assert run_id == "int-abcd1234-1700000000"

    def test_matches_valid_name_regex(self):
        """Run_Id should match the alphanumeric + hyphens pattern."""
        run_id = _compute_run_id("deadbeef", 1700000000)
        assert _VALID_NAME_RE.fullmatch(run_id)

    def test_within_128_chars(self):
        """Run_Id should be ≤128 chars."""
        run_id = _compute_run_id("abcdef01", 9999999999)
        assert len(run_id) <= _MAX_NAME_LENGTH

    def test_collision_disambiguator(self):
        """Same (sha, epoch) pair appends -1, -2, etc."""
        first = _compute_run_id("abcdef01", 1700000000)
        second = _compute_run_id("abcdef01", 1700000000)
        third = _compute_run_id("abcdef01", 1700000000)

        assert first == "int-abcdef01-1700000000"
        assert second == "int-abcdef01-1700000000-1"
        assert third == "int-abcdef01-1700000000-2"

    def test_different_sha_no_collision(self):
        """Different SHAs at the same epoch should not collide."""
        id1 = _compute_run_id("aaaaaaaa", 1700000000)
        id2 = _compute_run_id("bbbbbbbb", 1700000000)

        assert id1 == "int-aaaaaaaa-1700000000"
        assert id2 == "int-bbbbbbbb-1700000000"

    def test_different_epoch_no_collision(self):
        """Same SHA at different epochs should not collide."""
        id1 = _compute_run_id("abcdef01", 1700000000)
        id2 = _compute_run_id("abcdef01", 1700000001)

        assert id1 == "int-abcdef01-1700000000"
        assert id2 == "int-abcdef01-1700000001"


# ---------------------------------------------------------------------------
# RunScope.create tests
# ---------------------------------------------------------------------------


class TestRunScopeCreate:
    """Tests for RunScope.create class method."""

    def test_creates_valid_run_id(self):
        """create() should produce a valid run_id."""
        scope = RunScope.create()
        assert scope.run_id.startswith("int-")
        assert _VALID_NAME_RE.fullmatch(scope.run_id)
        assert len(scope.run_id) <= _MAX_NAME_LENGTH

    def test_run_id_format_matches_spec(self):
        """Run_Id should match int-<8hex>-<digits>."""
        scope = RunScope.create()
        assert re.fullmatch(r"int-[0-9a-f]{8}-\d+", scope.run_id)

    def test_empty_tracking_lists(self):
        """New scope should have empty tracking lists."""
        scope = RunScope.create()
        assert scope.config_keys == []
        assert scope.rule_group_names == []

    def test_raises_when_sha_unavailable(self):
        """Should raise RunIdError if git SHA can't be obtained."""
        with patch(
            "tests.integration.env.run_scope.subprocess.run",
            side_effect=FileNotFoundError("no git"),
        ):
            with pytest.raises(RunIdError):
                RunScope.create()

    def test_collision_handling_same_epoch(self):
        """Two creates in the same epoch second get disambiguated."""
        with patch("tests.integration.env.run_scope.time.time", return_value=1700000000.5):
            with patch(
                "tests.integration.env.run_scope._get_git_shortsha",
                return_value="abcdef01",
            ):
                scope1 = RunScope.create()
                scope2 = RunScope.create()

        assert scope1.run_id == "int-abcdef01-1700000000"
        assert scope2.run_id == "int-abcdef01-1700000000-1"


# ---------------------------------------------------------------------------
# RunScope.s3_key tests
# ---------------------------------------------------------------------------


class TestRunScopeS3Key:
    """Tests for the s3_key method."""

    def test_embeds_run_id(self):
        """S3 key should contain the run_id."""
        scope = RunScope(run_id="int-abcdef01-1700000000")
        key = scope.s3_key("eu-west-1")
        assert key == "int-abcdef01-1700000000/eu-west-1-config.yaml"

    def test_tracks_key(self):
        """Generated key should be tracked in config_keys."""
        scope = RunScope(run_id="int-abcdef01-1700000000")
        key = scope.s3_key("us-east-1")
        assert key in scope.config_keys

    def test_multiple_regions(self):
        """Multiple regions produce distinct tracked keys."""
        scope = RunScope(run_id="int-abcdef01-1700000000")
        key1 = scope.s3_key("eu-west-1")
        key2 = scope.s3_key("eu-central-1")

        assert key1 != key2
        assert len(scope.config_keys) == 2


# ---------------------------------------------------------------------------
# RunScope.rule_group_name tests
# ---------------------------------------------------------------------------


class TestRunScopeRuleGroupName:
    """Tests for the rule_group_name method."""

    def test_embeds_run_id(self):
        """Rule group name should contain the run_id."""
        scope = RunScope(run_id="int-abcdef01-1700000000")
        name = scope.rule_group_name("my-group")
        assert "int-abcdef01-1700000000" in name

    def test_within_128_chars(self):
        """Rule group name must be ≤128 chars."""
        scope = RunScope(run_id="int-abcdef01-1700000000")
        name = scope.rule_group_name("a" * 200)
        assert len(name) <= _MAX_NAME_LENGTH

    def test_alphanumeric_hyphens_only(self):
        """Rule group name must match [a-z0-9-]+."""
        scope = RunScope(run_id="int-abcdef01-1700000000")
        name = scope.rule_group_name("my-prefix")
        assert _VALID_NAME_RE.fullmatch(name)

    def test_truncates_long_prefix(self):
        """Long prefix is truncated to respect 128-char limit."""
        scope = RunScope(run_id="int-abcdef01-1700000000")
        long_prefix = "a" * 200
        name = scope.rule_group_name(long_prefix)

        assert len(name) <= _MAX_NAME_LENGTH
        assert name.endswith("int-abcdef01-1700000000")

    def test_tracks_name(self):
        """Generated name should be tracked in rule_group_names."""
        scope = RunScope(run_id="int-abcdef01-1700000000")
        name = scope.rule_group_name("test-prefix")
        assert name in scope.rule_group_names

    def test_sanitizes_invalid_chars(self):
        """Invalid characters in prefix are sanitized to hyphens."""
        scope = RunScope(run_id="int-abcdef01-1700000000")
        name = scope.rule_group_name("MY_PREFIX")
        # Should be lowercased and underscores replaced
        assert _VALID_NAME_RE.fullmatch(name)

    def test_format_is_prefix_dash_runid(self):
        """Format should be {prefix}-{run_id}."""
        scope = RunScope(run_id="int-abcdef01-1700000000")
        name = scope.rule_group_name("anfw-rules")
        assert name == "anfw-rules-int-abcdef01-1700000000"
