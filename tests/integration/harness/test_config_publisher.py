"""Unit tests for ConfigPublisher — mocks S3 to verify upload/delete logic.

Requirements: 8.1, 8.6
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from tests.integration.env.run_scope import RunScope
from tests.integration.env.stable import IntEnv
from tests.integration.harness.config_publisher import (
    ConfigPublisher,
    ConfigPublishError,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def int_env() -> IntEnv:
    """A minimal IntEnv for testing."""
    return IntEnv(
        run_id="int-abcd1234-1700000000",
        account_id="123456789012",
        region="eu-west-1",
        config_bucket="test-config-bucket",
        vpc_id="vpc-abc123",
        firewall_policy_arn="arn:aws:network-firewall:eu-west-1:123456789012:firewall-policy/test",
        xaccount_role_arn="arn:aws:iam::123456789012:role/xacct",
        event_bus_arn="arn:aws:events:eu-west-1:123456789012:event-bus/test",
    )


@pytest.fixture()
def run_scope() -> RunScope:
    """A fresh RunScope for testing."""
    return RunScope(run_id="int-abcd1234-1700000000")


@pytest.fixture()
def mock_session() -> MagicMock:
    """A mocked boto3 Session returning a mocked S3 client."""
    session = MagicMock()
    session.client.return_value = MagicMock()
    return session


@pytest.fixture()
def publisher(int_env: IntEnv, mock_session: MagicMock, run_scope: RunScope) -> ConfigPublisher:
    """A ConfigPublisher wired to mocked S3."""
    return ConfigPublisher(env=int_env, session=mock_session, scope=run_scope)


def _s3_client(publisher: ConfigPublisher) -> MagicMock:
    """Extract the mocked S3 client from a publisher."""
    return publisher._s3


# ---------------------------------------------------------------------------
# put_config tests
# ---------------------------------------------------------------------------


class TestPutConfig:
    """Tests for ConfigPublisher.put_config."""

    def test_uploads_to_correct_bucket_and_key(
        self, publisher: ConfigPublisher, int_env: IntEnv, run_scope: RunScope
    ) -> None:
        """put_config uploads content to s3://{bucket}/{run_id}/{region}-config.yaml."""
        key = publisher.put_config("eu-west-1", "rules:\n  - example.com")

        s3 = _s3_client(publisher)
        s3.put_object.assert_called_once_with(
            Bucket=int_env.config_bucket,
            Key=key,
            Body=b"rules:\n  - example.com",
        )
        assert key == f"{run_scope.run_id}/eu-west-1-config.yaml"

    def test_returns_s3_key(
        self, publisher: ConfigPublisher, run_scope: RunScope
    ) -> None:
        """put_config returns the S3 key used."""
        key = publisher.put_config("us-east-1", "content")
        assert key == f"{run_scope.run_id}/us-east-1-config.yaml"

    def test_tracks_key_in_scope(
        self, publisher: ConfigPublisher, run_scope: RunScope
    ) -> None:
        """put_config records the key in scope.config_keys for cleanup."""
        key = publisher.put_config("eu-central-1", "body")
        assert key in run_scope.config_keys

    def test_raises_config_publish_error_on_s3_failure(
        self, publisher: ConfigPublisher
    ) -> None:
        """put_config raises ConfigPublishError when S3 PutObject fails."""
        s3 = _s3_client(publisher)
        s3.put_object.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Forbidden"}},
            "PutObject",
        )

        with pytest.raises(ConfigPublishError, match="Failed to upload config"):
            publisher.put_config("eu-west-1", "content")

    def test_error_includes_bucket_and_key(
        self, publisher: ConfigPublisher, int_env: IntEnv
    ) -> None:
        """ConfigPublishError message includes the bucket and key."""
        s3 = _s3_client(publisher)
        s3.put_object.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "oops"}},
            "PutObject",
        )

        with pytest.raises(ConfigPublishError) as exc_info:
            publisher.put_config("eu-west-1", "content")

        assert int_env.config_bucket in str(exc_info.value)

    def test_multiple_puts_track_all_keys(
        self, publisher: ConfigPublisher, run_scope: RunScope
    ) -> None:
        """Multiple put_config calls track all keys in scope."""
        publisher.put_config("eu-west-1", "a")
        publisher.put_config("us-east-1", "b")

        assert len(run_scope.config_keys) == 2
        assert f"{run_scope.run_id}/eu-west-1-config.yaml" in run_scope.config_keys
        assert f"{run_scope.run_id}/us-east-1-config.yaml" in run_scope.config_keys


# ---------------------------------------------------------------------------
# delete_config tests
# ---------------------------------------------------------------------------


class TestDeleteConfig:
    """Tests for ConfigPublisher.delete_config."""

    def test_deletes_from_correct_bucket_and_key(
        self, publisher: ConfigPublisher, int_env: IntEnv, run_scope: RunScope
    ) -> None:
        """delete_config calls S3 DeleteObject with the right bucket/key."""
        key = f"{run_scope.run_id}/eu-west-1-config.yaml"
        publisher.delete_config("eu-west-1", key)

        s3 = _s3_client(publisher)
        s3.delete_object.assert_called_once_with(
            Bucket=int_env.config_bucket,
            Key=key,
        )

    def test_raises_config_publish_error_on_s3_failure(
        self, publisher: ConfigPublisher, run_scope: RunScope
    ) -> None:
        """delete_config raises ConfigPublishError when S3 DeleteObject fails."""
        s3 = _s3_client(publisher)
        s3.delete_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Not found"}},
            "DeleteObject",
        )

        key = f"{run_scope.run_id}/eu-west-1-config.yaml"
        with pytest.raises(ConfigPublishError, match="Failed to delete config"):
            publisher.delete_config("eu-west-1", key)

    def test_error_includes_bucket_and_key(
        self, publisher: ConfigPublisher, int_env: IntEnv, run_scope: RunScope
    ) -> None:
        """ConfigPublishError for delete includes bucket and key."""
        s3 = _s3_client(publisher)
        s3.delete_object.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "oops"}},
            "DeleteObject",
        )

        key = f"{run_scope.run_id}/eu-west-1-config.yaml"
        with pytest.raises(ConfigPublishError) as exc_info:
            publisher.delete_config("eu-west-1", key)

        assert int_env.config_bucket in str(exc_info.value)
        assert key in str(exc_info.value)
