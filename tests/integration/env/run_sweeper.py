"""Run_Sweeper — backstop for orphaned run-id-scoped ephemeral artifacts.

Finds and deletes run-id-scoped S3 config objects and Network Firewall rule
groups that are older than 24 hours (based on the epoch embedded in the
run_id). This is the backstop for crashed runs whose MutationCleaner never
executed.

SAFETY: Never touches stable/baseline resources (IntBaseStack, app stacks,
firewall policy itself). Only deletes ephemeral artifacts matching the
``int-<shortsha>-<epoch>`` naming pattern whose epoch is older than 24h.

Requirements: 10.7
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field

import boto3
from botocore.exceptions import ClientError

from tests.integration.env.stable import IntEnv

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TWENTY_FOUR_HOURS_SECONDS = 86400
"""Number of seconds in 24 hours."""

_RUN_ID_PATTERN = re.compile(r"int-[0-9a-f]{8}-(\d+)(?:-\d+)?")
"""Regex matching run-id format: int-<8 hex chars>-<epoch>[-disambiguator].

Captures the epoch as group 1.
"""


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


@dataclass
class SweepResult:
    """Outcome of a RunSweeper.sweep() call.

    Attributes:
        deleted_keys: S3 object keys that were successfully deleted.
        deleted_rule_groups: NFW rule group names that were successfully deleted.
        errors: Descriptions of artifacts that could not be deleted.
    """

    deleted_keys: list[str] = field(default_factory=list)
    deleted_rule_groups: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# RunSweeper
# ---------------------------------------------------------------------------


class RunSweeper:
    """Backstop that removes orphaned run-id-scoped ephemeral artifacts.

    Identifies S3 config objects with keys starting with ``int-`` and Network
    Firewall rule groups with names containing ``int-`` that match the run-id
    format, then deletes those whose embedded epoch is more than 24 hours old.

    Usage::

        sweeper = RunSweeper(env=int_env, session=boto3_session)
        result = sweeper.sweep()

    The sweeper:
    1. Lists S3 objects with keys starting with 'int-'.
    2. Lists NFW rule groups with names containing 'int-'.
    3. Parses the epoch from the run_id embedded in names/keys.
    4. Deletes only those older than 24h.
    5. Never touches stable/baseline resources.
    6. Returns a SweepResult with what was cleaned and any errors.

    Validates: Requirement 10.7
    """

    def __init__(self, env: IntEnv, session: boto3.Session) -> None:
        self._env = env
        self._session = session
        self._s3 = session.client("s3")
        self._nfw = session.client("network-firewall")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def sweep(self) -> SweepResult:
        """Find and delete run-id-scoped ephemeral artifacts older than 24h.

        - List S3 objects with keys starting with 'int-'
        - List NFW rule groups with names containing 'int-'
        - Parse the epoch from the run_id embedded in names/keys
        - Delete only those older than 24h
        - Never touch stable/baseline resources
        - Return a SweepResult with what was cleaned

        Returns:
            SweepResult with deleted_keys, deleted_rule_groups, and errors.
        """
        result = SweepResult()
        cutoff = time.time() - _TWENTY_FOUR_HOURS_SECONDS

        # Sweep S3 config objects
        self._sweep_s3_objects(cutoff, result)

        # Sweep Network Firewall rule groups
        self._sweep_rule_groups(cutoff, result)

        if result.deleted_keys or result.deleted_rule_groups:
            logger.info(
                "Sweep complete: deleted %d S3 keys, %d rule groups",
                len(result.deleted_keys),
                len(result.deleted_rule_groups),
            )
        else:
            logger.info("Sweep complete: no aged artifacts found")

        if result.errors:
            logger.warning(
                "Sweep encountered %d errors: %s",
                len(result.errors),
                result.errors,
            )

        return result

    # ------------------------------------------------------------------
    # Internal: S3 sweep
    # ------------------------------------------------------------------

    def _sweep_s3_objects(self, cutoff: float, result: SweepResult) -> None:
        """List and delete S3 objects with run-id prefix older than cutoff."""
        try:
            paginator = self._s3.get_paginator("list_objects_v2")
            pages = paginator.paginate(
                Bucket=self._env.config_bucket,
                Prefix="int-",
            )

            for page in pages:
                for obj in page.get("Contents", []):
                    key = obj["Key"]
                    epoch = self._extract_epoch_from_key(key)
                    if epoch is not None and epoch < cutoff:
                        self._delete_s3_object(key, result)
        except ClientError as exc:
            error_msg = (
                f"Failed to list S3 objects in bucket "
                f"'{self._env.config_bucket}': {exc}"
            )
            logger.error(error_msg)
            result.errors.append(error_msg)

    def _extract_epoch_from_key(self, key: str) -> int | None:
        """Extract the epoch from a run-id-scoped S3 key.

        Keys have the form: ``int-<shortsha>-<epoch>/...`` or
        ``int-<shortsha>-<epoch>-<disambiguator>/...``

        Returns the epoch as int, or None if the key doesn't match.
        """
        # The run-id is the first path segment (before the /)
        first_segment = key.split("/")[0]
        match = _RUN_ID_PATTERN.fullmatch(first_segment)
        if match:
            return int(match.group(1))
        return None

    def _delete_s3_object(self, key: str, result: SweepResult) -> None:
        """Delete a single S3 object. Records success or error."""
        try:
            self._s3.delete_object(
                Bucket=self._env.config_bucket,
                Key=key,
            )
            result.deleted_keys.append(key)
            logger.debug("Swept S3 object: s3://%s/%s", self._env.config_bucket, key)
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            if error_code in ("NoSuchKey", "404"):
                # Already gone — not an error for sweeping purposes
                logger.debug("S3 object already absent (ignored): %s", key)
            else:
                error_msg = f"Failed to delete S3 key '{key}': {exc}"
                logger.warning(error_msg)
                result.errors.append(error_msg)

    # ------------------------------------------------------------------
    # Internal: NFW rule group sweep
    # ------------------------------------------------------------------

    def _sweep_rule_groups(self, cutoff: float, result: SweepResult) -> None:
        """List and delete NFW rule groups with run-id names older than cutoff."""
        try:
            rule_groups = self._list_rule_groups()
            for rg_name in rule_groups:
                epoch = self._extract_epoch_from_name(rg_name)
                if epoch is not None and epoch < cutoff:
                    self._delete_rule_group(rg_name, result)
        except ClientError as exc:
            error_msg = f"Failed to list NFW rule groups: {exc}"
            logger.error(error_msg)
            result.errors.append(error_msg)

    def _list_rule_groups(self) -> list[str]:
        """List all stateful rule group names that contain 'int-'.

        Uses pagination to handle accounts with many rule groups.
        """
        names: list[str] = []
        paginator = self._nfw.get_paginator("list_rule_groups")
        pages = paginator.paginate(Type="STATEFUL")

        for page in pages:
            for rg in page.get("RuleGroups", []):
                name = rg.get("Name", "")
                if "int-" in name:
                    names.append(name)

        return names

    def _extract_epoch_from_name(self, name: str) -> int | None:
        """Extract the epoch from a rule group name containing a run-id.

        Rule group names have the form:
        ``<prefix>-int-<shortsha>-<epoch>`` or
        ``<prefix>-int-<shortsha>-<epoch>-<disambiguator>``

        We search for the run-id pattern anywhere in the name.

        Returns the epoch as int, or None if no run-id pattern is found.
        """
        match = _RUN_ID_PATTERN.search(name)
        if match:
            return int(match.group(1))
        return None

    def _delete_rule_group(self, rule_group_name: str, result: SweepResult) -> None:
        """Delete a single NFW rule group. Records success or error."""
        try:
            self._nfw.delete_rule_group(
                RuleGroupName=rule_group_name,
                Type="STATEFUL",
            )
            result.deleted_rule_groups.append(rule_group_name)
            logger.debug("Swept rule group: %s", rule_group_name)
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            if error_code == "ResourceNotFoundException":
                # Already gone — not an error for sweeping purposes
                logger.debug("Rule group already absent (ignored): %s", rule_group_name)
            else:
                error_msg = (
                    f"Failed to delete rule group '{rule_group_name}': {exc}"
                )
                logger.warning(error_msg)
                result.errors.append(error_msg)
