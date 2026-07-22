"""FirewallInspector — read-only assertions against real Network Firewall.

Provides query methods for integration tests to verify rule group state
after the real event path completes. All methods are read-only; they never
mutate firewall resources.

Requirements: 9.1, 9.9
"""

from __future__ import annotations

import logging
import re

import boto3
from botocore.exceptions import ClientError

from tests.integration.env.stable import IntEnv

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex for parsing rule_name from Suricata metadata
# ---------------------------------------------------------------------------

_RULE_NAME_PATTERN = re.compile(r"metadata\s*:.*?rule_name\s+([^;]+);")
"""Matches 'metadata: ... rule_name <name>;' within a Suricata rule string."""


# ---------------------------------------------------------------------------
# FirewallInspector
# ---------------------------------------------------------------------------


class FirewallInspector:
    """Read-only inspector for Network Firewall rule groups and rules.

    Used by integration tests to verify that the real event path
    (S3 → EventBridge → RuleCollect → SQS → RuleExecute → NFW) produced
    the expected firewall state.

    All methods use the ``network-firewall`` boto3 client and perform only
    read operations (``list_rule_groups``, ``describe_rule_group``).
    """

    def __init__(self, env: IntEnv, session: boto3.Session) -> None:
        self._env = env
        self._session = session
        self._nfw = session.client("network-firewall")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_rule_group_names(self, run_id: str) -> list[str]:
        """List Network Firewall rule group names scoped to a run_id.

        Returns only stateful rule groups whose name contains the given
        ``run_id``. Uses pagination to handle accounts with many rule groups.

        Args:
            run_id: The run identifier to filter by (e.g. ``int-abcdef01-1700000000``).

        Returns:
            A list of rule group names containing the run_id substring.

        Validates: Requirement 9.1
        """
        names: list[str] = []

        try:
            paginator = self._nfw.get_paginator("list_rule_groups")
            pages = paginator.paginate(Type="STATEFUL")

            for page in pages:
                for rg in page.get("RuleGroups", []):
                    name = rg.get("Name", "")
                    if run_id in name:
                        names.append(name)
        except ClientError as exc:
            logger.error(
                "Failed to list rule groups for run_id '%s': %s",
                run_id,
                exc,
            )
            raise

        logger.debug(
            "list_rule_group_names(run_id=%s): found %d groups: %s",
            run_id,
            len(names),
            names,
        )
        return names

    def rule_names_in_group(self, rule_group_name: str) -> list[str]:
        """Get rule names from metadata within a specific rule group.

        Calls ``describe_rule_group`` and parses the Suricata rules source
        string looking for ``metadata: ... rule_name <name>;`` patterns.

        Args:
            rule_group_name: The name of the stateful rule group to inspect.

        Returns:
            A list of rule names extracted from the metadata of each rule
            string. Returns an empty list if no rules or no metadata is found.

        Validates: Requirement 9.1
        """
        try:
            response = self._nfw.describe_rule_group(
                RuleGroupName=rule_group_name,
                Type="STATEFUL",
            )
        except ClientError as exc:
            logger.error(
                "Failed to describe rule group '%s': %s",
                rule_group_name,
                exc,
            )
            raise

        # Navigate into the rules source string
        rule_group = response.get("RuleGroup", {})
        rules_source = rule_group.get("RulesSource", {})
        rules_string = rules_source.get("RulesString", "")

        if not rules_string:
            logger.debug(
                "rule_names_in_group(%s): no RulesString found",
                rule_group_name,
            )
            return []

        # Parse rule_name from each rule line's metadata
        rule_names: list[str] = []
        for line in rules_string.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            match = _RULE_NAME_PATTERN.search(line)
            if match:
                rule_names.append(match.group(1).strip())

        logger.debug(
            "rule_names_in_group(%s): found %d rule names: %s",
            rule_group_name,
            len(rule_names),
            rule_names,
        )
        return rule_names

    def reserved_group_exists(self) -> bool:
        """Check if a '-reserved' default-deny rule group exists.

        Scans all stateful rule groups and returns True if any group's name
        contains the substring ``-reserved``.

        Returns:
            True if a rule group with '-reserved' in its name is present;
            False otherwise.

        Validates: Requirement 9.9
        """
        try:
            paginator = self._nfw.get_paginator("list_rule_groups")
            pages = paginator.paginate(Type="STATEFUL")

            for page in pages:
                for rg in page.get("RuleGroups", []):
                    name = rg.get("Name", "")
                    if "-reserved" in name:
                        logger.debug(
                            "reserved_group_exists: found '%s'", name
                        )
                        return True
        except ClientError as exc:
            logger.error("Failed to list rule groups for reserved check: %s", exc)
            raise

        logger.debug("reserved_group_exists: no '-reserved' group found")
        return False
