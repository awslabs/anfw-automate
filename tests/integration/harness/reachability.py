"""Network reachability assertions from the tenant VPC.

Verifies actual traffic flow through the Network Firewall by invoking a
probe Lambda deployed in the tenant VPC (TGW-attached, routed through NFW).
If a domain is allowed by NFW rules, the TCP connection succeeds. If blocked
by default-deny or an explicit drop rule, the connection fails.

This is the secondary assertion channel: it proves that rules have taken
effect at the data-plane level, not just the control plane.
"""

from __future__ import annotations

import json
import logging
import time

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class ReachabilityChecker:
    """Verifies network reachability from the tenant VPC through NFW.

    Uses a Lambda function deployed in the tenant VPC to attempt HTTPS
    connections to specified domains. If the domain is allowed by NFW rules,
    the connection succeeds. If blocked, it fails.

    Parameters
    ----------
    session : boto3.Session
        An authenticated boto3 session for the INT account.
    checker_function_name : str
        The name of the probe Lambda function deployed in the tenant VPC.
    """

    def __init__(
        self,
        session: boto3.Session,
        checker_function_name: str,
    ) -> None:
        self._lambda = session.client("lambda")
        self._probe_function_name = checker_function_name

    def can_reach(
        self,
        domain: str,
        port: int = 443,
        timeout_s: float = 10.0,
    ) -> bool:
        """Invoke the checker Lambda to test if a domain is reachable.

        Returns True if connection succeeds, False if blocked by NFW.

        Parameters
        ----------
        domain : str
            The domain name to test connectivity to.
        port : int
            The TCP port to connect to. Defaults to 443.
        timeout_s : float
            Connection timeout for the probe. Defaults to 10 seconds.

        Returns
        -------
        bool
            True if the domain:port is reachable from the tenant VPC.
        """
        return self._invoke_probe(domain, port, timeout_s)

    def cannot_reach(
        self,
        domain: str,
        port: int = 443,
        timeout_s: float = 10.0,
    ) -> bool:
        """Test if a domain:port is NOT reachable (blocked by NFW).

        Returns True if the connection is blocked/times out (meaning the
        NFW default-deny or an explicit drop rule applies).

        Parameters
        ----------
        domain : str
            The domain name to test connectivity to.
        port : int
            The TCP port to connect to. Defaults to 443.
        timeout_s : float
            Connection timeout for the probe. Defaults to 10 seconds.

        Returns
        -------
        bool
            True if the domain:port is NOT reachable (blocked by firewall).
        """
        return not self._invoke_probe(domain, port, timeout_s)

    def assert_reachable(
        self,
        domain: str,
        port: int = 443,
        timeout_s: float = 60,
        poll_interval_s: float = 5.0,
    ) -> None:
        """Assert the domain IS reachable (rule was applied). Polls with backoff.

        Retries the reachability check until the domain is reachable or the
        timeout expires. This accounts for propagation delay between NFW rule
        application and actual data-plane enforcement.

        Parameters
        ----------
        domain : str
            The domain to verify reachability for.
        port : int
            TCP port to check. Defaults to 443.
        timeout_s : float
            Maximum seconds to retry before failing.
        poll_interval_s : float
            Seconds between retry attempts.

        Raises
        ------
        AssertionError
            If the domain is not reachable within the timeout.
        """
        start = time.time()
        while True:
            if self._invoke_probe(domain, port, timeout_s=10.0):
                return
            elapsed = time.time() - start
            if elapsed >= timeout_s:
                raise AssertionError(
                    f"Expected {domain}:{port} to be reachable from tenant VPC "
                    f"within {timeout_s:.0f}s, but it remained blocked."
                )
            time.sleep(poll_interval_s)

    def assert_blocked(
        self,
        domain: str,
        port: int = 443,
        timeout_s: float = 60,
        poll_interval_s: float = 5.0,
    ) -> None:
        """Assert the domain is NOT reachable (rule was not applied or removed).

        Retries until the domain is confirmed blocked or the timeout expires.
        This accounts for propagation delay after rule removal.

        Parameters
        ----------
        domain : str
            The domain to verify is blocked.
        port : int
            TCP port to check. Defaults to 443.
        timeout_s : float
            Maximum seconds to retry before failing.
        poll_interval_s : float
            Seconds between retry attempts.

        Raises
        ------
        AssertionError
            If the domain is still reachable after the timeout.
        """
        start = time.time()
        while True:
            if not self._invoke_probe(domain, port, timeout_s=10.0):
                return
            elapsed = time.time() - start
            if elapsed >= timeout_s:
                raise AssertionError(
                    f"Expected {domain}:{port} to be BLOCKED from tenant VPC "
                    f"within {timeout_s:.0f}s, but it remained reachable."
                )
            time.sleep(poll_interval_s)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _invoke_probe(
        self,
        domain: str,
        port: int,
        timeout_s: float,
    ) -> bool:
        """Invoke the probe Lambda and return reachability result.

        The probe Lambda accepts:
            {"domain": "example.com", "port": 443, "timeout_s": 10}

        And returns:
            {"reachable": true/false, "error": null/"message"}
        """
        payload = json.dumps({
            "domain": domain,
            "port": port,
            "timeout_s": timeout_s,
        })

        try:
            response = self._lambda.invoke(
                FunctionName=self._probe_function_name,
                InvocationType="RequestResponse",
                Payload=payload.encode("utf-8"),
            )

            # Read response payload
            response_payload = json.loads(
                response["Payload"].read().decode("utf-8")
            )

            # Check for Lambda-level errors
            if "FunctionError" in response:
                logger.warning(
                    "Probe Lambda error for %s:%d — %s",
                    domain,
                    port,
                    response_payload,
                )
                return False

            reachable = response_payload.get("reachable", False)
            logger.debug(
                "Probe result: %s:%d reachable=%s",
                domain,
                port,
                reachable,
            )
            return reachable

        except ClientError as exc:
            logger.error(
                "Failed to invoke probe Lambda '%s': %s",
                self._probe_function_name,
                exc,
            )
            return False
        except (json.JSONDecodeError, KeyError) as exc:
            logger.error(
                "Failed to parse probe Lambda response: %s", exc
            )
            return False
