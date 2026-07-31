"""ConfigPublisher — upload/delete region config objects to the tenant S3 bucket.

Drives the real event path by publishing ``<region>-config.yaml`` objects
to the tenant's S3 config bucket at the bucket root (matching prod behavior).
EventBridge picks up the S3 event and forwards to the central bus, triggering
the automation pipeline.

On any upload/delete failure the test is aborted immediately by raising
ConfigPublishError.
"""

from __future__ import annotations

import logging

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class ConfigPublishError(Exception):
    """Raised when a config upload or delete fails."""


class ConfigPublisher:
    """Publishes and deletes region config objects in the tenant's S3 bucket.

    Keys are root-level ``<region>-config.yaml`` — exactly what a real tenant
    uploads and what RuleCollect's ``validate_file_name`` expects.

    Parameters
    ----------
    session : boto3.Session
        An authenticated boto3 session.
    bucket_name : str
        The tenant's config bucket name.
    """

    def __init__(self, session: boto3.Session, bucket_name: str) -> None:
        self._bucket = bucket_name
        self._s3 = session.client("s3")
        self._uploaded_keys: list[str] = []

    def put_config(self, region: str, config_content: str) -> str:
        """Upload a region-config.yaml to the tenant's S3 bucket.

        Key: ``<region>-config.yaml`` at bucket root.

        Parameters
        ----------
        region : str
            AWS region name (e.g. ``eu-west-1``).
        config_content : str
            YAML config body.

        Returns
        -------
        str
            The S3 key used.

        Raises
        ------
        ConfigPublishError
            If S3 PutObject fails.
        """
        key = f"{region}-config.yaml"
        logger.info("ConfigPublisher.put_config: uploading s3://%s/%s", self._bucket, key)

        try:
            self._s3.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=config_content.encode("utf-8"),
            )
        except ClientError as exc:
            raise ConfigPublishError(
                f"Failed to upload config to s3://{self._bucket}/{key}: {exc}"
            ) from exc

        self._uploaded_keys.append(key)
        logger.info("ConfigPublisher.put_config: upload succeeded for key=%s", key)
        return key

    def delete_config(self, region: str) -> None:
        """Delete a config object from the tenant's S3 bucket.

        Parameters
        ----------
        region : str
            The region whose config to delete.

        Raises
        ------
        ConfigPublishError
            If S3 DeleteObject fails.
        """
        key = f"{region}-config.yaml"
        logger.info("ConfigPublisher.delete_config: deleting s3://%s/%s", self._bucket, key)

        try:
            self._s3.delete_object(Bucket=self._bucket, Key=key)
        except ClientError as exc:
            raise ConfigPublishError(
                f"Failed to delete config s3://{self._bucket}/{key}: {exc}"
            ) from exc

        if key in self._uploaded_keys:
            self._uploaded_keys.remove(key)
        logger.info("ConfigPublisher.delete_config: delete succeeded for key=%s", key)

    def cleanup_all(self) -> None:
        """Delete all configs uploaded during this test's lifetime.

        Called in the fixture teardown to ensure no orphaned configs remain.
        Tolerates already-deleted keys.
        """
        for key in list(self._uploaded_keys):
            try:
                self._s3.delete_object(Bucket=self._bucket, Key=key)
                logger.debug("Cleanup: deleted s3://%s/%s", self._bucket, key)
            except ClientError:
                logger.debug("Cleanup: key already gone s3://%s/%s", self._bucket, key)
        self._uploaded_keys.clear()
