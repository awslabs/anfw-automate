"""Unit tests for TenantLogChecker and ReachabilityChecker.

Mocks CloudWatch Logs and Lambda to verify the tenant-observable
outcome assertion logic without real AWS calls.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from tests.integration.harness.tenant_logs import TenantLogChecker
from tests.integration.harness.reachability import ReachabilityChecker


# ---------------------------------------------------------------------------
# TenantLogChecker fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_logs_session() -> MagicMock:
    """A mocked boto3 Session returning a mocked CloudWatch Logs client."""
    session = MagicMock()
    session.client.return_value = MagicMock()
    return session


@pytest.fixture()
def log_checker(mock_logs_session: MagicMock) -> TenantLogChecker:
    """A TenantLogChecker wired to mocked CW Logs."""
    return TenantLogChecker(
        session=mock_logs_session,
        log_group_name="cw-anfw-CustomerLog-int",
    )


def _logs_client(checker: TenantLogChecker) -> MagicMock:
    """Extract the mocked logs client."""
    return checker._logs


# ---------------------------------------------------------------------------
# TenantLogChecker tests
# ---------------------------------------------------------------------------


class TestTenantLogChecker:
    """Tests for TenantLogChecker."""

    def test_wait_for_success_log_returns_matching_message(
        self, log_checker: TenantLogChecker
    ) -> None:
        """Returns the log message when success pattern is found."""
        logs = _logs_client(log_checker)
        logs.filter_log_events.return_value = {
            "events": [
                {
                    "message": "Processing object: eu-west-1-config.yaml",
                    "timestamp": 1700000000000,
                },
                {
                    "message": "All rules processed and sent to SQS for execution.",
                    "timestamp": 1700000001000,
                },
            ]
        }

        result = log_checker.wait_for_success_log(
            key="eu-west-1-config.yaml",
            timeout_s=5,
            poll_interval_s=0.1,
        )
        assert "eu-west-1-config.yaml" in result

    def test_wait_for_success_log_times_out_when_no_match(
        self, log_checker: TenantLogChecker
    ) -> None:
        """Raises TimeoutError when no success log appears."""
        logs = _logs_client(log_checker)
        logs.filter_log_events.return_value = {"events": []}

        with pytest.raises(TimeoutError, match="No success log"):
            log_checker.wait_for_success_log(
                key="missing-config.yaml",
                timeout_s=0.5,
                poll_interval_s=0.1,
            )

    def test_wait_for_success_log_excludes_error_messages(
        self, log_checker: TenantLogChecker
    ) -> None:
        """Success check excludes messages containing error patterns."""
        logs = _logs_client(log_checker)
        logs.filter_log_events.return_value = {
            "events": [
                {
                    "message": "ERROR: FormatError processing eu-west-1-config.yaml",
                    "timestamp": 1700000000000,
                },
            ]
        }

        with pytest.raises(TimeoutError):
            log_checker.wait_for_success_log(
                key="eu-west-1-config.yaml",
                timeout_s=0.5,
                poll_interval_s=0.1,
            )

    def test_wait_for_error_log_returns_matching_message(
        self, log_checker: TenantLogChecker
    ) -> None:
        """Returns the error message when pattern matches."""
        logs = _logs_client(log_checker)
        logs.filter_log_events.return_value = {
            "events": [
                {
                    "message": "Invalid Format: FormatError - reserved keyword 'sid:' detected",
                    "timestamp": 1700000000000,
                },
            ]
        }

        result = log_checker.wait_for_error_log(
            pattern="FormatError|reserved",
            timeout_s=5,
            poll_interval_s=0.1,
        )
        assert "FormatError" in result

    def test_wait_for_error_log_times_out_when_no_match(
        self, log_checker: TenantLogChecker
    ) -> None:
        """Raises TimeoutError when no error log matches the pattern."""
        logs = _logs_client(log_checker)
        logs.filter_log_events.return_value = {"events": []}

        with pytest.raises(TimeoutError, match="No error log matching"):
            log_checker.wait_for_error_log(
                pattern="NonExistentError",
                timeout_s=0.5,
                poll_interval_s=0.1,
            )

    def test_wait_for_error_log_handles_regex_pattern(
        self, log_checker: TenantLogChecker
    ) -> None:
        """Pattern is treated as regex for flexible matching."""
        logs = _logs_client(log_checker)
        logs.filter_log_events.return_value = {
            "events": [
                {
                    "message": "Invalid Format: reserved keyword detected",
                    "timestamp": 1700000000000,
                },
            ]
        }

        result = log_checker.wait_for_error_log(
            pattern="reserved.*keyword",
            timeout_s=5,
            poll_interval_s=0.1,
        )
        assert "reserved keyword" in result

    def test_wait_for_skip_log_returns_matching_message(
        self, log_checker: TenantLogChecker
    ) -> None:
        """Returns the skip message when VPC skip pattern is found."""
        logs = _logs_client(log_checker)
        logs.filter_log_events.return_value = {
            "events": [
                {
                    "message": "vpc-0abcdef123456 rules skipped as it is not attached to TGW",
                    "timestamp": 1700000000000,
                },
            ]
        }

        result = log_checker.wait_for_skip_log(
            vpc_id="vpc-0abcdef123456",
            timeout_s=5,
            poll_interval_s=0.1,
        )
        assert "vpc-0abcdef123456" in result
        assert "skipped" in result

    def test_wait_for_skip_log_times_out_when_no_match(
        self, log_checker: TenantLogChecker
    ) -> None:
        """Raises TimeoutError when no skip log is found for the VPC."""
        logs = _logs_client(log_checker)
        logs.filter_log_events.return_value = {"events": []}

        with pytest.raises(TimeoutError, match="No skip/warning log"):
            log_checker.wait_for_skip_log(
                vpc_id="vpc-nonexistent",
                timeout_s=0.5,
                poll_interval_s=0.1,
            )

    def test_get_recent_logs_returns_events(
        self, log_checker: TenantLogChecker
    ) -> None:
        """get_recent_logs returns available log events."""
        logs = _logs_client(log_checker)
        logs.filter_log_events.return_value = {
            "events": [
                {"message": "event1", "timestamp": 1700000000000},
                {"message": "event2", "timestamp": 1700000001000},
            ]
        }

        results = log_checker.get_recent_logs(limit=10)
        assert len(results) == 2

    def test_get_recent_logs_returns_empty_on_error(
        self, log_checker: TenantLogChecker
    ) -> None:
        """get_recent_logs returns empty list on API error."""
        logs = _logs_client(log_checker)
        logs.filter_log_events.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "not found"}},
            "FilterLogEvents",
        )

        results = log_checker.get_recent_logs()
        assert results == []

    def test_get_recent_logs_with_filter_pattern(
        self, log_checker: TenantLogChecker
    ) -> None:
        """get_recent_logs passes filter_pattern to CW Logs API."""
        logs = _logs_client(log_checker)
        logs.filter_log_events.return_value = {"events": []}

        log_checker.get_recent_logs(filter_pattern="ERROR", limit=10)

        call_kwargs = logs.filter_log_events.call_args[1]
        assert call_kwargs["filterPattern"] == "ERROR"
        assert call_kwargs["limit"] == 10


# ---------------------------------------------------------------------------
# ReachabilityChecker fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_lambda_session() -> MagicMock:
    """A mocked boto3 Session returning a mocked Lambda client."""
    session = MagicMock()
    session.client.return_value = MagicMock()
    return session


@pytest.fixture()
def reachability_checker(mock_lambda_session: MagicMock) -> ReachabilityChecker:
    """A ReachabilityChecker wired to mocked Lambda."""
    return ReachabilityChecker(
        session=mock_lambda_session,
        checker_function_name="anfw-int-probe-int",
    )


def _lambda_client(checker: ReachabilityChecker) -> MagicMock:
    """Extract the mocked Lambda client."""
    return checker._lambda


def _make_lambda_response(reachable: bool, error: str | None = None) -> dict:
    """Build a mock Lambda invoke response."""
    payload = json.dumps({"reachable": reachable, "error": error}).encode()
    mock_payload = MagicMock()
    mock_payload.read.return_value = payload
    return {"Payload": mock_payload, "StatusCode": 200}


# ---------------------------------------------------------------------------
# ReachabilityChecker tests
# ---------------------------------------------------------------------------


class TestReachabilityChecker:
    """Tests for ReachabilityChecker."""

    def test_can_reach_returns_true_when_reachable(
        self, reachability_checker: ReachabilityChecker
    ) -> None:
        """can_reach returns True when probe reports reachable."""
        lmb = _lambda_client(reachability_checker)
        lmb.invoke.return_value = _make_lambda_response(reachable=True)

        assert reachability_checker.can_reach("example.com", port=443) is True

    def test_can_reach_returns_false_when_blocked(
        self, reachability_checker: ReachabilityChecker
    ) -> None:
        """can_reach returns False when probe reports not reachable."""
        lmb = _lambda_client(reachability_checker)
        lmb.invoke.return_value = _make_lambda_response(
            reachable=False, error="connect_ex returned 110"
        )

        assert reachability_checker.can_reach("blocked.com", port=443) is False

    def test_cannot_reach_returns_true_when_blocked(
        self, reachability_checker: ReachabilityChecker
    ) -> None:
        """cannot_reach returns True when probe reports not reachable."""
        lmb = _lambda_client(reachability_checker)
        lmb.invoke.return_value = _make_lambda_response(
            reachable=False, error="Connection timed out"
        )

        assert reachability_checker.cannot_reach("blocked.com", port=443) is True

    def test_cannot_reach_returns_false_when_reachable(
        self, reachability_checker: ReachabilityChecker
    ) -> None:
        """cannot_reach returns False when probe reports reachable."""
        lmb = _lambda_client(reachability_checker)
        lmb.invoke.return_value = _make_lambda_response(reachable=True)

        assert reachability_checker.cannot_reach("allowed.com", port=443) is False

    def test_can_reach_invokes_probe_with_correct_payload(
        self, reachability_checker: ReachabilityChecker
    ) -> None:
        """Probe Lambda is invoked with the domain, port, and timeout."""
        lmb = _lambda_client(reachability_checker)
        lmb.invoke.return_value = _make_lambda_response(reachable=True)

        reachability_checker.can_reach("test.example.com", port=8080, timeout_s=5.0)

        lmb.invoke.assert_called_once()
        call_kwargs = lmb.invoke.call_args[1]
        assert call_kwargs["FunctionName"] == "anfw-int-probe-int"
        assert call_kwargs["InvocationType"] == "RequestResponse"

        payload = json.loads(call_kwargs["Payload"].decode())
        assert payload["domain"] == "test.example.com"
        assert payload["port"] == 8080
        assert payload["timeout_s"] == 5.0

    def test_can_reach_returns_false_on_lambda_error(
        self, reachability_checker: ReachabilityChecker
    ) -> None:
        """Returns False when Lambda invocation has a FunctionError."""
        lmb = _lambda_client(reachability_checker)
        response = _make_lambda_response(reachable=False)
        response["FunctionError"] = "Unhandled"
        lmb.invoke.return_value = response

        assert reachability_checker.can_reach("example.com") is False

    def test_can_reach_returns_false_on_client_error(
        self, reachability_checker: ReachabilityChecker
    ) -> None:
        """Returns False when Lambda invoke raises ClientError."""
        lmb = _lambda_client(reachability_checker)
        lmb.invoke.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "not found"}},
            "Invoke",
        )

        assert reachability_checker.can_reach("example.com") is False

    def test_can_reach_returns_false_on_malformed_response(
        self, reachability_checker: ReachabilityChecker
    ) -> None:
        """Returns False when probe response is malformed JSON."""
        lmb = _lambda_client(reachability_checker)
        mock_payload = MagicMock()
        mock_payload.read.return_value = b"not json"
        lmb.invoke.return_value = {"Payload": mock_payload, "StatusCode": 200}

        assert reachability_checker.can_reach("example.com") is False

    def test_assert_reachable_passes_when_immediately_reachable(
        self, reachability_checker: ReachabilityChecker
    ) -> None:
        """assert_reachable returns immediately when probe succeeds."""
        lmb = _lambda_client(reachability_checker)
        lmb.invoke.return_value = _make_lambda_response(reachable=True)

        # Should not raise
        reachability_checker.assert_reachable("example.com", timeout_s=5)

    def test_assert_reachable_raises_on_timeout(
        self, reachability_checker: ReachabilityChecker
    ) -> None:
        """assert_reachable raises AssertionError when domain stays blocked."""
        lmb = _lambda_client(reachability_checker)
        lmb.invoke.return_value = _make_lambda_response(reachable=False)

        with pytest.raises(AssertionError, match="to be reachable"):
            reachability_checker.assert_reachable(
                "blocked.com", timeout_s=0.5, poll_interval_s=0.1
            )

    def test_assert_blocked_passes_when_immediately_blocked(
        self, reachability_checker: ReachabilityChecker
    ) -> None:
        """assert_blocked returns immediately when probe reports blocked."""
        lmb = _lambda_client(reachability_checker)
        lmb.invoke.return_value = _make_lambda_response(reachable=False)

        # Should not raise
        reachability_checker.assert_blocked("blocked.com", timeout_s=5)

    def test_assert_blocked_raises_on_timeout(
        self, reachability_checker: ReachabilityChecker
    ) -> None:
        """assert_blocked raises AssertionError when domain stays reachable."""
        lmb = _lambda_client(reachability_checker)
        lmb.invoke.return_value = _make_lambda_response(reachable=True)

        with pytest.raises(AssertionError, match="to be BLOCKED"):
            reachability_checker.assert_blocked(
                "example.com", timeout_s=0.5, poll_interval_s=0.1
            )
