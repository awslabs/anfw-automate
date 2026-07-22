"""ConfigPublisher — upload/delete region config objects to the S3 config bucket.

Drives the real event path by publishing ``<region>-config.yaml`` objects
to the S3 config bucket, which triggers EventBridge → RuleCollect → SQS →
RuleExecute → Network Firewall.

On any upload/delete failure the test is aborted immediately (no polling)
by raising ConfigPublishError.

Requirements: 8.1, 8.6
"""

from __future__ import annotations

import logging

import boto3
from botocore.exceptions import ClientError

from tests.integration.env.run_scope import RunScope
from tests.integration.env.stable import IntEnv

logger = logging.getLogger(__name__)


class ConfigPublishError(Exception):
    """Raised when a config upload or delete fails.

    Signals that the test should abort immediately without polling any
    post-condition predicate. The error message includes the S3 key and
    the underlying failure reason.
    """


class ConfigPublisher:
    """Publishes and deletes region config objects in the S3 config bucket.

    Each operation embeds the run_id in the S3 key via ``RunScope.s3_key()``
    so that the MutationCleaner can revert all artifacts created during the
    run without affecting stable/baseline resources.

    Parameters
    ----------
    env : IntEnv
        Resolved integration environment containing the config bucket name.
    session : boto3.Session
        An authenticated boto3 session for the INT account.
    scope : RunScope
        The current run scope; keys are tracked in ``scope.config_keys``.
    """

    def __init__(self, env: IntEnv, session: boto3.Session, scope: RunScope) -> None:
        self._env = env
        self._scope = scope
        self._s3 = session.client("s3")

    def put_config(self, region: str, config_content: str) -> str:
        """Upload a region-config.yaml to the S3 config bucket.

        The S3 key is computed via ``scope.s3_key(region)`` which embeds the
        run_id for isolation and records the key in ``scope.config_keys``
        for cleanup.

        Parameters
        ----------
        region : str
            The AWS region name (e.g. ``eu-west-1``). Used to form the
            object key ``{run_id}/{region}-config.yaml``.
        config_content : str
            The YAML config body to upload.

        Returns
        -------
        str
            The S3 key used for the upload.

        Raises
        ------
        ConfigPublishError
            If the S3 PutObject call fails for any reason. The test should
            abort immediately without polling any post-condition.
        """
        key = self._scope.s3_key(region)
        bucket = self._env.config_bucket

        logger.info(
            "ConfigPublisher.put_config: uploading s3://%s/%s (%d bytes)",
            bucket,
            key,
            len(config_content),
        )

        try:
            self._s3.put_object(
                Bucket=bucket,
                Key=key,
                Body=config_content.encode("utf-8"),
            )
        except ClientError as exc:
            raise ConfigPublishError(
                f"Failed to upload config to s3://{bucket}/{key}: {exc}"
            ) from exc

        logger.info("ConfigPublisher.put_config: upload succeeded for key=%s", key)
        return key

    def delete_config(self, region: str, key: str) -> None:
        """Delete a config object from the S3 config bucket.

        Parameters
        ----------
        region : str
            The AWS region (informational for logging).
        key : str
            The S3 key to delete (previously returned by ``put_config``).

        Raises
        ------
        ConfigPublishError
            If the S3 DeleteObject call fails for any reason. The test
            should abort immediately.
        """
        bucket = self._env.config_bucket

        logger.info(
            "ConfigPublisher.delete_config: deleting s3://%s/%s",
            bucket,
            key,
        )

        try:
            self._s3.delete_object(
                Bucket=bucket,
                Key=key,
            )
        except ClientError as exc:
            raise ConfigPublishError(
                f"Failed to delete config s3://{bucket}/{key}: {exc}"
            ) from exc

        logger.info("ConfigPublisher.delete_config: delete succeeded for key=%s", key)
