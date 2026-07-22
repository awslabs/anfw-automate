"""Stable-tier environment resolver and account guardrail.

This module provides the StableEnvResolver which guards against running
integration tests in any account that is NOT the allowlisted INT account.
It also resolves handles from the already-deployed stable stacks into an
immutable IntEnv for use by test runs.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import (
    ClientError,
    ConnectTimeoutError,
    ReadTimeoutError,
)

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib
    except ModuleNotFoundError:  # pragma: no cover
        import tomli as tomllib  # type: ignore[no-redef]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_STS_TIMEOUT_SECONDS = 5
"""Maximum time allowed for STS GetCallerIdentity before aborting."""

_CDK_DEPLOY_TIMEOUT_SECONDS = 600
"""Maximum time allowed for a cdk deploy operation before aborting."""

_CONFIG_PATH = Path(__file__).resolve().parents[3] / "scripts" / "velocity" / "config.toml"
"""Path to the DVP config file containing the allowlisted INT account."""

_INT_ENV_DIR = Path(__file__).resolve().parent
"""Directory containing the IntBaseStack CDK app (cdk.json, app.ts, etc.)."""

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class AccountGuardError(Exception):
    """Raised when the account guardrail rejects the caller environment.

    Contains a human-readable message naming the rejected account or the
    failure condition (e.g. timeout).
    """


class EnsureBaseInfraError(Exception):
    """Raised when ensure_base_infra() fails to deploy or update the stable tier.

    Contains a human-readable message with the cdk deploy failure details.
    CloudFormation native rollback is relied upon to restore the stack — this
    error is an indication that the ensure step failed, not a signal to
    destroy or recreate the stable tier.
    """


class ResolveError(Exception):
    """Raised when resolve() cannot read a required handle from stable stacks.

    Contains a human-readable message naming the missing stack or handle.
    The resolve step provisions nothing — it only reads existing CFN outputs.
    """


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IntEnv:
    """Immutable handle set resolved from the already-deployed stable stacks."""

    run_id: str
    account_id: str
    region: str
    config_bucket: str
    vpc_id: str
    firewall_policy_arn: str
    xaccount_role_arn: str
    event_bus_arn: str


@dataclass
class RunScope:
    """Tracks the ephemeral artifacts created during a single integration run."""

    run_id: str
    config_keys: list[str] = field(default_factory=list)
    rule_group_names: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# StableEnvResolver
# ---------------------------------------------------------------------------


class StableEnvResolver:
    """Manages the stable INT tier and enforces the account guardrail.

    The resolver reads the allowlisted INT account from
    ``scripts/velocity/config.toml`` and uses STS to verify that the caller
    is operating within that account before any mutation occurs.
    """

    def __init__(self, config_path: Path | None = None) -> None:
        self._config_path = config_path or _CONFIG_PATH
        self._allowlisted_account_id = self._load_allowlisted_account()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def assert_is_int_account(self) -> None:
        """Raise unless the caller account is the allowlisted INT account.

        Behaviour
        ---------
        - Resolves caller identity via STS ``GetCallerIdentity`` with a
          5-second connect and read timeout.
        - Aborts *without mutation* if the resolved account does not match
          the single allowlisted INT account from config.toml.
        - Emits a rejection ``AccountGuardError`` naming the rejected
          account.
        - Treats any identity-resolution timeout as an abort (raises
          ``AccountGuardError`` with a timeout message).

        Validates
        ---------
        Requirements 5.1, 5.2, 5.5, 5.6, 5.7
        """
        try:
            caller_account = self._resolve_caller_account()
        except (ConnectTimeoutError, ReadTimeoutError) as exc:
            raise AccountGuardError(
                "Account guardrail: STS identity resolution timed out after "
                f"{_STS_TIMEOUT_SECONDS}s — aborting without mutation. "
                "Cannot verify caller is the allowlisted INT account."
            ) from exc
        except ClientError as exc:
            raise AccountGuardError(
                "Account guardrail: failed to resolve caller identity via STS — "
                f"aborting without mutation. Error: {exc}"
            ) from exc

        if caller_account != self._allowlisted_account_id:
            raise AccountGuardError(
                f"Account guardrail: caller account '{caller_account}' is NOT the "
                f"allowlisted INT account '{self._allowlisted_account_id}'. "
                "Aborting without mutation — integration tests may only run "
                "against the fixed INT account."
            )

    def resolve(self, run_id: str) -> IntEnv:
        """Read handles from the deployed stable stacks into an IntEnv.

        Behaviour
        ---------
        - Reads CloudFormation exports matching the name prefix pattern
          ``{namePrefix}-int-*`` to obtain vpc_id, firewall_policy_arn,
          config_bucket, xaccount_role_arn, and event_bus_arn.
        - Reads account_id and region from the current boto3 session.
        - Returns a fully populated ``IntEnv`` dataclass.
        - If any required handle is missing (stack not deployed, export not
          found), raises ``ResolveError`` naming the missing handle.
        - Provisions nothing — this is a read-only operation.

        Validates
        ---------
        Requirements 6.5, 6.6
        """
        name_prefix = self._load_name_prefix()

        # Determine account_id and region from the session
        try:
            account_id = self._resolve_caller_account()
        except (ConnectTimeoutError, ReadTimeoutError, ClientError) as exc:
            raise ResolveError(
                f"resolve: failed to determine caller account — {exc}"
            ) from exc

        session = boto3.session.Session()
        region = session.region_name or "us-east-1"

        # Read CloudFormation exports
        export_map = self._read_cfn_exports(name_prefix, region)

        # Map export names to IntEnv fields
        required_handles = {
            "config_bucket": f"{name_prefix}-int-config-bucket-name",
            "vpc_id": f"{name_prefix}-int-vpc-id",
            "firewall_policy_arn": f"{name_prefix}-int-firewall-policy-arn",
            "xaccount_role_arn": f"{name_prefix}-int-xaccount-role-arn",
            "event_bus_arn": f"{name_prefix}-int-event-bus-arn",
        }

        resolved: dict[str, str] = {}
        missing: list[str] = []

        for field_name, export_name in required_handles.items():
            value = export_map.get(export_name)
            if not value:
                missing.append(export_name)
            else:
                resolved[field_name] = value

        if missing:
            raise ResolveError(
                "resolve: required handle(s) not found in CloudFormation exports. "
                "The stable IntBaseStack may not be deployed or is missing outputs. "
                f"Missing export(s): {', '.join(missing)}"
            )

        return IntEnv(
            run_id=run_id,
            account_id=account_id,
            region=region,
            **resolved,
        )

    def ensure_base_infra(self) -> None:
        """Verify/update the stable IntBaseStack via ``cdk deploy`` UPDATE.

        Behaviour
        ---------
        - Runs ``cdk deploy IntBaseStack --require-approval never`` from the
          ``tests/integration/env/`` directory.
        - Idempotent and cheap: if the CloudFormation changeset is empty (no
          changes), CDK exits successfully and this method is a no-op.
        - On failure: relies on CloudFormation native rollback of the stable
          stack. Never calls ``cdk destroy`` or replaces stable resources
          (TGW VPC, firewall policy, S3 bucket, or cross-account role).
        - Raises ``EnsureBaseInfraError`` with deploy details on failure.

        Validates
        ---------
        Requirements 6.2, 6.3, 6.4, 6.7
        """
        cmd = [
            "npx", "cdk", "deploy", "IntBaseStack",
            "--require-approval", "never",
            "--app", "npx ts-node --prefer-ts-exts app.ts",
        ]

        logger.info(
            "ensure_base_infra: starting cdk deploy IntBaseStack "
            "(idempotent UPDATE; no-op if unchanged)"
        )

        try:
            result = subprocess.run(
                cmd,
                cwd=str(_INT_ENV_DIR),
                capture_output=True,
                text=True,
                timeout=_CDK_DEPLOY_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            logger.error(
                "ensure_base_infra: cdk deploy timed out after %ds",
                _CDK_DEPLOY_TIMEOUT_SECONDS,
            )
            raise EnsureBaseInfraError(
                f"ensure_base_infra failed: cdk deploy timed out after "
                f"{_CDK_DEPLOY_TIMEOUT_SECONDS}s. CloudFormation native rollback "
                f"will restore the stack. stdout={exc.stdout!r}, stderr={exc.stderr!r}"
            ) from exc

        # CDK exits 0 on success (including no-op when changeset is empty)
        if result.returncode == 0:
            # Detect the no-op case from CDK output
            combined_output = (result.stdout or "") + (result.stderr or "")
            if "no changes" in combined_output.lower() or "did not change" in combined_output.lower():
                logger.info(
                    "ensure_base_infra: no changes detected — stable tier is current (no-op)"
                )
            else:
                logger.info(
                    "ensure_base_infra: cdk deploy completed successfully — "
                    "stable tier updated"
                )
            return

        # Non-zero exit: deploy failed. CloudFormation native rollback handles
        # the stack; we emit the ensure-failed indication.
        logger.error(
            "ensure_base_infra: cdk deploy failed (exit %d). "
            "Relying on CloudFormation native rollback.",
            result.returncode,
        )
        raise EnsureBaseInfraError(
            f"ensure_base_infra failed: cdk deploy exited with status "
            f"{result.returncode}. CloudFormation native rollback will restore "
            f"the stack — the stable tier is NOT destroyed or recreated.\n"
            f"stdout: {result.stdout[-2000:] if result.stdout else '(empty)'}\n"
            f"stderr: {result.stderr[-2000:] if result.stderr else '(empty)'}"
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_allowlisted_account(self) -> str:
        """Read the allowlisted INT account id from config.toml."""
        if not self._config_path.exists():
            raise AccountGuardError(
                f"Account guardrail: config file not found at {self._config_path}"
            )

        with open(self._config_path, "rb") as f:
            config = tomllib.load(f)

        try:
            account_id: str = config["int_account"]["account_id"]
        except KeyError as exc:
            raise AccountGuardError(
                "Account guardrail: [int_account].account_id not found in "
                f"{self._config_path}"
            ) from exc

        if not account_id or account_id == "PLACEHOLDER_INT_ACCOUNT_ID":
            raise AccountGuardError(
                "Account guardrail: [int_account].account_id is still a "
                f"placeholder in {self._config_path} — replace with the real "
                "12-digit INT account id before running integration tests."
            )

        return account_id

    def _resolve_caller_account(self) -> str:
        """Call STS GetCallerIdentity with a 5s timeout and return the account."""
        sts = boto3.client(
            "sts",
            config=BotoConfig(
                connect_timeout=_STS_TIMEOUT_SECONDS,
                read_timeout=_STS_TIMEOUT_SECONDS,
                retries={"max_attempts": 0},
            ),
        )
        response = sts.get_caller_identity()
        return response["Account"]

    def _load_name_prefix(self) -> str:
        """Read the name prefix from config.toml, defaulting to 'anfw'."""
        if not self._config_path.exists():
            return "anfw"

        with open(self._config_path, "rb") as f:
            config = tomllib.load(f)

        return config.get("int_account", {}).get("name_prefix", "anfw")

    def _read_cfn_exports(self, name_prefix: str, region: str) -> dict[str, str]:
        """Read all CloudFormation exports and return those matching the name prefix.

        Paginates through list_exports and returns a dict of
        {export_name: export_value} for exports whose name starts with
        ``{name_prefix}-int-``.

        Raises ResolveError if the CloudFormation API call fails.
        """
        try:
            cfn = boto3.client(
                "cloudformation",
                region_name=region,
                config=BotoConfig(
                    connect_timeout=_STS_TIMEOUT_SECONDS,
                    read_timeout=_STS_TIMEOUT_SECONDS,
                    retries={"max_attempts": 2},
                ),
            )
            export_map: dict[str, str] = {}
            paginator = cfn.get_paginator("list_exports")
            prefix = f"{name_prefix}-int-"

            for page in paginator.paginate():
                for export in page.get("Exports", []):
                    name = export.get("Name", "")
                    if name.startswith(prefix):
                        export_map[name] = export.get("Value", "")

            return export_map
        except ClientError as exc:
            raise ResolveError(
                f"resolve: CloudFormation list_exports failed — "
                f"the stable IntBaseStack may not be deployed. Error: {exc}"
            ) from exc
