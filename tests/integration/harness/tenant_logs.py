"""Tenant CloudWatch log assertions — replaces FirewallInspector.

Polls the customer CloudWatch log group for processing outcomes.
The log group (``cw-<prefix>-CustomerLog-<stage>``) is where the app
writes INFO (success), WARN (skipped), and ERROR (rejected) messages
visible to the tenant.

This is the primary assertion channel for integration tests: if the
tenant can see it in their logs, the system did its job.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class TenantLogChecker:
    """Checks the tenant's customer CloudWatch log group for processing outcomes.

    The customer log group is where the real app writes success/error messages.
    This checker polls those logs to assert that the expected processing outcome
    occurred after a config upload or deletion.

    Parameters
    ----------
    session : boto3.Session
        An authenticated boto3 session for the INT account.
    log_group_name : str
        The customer log group name, e.g. ``cw-anfw-CustomerLog-int``.
    """

    def __init__(self, session: boto3.Session, log_group_name: str) -> None:
        self._logs = session.client("logs")
        self._log_group_name = log_group_name

    def wait_for_success_log(
        self,
        key: str,
        timeout_s: float = 240,
        poll_interval_s: float = 5.0,
    ) -> str:
        """Wait for a log entry indicating successful processing of the given config key.

        Looks for log messages indicating successful processing (e.g.,
        "All rules processed and sent to SQS for execution" or
        "Processing object: <key>") while excluding error messages.

        Parameters
        ----------
        key : str
            The config key to search for (e.g. ``eu-west-1-config.yaml``).
        timeout_s : float
            Maximum seconds to poll before raising TimeoutError.
        poll_interval_s : float
            Seconds between polling attempts.

        Returns
        -------
        str
            The matching log message content.

        Raises
        ------
        TimeoutError
            If no success log is found within the timeout.
        """
        start = time.time()
        # Look for logs from just before we started waiting
        start_time_ms = int((start - 60) * 1000)

        while True:
            elapsed = time.time() - start
            if elapsed >= timeout_s:
                raise TimeoutError(
                    f"No success log mentioning '{key}' found in "
                    f"'{self._log_group_name}' within {timeout_s:.0f}s"
                )

            message = self._find_log_message(
                start_time_ms=start_time_ms,
                patterns=[
                    key,
                    "All rules processed",
                    "sent to SQS for execution",
                ],
                exclude_patterns=["ERROR", "FormatError", "Invalid Format"],
                require_key_mention=True,
                key=key,
            )
            if message:
                logger.info(
                    "Success log found for key '%s': %s",
                    key,
                    message[:200],
                )
                return message

            time.sleep(poll_interval_s)

    def wait_for_error_log(
        self,
        pattern: str,
        timeout_s: float = 240,
        poll_interval_s: float = 5.0,
    ) -> str:
        """Wait for an ERROR log entry matching the given pattern.

        Searches for log events containing the pattern (interpreted as a
        regex) OR containing common error indicators like "FormatError",
        "Invalid Format", "ERROR".

        Parameters
        ----------
        pattern : str
            A regex pattern or literal string to match in log messages.
            Examples: ``"FormatError|reserved"`` or ``"sid:"``
        timeout_s : float
            Maximum seconds to poll before raising TimeoutError.
        poll_interval_s : float
            Seconds between polling attempts.

        Returns
        -------
        str
            The matching error log message.

        Raises
        ------
        TimeoutError
            If no matching error log is found within the timeout.
        """
        start = time.time()
        start_time_ms = int((start - 60) * 1000)
        compiled_pattern = re.compile(pattern, re.IGNORECASE)

        while True:
            elapsed = time.time() - start
            if elapsed >= timeout_s:
                raise TimeoutError(
                    f"No error log matching '{pattern}' found in "
                    f"'{self._log_group_name}' within {timeout_s:.0f}s"
                )

            try:
                events = self._get_log_events(start_time_ms=start_time_ms)
                for event in events:
                    msg = event.get("message", "")
                    if compiled_pattern.search(msg):
                        logger.info(
                            "Error log found matching '%s': %s",
                            pattern,
                            msg[:200],
                        )
                        return msg
            except ClientError as exc:
                logger.debug(
                    "Log query failed (will retry): %s", exc
                )

            time.sleep(poll_interval_s)

    def wait_for_skip_log(
        self,
        vpc_id: str,
        timeout_s: float = 240,
        poll_interval_s: float = 5.0,
    ) -> str:
        """Wait for a WARNING log about a VPC being skipped (not TGW-attached).

        The app emits a WARN-level log like:
            ``<vpc_id> rules skipped as it is not attached to TGW``

        Parameters
        ----------
        vpc_id : str
            The VPC ID that should appear in the skip warning.
        timeout_s : float
            Maximum seconds to poll before raising TimeoutError.
        poll_interval_s : float
            Seconds between polling attempts.

        Returns
        -------
        str
            The matching skip/warning log message.

        Raises
        ------
        TimeoutError
            If no skip log mentioning the VPC is found within the timeout.
        """
        start = time.time()
        start_time_ms = int((start - 60) * 1000)
        # Match patterns the app uses for skipped VPCs
        skip_pattern = re.compile(
            rf"{re.escape(vpc_id)}.*(?:skipped|not attached to TGW)",
            re.IGNORECASE,
        )

        while True:
            elapsed = time.time() - start
            if elapsed >= timeout_s:
                raise TimeoutError(
                    f"No skip/warning log for VPC '{vpc_id}' found in "
                    f"'{self._log_group_name}' within {timeout_s:.0f}s"
                )

            try:
                events = self._get_log_events(start_time_ms=start_time_ms)
                for event in events:
                    msg = event.get("message", "")
                    if skip_pattern.search(msg):
                        logger.info(
                            "Skip log found for VPC '%s': %s",
                            vpc_id,
                            msg[:200],
                        )
                        return msg
            except ClientError as exc:
                logger.debug(
                    "Log query failed (will retry): %s", exc
                )

            time.sleep(poll_interval_s)

    def get_recent_logs(
        self,
        filter_pattern: str = "",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get recent log events matching a filter pattern.

        Parameters
        ----------
        filter_pattern : str
            Optional CloudWatch Logs filter pattern. If empty, returns all
            recent events.
        limit : int
            Maximum number of events to return.

        Returns
        -------
        list[dict]
            Recent log events with 'timestamp', 'message', and 'logStreamName'.
        """
        try:
            kwargs: dict[str, Any] = {
                "logGroupName": self._log_group_name,
                "interleaved": True,
                "limit": limit,
            }
            if filter_pattern:
                kwargs["filterPattern"] = filter_pattern
            response = self._logs.filter_log_events(**kwargs)
            return response.get("events", [])
        except ClientError as exc:
            logger.warning("Failed to get recent logs: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_log_events(
        self,
        start_time_ms: int | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Fetch log events from the customer log group."""
        kwargs: dict[str, Any] = {
            "logGroupName": self._log_group_name,
            "interleaved": True,
            "limit": limit,
        }
        if start_time_ms is not None:
            kwargs["startTime"] = start_time_ms

        response = self._logs.filter_log_events(**kwargs)
        return response.get("events", [])

    def _find_log_message(
        self,
        start_time_ms: int,
        patterns: list[str],
        exclude_patterns: list[str] | None = None,
        require_key_mention: bool = False,
        key: str = "",
    ) -> str | None:
        """Search log events for a message matching success criteria."""
        try:
            events = self._get_log_events(start_time_ms=start_time_ms)
        except ClientError:
            return None

        for event in events:
            msg = event.get("message", "")

            # If we require the key to be mentioned, check first
            if require_key_mention and key and key not in msg:
                continue

            # Exclude error patterns from success matches
            if exclude_patterns:
                if any(ep in msg for ep in exclude_patterns):
                    continue

            # Check if any of the success patterns match
            if any(p in msg for p in patterns):
                return msg

        return None
