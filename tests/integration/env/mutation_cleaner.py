"""MutationCleaner — reverts a run's ephemeral mutations.

Deletes run-id-scoped S3 config objects and Network Firewall rule groups,
then restores the stable firewall policy to the baseline rule-group-references
captured at run start. Never touches stable/baseline resources.

Requirements: 10.1, 10.3, 10.4, 10.5, 10.8, 10.9
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

import boto3
from botocore.exceptions import ClientError

from tests.integration.env.run_scope import RunScope
from tests.integration.env.stable import IntEnv

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_RETRIES = 3
"""Maximum number of deletion attempts per artifact before recording failure."""

_RETRY_BACKOFF_BASE = 0.5
"""Base wait in seconds between retries (doubles each attempt)."""


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


@dataclass
class RevertResult:
    """Outcome of a MutationCleaner.revert() call.

    Attributes:
        mutations_reverted: True when all run-id artifacts were deleted
            successfully (no failures remained after retries).
        baseline_restored: True when the firewall policy was restored to the
            baseline rule-group-reference set captured at run start.
        failed_artifacts: Names/keys of artifacts that could not be deleted
            after the maximum retry attempts.
    """

    mutations_reverted: bool
    baseline_restored: bool
    failed_artifacts: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# MutationCleaner
# ---------------------------------------------------------------------------


class MutationCleaner:
    """Reverts a run's ephemeral mutations and restores the firewall policy.

    Usage::

        cleaner = MutationCleaner(env=int_env, session=boto3_session)
        cleaner.capture_baseline()
        # ... run creates artifacts tracked in RunScope ...
        result = cleaner.revert(scope)

    The cleaner:
    1. Deletes S3 config objects created by this run.
    2. Deletes Network Firewall rule groups created by this run.
    3. Restores the firewall policy rule-group-references to baseline.
    4. Never touches stable/baseline resources.
    5. Tolerates already-deleted artifacts (ResourceNotFoundException / NoSuchKey).
    6. Records failures after 3 retry attempts in RevertResult.failed_artifacts.
    """

    def __init__(self, env: IntEnv, session: boto3.Session) -> None:
        self._env = env
        self._session = session
        self._s3 = session.client("s3")
        self._nfw = session.client("network-firewall")
        self._baseline_rule_group_references: list[dict] | None = None
        self._baseline_update_token: str | None = None

    # ------------------------------------------------------------------
    # Baseline capture
    # ------------------------------------------------------------------

    def capture_baseline(self) -> None:
        """Capture the current firewall policy rule-group references as baseline.

        Must be called BEFORE any run mutations occur so that `revert()` can
        restore the policy to this state.

        Validates: Requirement 10.8 — capture baseline before creating mutations.
        """
        response = self._nfw.describe_firewall_policy(
            FirewallPolicyArn=self._env.firewall_policy_arn
        )
        policy_detail = response["FirewallPolicy"]
        # Capture both stateless and stateful rule group references
        self._baseline_rule_group_references = (
            policy_detail.get("StatefulRuleGroupReferences", [])
        )
        self._baseline_update_token = response.get("UpdateToken")
        logger.info(
            "Captured baseline: %d stateful rule group references for policy %s",
            len(self._baseline_rule_group_references),
            self._env.firewall_policy_arn,
        )

    # ------------------------------------------------------------------
    # Revert
    # ------------------------------------------------------------------

    def revert(self, scope: RunScope) -> RevertResult:
        """Delete run-id artifacts and restore the firewall policy to baseline.

        Steps:
        1. Delete S3 config objects (scope.config_keys)
        2. Delete Network Firewall rule groups (scope.rule_group_names)
        3. Restore firewall policy rule-group-references to baseline
        4. Tolerate already-deleted artifacts
        5. Retry each deletion up to 3 times
        6. Record failures in RevertResult.failed_artifacts

        Args:
            scope: The RunScope tracking artifacts created by this run.

        Returns:
            RevertResult with mutation/baseline status and any failures.

        Validates: Requirements 10.1, 10.3, 10.4, 10.5, 10.9
        """
        failed_artifacts: list[str] = []

        # Step 1: Delete S3 config objects
        for key in scope.config_keys:
            if not self._delete_s3_object(key):
                failed_artifacts.append(f"s3://{self._env.config_bucket}/{key}")

        # Step 2: Delete Network Firewall rule groups
        for rule_group_name in scope.rule_group_names:
            if not self._delete_rule_group(rule_group_name):
                failed_artifacts.append(f"rule-group:{rule_group_name}")

        # Step 3: Restore firewall policy to baseline
        baseline_restored = self._restore_baseline_policy()

        mutations_reverted = len(failed_artifacts) == 0

        result = RevertResult(
            mutations_reverted=mutations_reverted,
            baseline_restored=baseline_restored,
            failed_artifacts=failed_artifacts,
        )

        if not mutations_reverted:
            logger.error(
                "Revert incomplete — %d artifacts failed after %d attempts each: %s",
                len(failed_artifacts),
                _MAX_RETRIES,
                failed_artifacts,
            )
        else:
            logger.info(
                "Revert complete — deleted %d config keys, %d rule groups; "
                "baseline_restored=%s",
                len(scope.config_keys),
                len(scope.rule_group_names),
                baseline_restored,
            )

        return result

    # ------------------------------------------------------------------
    # Internal: S3 deletion with retry
    # ------------------------------------------------------------------

    def _delete_s3_object(self, key: str) -> bool:
        """Attempt to delete an S3 object up to _MAX_RETRIES times.

        Tolerates NoSuchKey (already deleted).

        Returns:
            True if the object was deleted or already absent; False on failure.
        """
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                self._s3.delete_object(
                    Bucket=self._env.config_bucket,
                    Key=key,
                )
                logger.debug("Deleted S3 object: s3://%s/%s", self._env.config_bucket, key)
                return True
            except ClientError as exc:
                error_code = exc.response.get("Error", {}).get("Code", "")
                # S3 delete_object is idempotent (doesn't raise on missing key
                # in most cases), but handle NoSuchKey defensively.
                if error_code in ("NoSuchKey", "404"):
                    logger.debug(
                        "S3 object already deleted (tolerated): s3://%s/%s",
                        self._env.config_bucket,
                        key,
                    )
                    return True
                logger.warning(
                    "S3 delete attempt %d/%d failed for key '%s': %s",
                    attempt,
                    _MAX_RETRIES,
                    key,
                    exc,
                )
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_BACKOFF_BASE * (2 ** (attempt - 1)))
        return False

    # ------------------------------------------------------------------
    # Internal: Rule group deletion with retry
    # ------------------------------------------------------------------

    def _delete_rule_group(self, rule_group_name: str) -> bool:
        """Attempt to delete a Network Firewall rule group up to _MAX_RETRIES times.

        Tolerates ResourceNotFoundException (already deleted).

        Returns:
            True if the group was deleted or already absent; False on failure.
        """
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                self._nfw.delete_rule_group(
                    RuleGroupName=rule_group_name,
                    Type="STATEFUL",
                )
                logger.debug("Deleted rule group: %s", rule_group_name)
                return True
            except ClientError as exc:
                error_code = exc.response.get("Error", {}).get("Code", "")
                if error_code == "ResourceNotFoundException":
                    logger.debug(
                        "Rule group already deleted (tolerated): %s",
                        rule_group_name,
                    )
                    return True
                logger.warning(
                    "Rule group delete attempt %d/%d failed for '%s': %s",
                    attempt,
                    _MAX_RETRIES,
                    rule_group_name,
                    exc,
                )
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_BACKOFF_BASE * (2 ** (attempt - 1)))
        return False

    # ------------------------------------------------------------------
    # Internal: Restore firewall policy baseline
    # ------------------------------------------------------------------

    def _restore_baseline_policy(self) -> bool:
        """Restore the firewall policy's stateful rule-group references to baseline.

        If no baseline was captured, logs a warning and returns False.
        Retries up to _MAX_RETRIES times on transient failures.

        Returns:
            True if the policy was restored to baseline; False on failure.
        """
        if self._baseline_rule_group_references is None:
            logger.warning(
                "Cannot restore baseline — capture_baseline() was never called."
            )
            return False

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                # Fetch the current update token (it changes after every mutation).
                describe_resp = self._nfw.describe_firewall_policy(
                    FirewallPolicyArn=self._env.firewall_policy_arn
                )
                current_token = describe_resp["UpdateToken"]
                current_policy = describe_resp["FirewallPolicy"]

                # Rebuild the policy with the baseline stateful references,
                # preserving other policy fields (stateless settings, etc.).
                restored_policy = dict(current_policy)
                restored_policy["StatefulRuleGroupReferences"] = (
                    self._baseline_rule_group_references
                )

                self._nfw.update_firewall_policy(
                    FirewallPolicyArn=self._env.firewall_policy_arn,
                    FirewallPolicy=restored_policy,
                    UpdateToken=current_token,
                    Description="Restored to baseline by MutationCleaner.revert()",
                )
                logger.info(
                    "Firewall policy restored to baseline (%d stateful references).",
                    len(self._baseline_rule_group_references),
                )
                return True
            except ClientError as exc:
                error_code = exc.response.get("Error", {}).get("Code", "")
                logger.warning(
                    "Policy restore attempt %d/%d failed (error=%s): %s",
                    attempt,
                    _MAX_RETRIES,
                    error_code,
                    exc,
                )
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_BACKOFF_BASE * (2 ** (attempt - 1)))

        logger.error(
            "Failed to restore firewall policy baseline after %d attempts.",
            _MAX_RETRIES,
        )
        return False
