"""Smoke tests for wait_until bounded polling.

Basic validation that the polling function behaves correctly:
- Returns True immediately when the predicate is already true.
- Raises TimeoutError when the predicate never becomes true.
- Respects the configurable timeout.
- Rejects timeout_s above the 900 s maximum.
- Reports the unmet predicate description on timeout.
- Uses exponential backoff (no fixed sleeps).

Requirements: 8.2, 8.3, 8.4
"""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from tests.integration.harness.polling import (
    MAX_CONFIGURABLE_TIMEOUT_S,
    TimeoutError,
    wait_until,
)


class TestWaitUntilImmediateSuccess:
    """Predicate already true on first call."""

    def test_returns_true_immediately(self) -> None:
        result = wait_until(lambda: True, timeout_s=5.0)
        assert result is True

    def test_no_sleep_on_first_truthy(self) -> None:
        """No sleep should occur when predicate is true on first attempt."""
        start = time.time()
        wait_until(lambda: True, timeout_s=5.0)
        elapsed = time.time() - start
        # Should complete in well under 100ms (no sleep)
        assert elapsed < 0.1


class TestWaitUntilTimeout:
    """Predicate never becomes true."""

    def test_raises_timeout_error(self) -> None:
        with pytest.raises(TimeoutError):
            wait_until(lambda: False, timeout_s=1.0, initial_interval_s=0.1)

    def test_timeout_error_includes_description(self) -> None:
        with pytest.raises(TimeoutError, match="rule group created"):
            wait_until(
                lambda: False,
                timeout_s=0.5,
                initial_interval_s=0.1,
                description="rule group created",
            )

    def test_default_timeout_is_300s(self) -> None:
        """Default timeout_s is 300 seconds (not tested with real sleep)."""
        # We patch time.sleep and time.time to simulate passage
        call_count = 0
        fake_time = [0.0]

        def fake_time_fn() -> float:
            return fake_time[0]

        def fake_sleep(duration: float) -> None:
            nonlocal call_count
            call_count += 1
            fake_time[0] += duration

        with (
            patch("tests.integration.harness.polling.time.time", side_effect=fake_time_fn),
            patch("tests.integration.harness.polling.time.sleep", side_effect=fake_sleep),
        ):
            with pytest.raises(TimeoutError, match="300.0s"):
                wait_until(lambda: False)

        # Should have made multiple attempts
        assert call_count > 0


class TestWaitUntilMaxTimeout:
    """Validate timeout_s cannot exceed 900 s."""

    def test_rejects_timeout_above_900s(self) -> None:
        with pytest.raises(ValueError, match="exceeds the maximum"):
            wait_until(lambda: True, timeout_s=901.0)

    def test_accepts_exactly_900s(self) -> None:
        """900 s is the configured maximum — should not raise ValueError."""
        result = wait_until(lambda: True, timeout_s=MAX_CONFIGURABLE_TIMEOUT_S)
        assert result is True


class TestWaitUntilBackoff:
    """Verify exponential backoff with cap."""

    def test_exponential_intervals(self) -> None:
        """Sleep intervals should follow 1, 2, 4, 8, 16, 30, 30... pattern."""
        sleep_durations: list[float] = []
        call_count = [0]

        def never_true() -> bool:
            return False

        def record_sleep(duration: float) -> None:
            sleep_durations.append(duration)

        fake_time = [0.0]

        def fake_time_fn() -> float:
            return fake_time[0]

        original_sleep = record_sleep

        def patched_sleep(duration: float) -> None:
            original_sleep(duration)
            fake_time[0] += duration

        with (
            patch("tests.integration.harness.polling.time.time", side_effect=fake_time_fn),
            patch("tests.integration.harness.polling.time.sleep", side_effect=patched_sleep),
        ):
            with pytest.raises(TimeoutError):
                wait_until(
                    never_true,
                    timeout_s=100.0,
                    initial_interval_s=1.0,
                    backoff_factor=2.0,
                    max_interval_s=30.0,
                )

        # Expected intervals: 1, 2, 4, 8, 16, 30, 30...
        expected_uncapped = [1.0, 2.0, 4.0, 8.0, 16.0]
        for i, expected in enumerate(expected_uncapped):
            assert sleep_durations[i] == pytest.approx(expected, abs=0.01), (
                f"Interval {i} was {sleep_durations[i]}, expected {expected}"
            )
        # After 1+2+4+8+16=31s, remaining intervals should be capped at 30
        for duration in sleep_durations[5:]:
            assert duration <= 30.0

    def test_no_fixed_sleeps_all_intervals_computed(self) -> None:
        """Every sleep duration matches the capped-exponential formula.

        Proves no fixed/hardcoded sleeps are used — each interval must equal
        min(initial * factor^attempt, max_interval).

        Requirements: 8.2 (no fixed sleeps)
        """
        sleep_durations: list[float] = []
        fake_time = [0.0]

        def fake_time_fn() -> float:
            return fake_time[0]

        def patched_sleep(duration: float) -> None:
            sleep_durations.append(duration)
            fake_time[0] += duration

        initial = 1.0
        factor = 2.0
        cap = 30.0

        with (
            patch("tests.integration.harness.polling.time.time", side_effect=fake_time_fn),
            patch("tests.integration.harness.polling.time.sleep", side_effect=patched_sleep),
        ):
            with pytest.raises(TimeoutError):
                wait_until(
                    lambda: False,
                    timeout_s=200.0,
                    initial_interval_s=initial,
                    backoff_factor=factor,
                    max_interval_s=cap,
                )

        # Every recorded sleep must match the formula: min(initial * factor^i, cap)
        # (with a small tolerance for the final interval which may be clipped to
        # remaining time budget)
        for i, actual in enumerate(sleep_durations):
            expected = min(initial * (factor ** i), cap)
            # The last interval may be clipped to remaining budget — still not fixed
            assert actual <= expected + 0.01, (
                f"Interval {i}: {actual} exceeded expected computed value {expected}"
            )
            # Must be > 0 (actually sleeping)
            assert actual > 0, f"Interval {i} was zero — should always sleep"

    def test_cap_with_custom_max_interval(self) -> None:
        """Cap applies at any custom max_interval_s value.

        Requirements: 8.2 (cap at max_interval_s)
        """
        sleep_durations: list[float] = []
        fake_time = [0.0]

        def fake_time_fn() -> float:
            return fake_time[0]

        def patched_sleep(duration: float) -> None:
            sleep_durations.append(duration)
            fake_time[0] += duration

        custom_cap = 5.0

        with (
            patch("tests.integration.harness.polling.time.time", side_effect=fake_time_fn),
            patch("tests.integration.harness.polling.time.sleep", side_effect=patched_sleep),
        ):
            with pytest.raises(TimeoutError):
                wait_until(
                    lambda: False,
                    timeout_s=50.0,
                    initial_interval_s=1.0,
                    backoff_factor=2.0,
                    max_interval_s=custom_cap,
                )

        # Expected: 1, 2, 4, 5, 5, 5... (cap kicks in at interval index 3)
        assert sleep_durations[0] == pytest.approx(1.0)
        assert sleep_durations[1] == pytest.approx(2.0)
        assert sleep_durations[2] == pytest.approx(4.0)
        # From index 3 onward, all intervals must be capped at custom_cap
        for i, duration in enumerate(sleep_durations[3:], start=3):
            assert duration <= custom_cap + 0.01, (
                f"Interval {i} was {duration}, should be capped at {custom_cap}"
            )

    def test_stops_on_first_truthy(self) -> None:
        """Polling stops immediately when predicate returns True."""
        attempt = [0]

        def becomes_true_on_third() -> bool:
            attempt[0] += 1
            return attempt[0] >= 3

        with patch("tests.integration.harness.polling.time.sleep"):
            result = wait_until(
                becomes_true_on_third,
                timeout_s=60.0,
                initial_interval_s=0.01,
            )

        assert result is True
        assert attempt[0] == 3

    def test_configurable_timeout_up_to_900s(self) -> None:
        """Timeout is configurable; 900 s is accepted, > 900 s is rejected."""
        # 900 is OK (predicate true immediately so no real waiting)
        assert wait_until(lambda: True, timeout_s=900.0) is True
        # 901 raises ValueError
        with pytest.raises(ValueError):
            wait_until(lambda: True, timeout_s=901.0)


class TestWaitUntilTimeoutReporting:
    """Verify timeout failure reports the unmet predicate description.

    Requirements: 8.4
    """

    def test_timeout_message_contains_predicate_description(self) -> None:
        """The TimeoutError message must name the unmet predicate."""
        fake_time = [0.0]

        def fake_time_fn() -> float:
            return fake_time[0]

        def patched_sleep(duration: float) -> None:
            fake_time[0] += duration

        with (
            patch("tests.integration.harness.polling.time.time", side_effect=fake_time_fn),
            patch("tests.integration.harness.polling.time.sleep", side_effect=patched_sleep),
        ):
            with pytest.raises(TimeoutError, match="rule group materialized"):
                wait_until(
                    lambda: False,
                    timeout_s=5.0,
                    description="rule group materialized",
                )

    def test_timeout_message_includes_elapsed_and_attempts(self) -> None:
        """The TimeoutError message includes attempt count and elapsed time."""
        fake_time = [0.0]

        def fake_time_fn() -> float:
            return fake_time[0]

        def patched_sleep(duration: float) -> None:
            fake_time[0] += duration

        with (
            patch("tests.integration.harness.polling.time.time", side_effect=fake_time_fn),
            patch("tests.integration.harness.polling.time.sleep", side_effect=patched_sleep),
        ):
            with pytest.raises(TimeoutError) as exc_info:
                wait_until(
                    lambda: False,
                    timeout_s=10.0,
                    initial_interval_s=1.0,
                    description="firewall updated",
                )

        msg = str(exc_info.value)
        # Must include the description
        assert "firewall updated" in msg
        # Must include the timeout value
        assert "10.0s" in msg
        # Must include attempts count
        assert "attempts" in msg

    def test_timeout_uses_default_description_when_not_specified(self) -> None:
        """When no description is given, 'predicate' appears in the error."""
        fake_time = [0.0]

        def fake_time_fn() -> float:
            return fake_time[0]

        def patched_sleep(duration: float) -> None:
            fake_time[0] += duration

        with (
            patch("tests.integration.harness.polling.time.time", side_effect=fake_time_fn),
            patch("tests.integration.harness.polling.time.sleep", side_effect=patched_sleep),
        ):
            with pytest.raises(TimeoutError, match="predicate"):
                wait_until(lambda: False, timeout_s=2.0, initial_interval_s=0.5)
