"""Bounded polling with capped exponential backoff.

Provides ``wait_until`` for asserting asynchronous post-conditions in
integration tests without fixed sleeps. The poller starts at a 1-second
interval, doubles after each attempt (capped at 30 s), and stops on the
first truthy result or raises ``TimeoutError`` identifying the unmet
predicate.

Requirements: 8.2, 8.3, 8.4
"""

from __future__ import annotations

import time
from typing import Callable

#: Absolute maximum timeout that can be configured (seconds).
MAX_CONFIGURABLE_TIMEOUT_S: float = 900.0


class TimeoutError(Exception):
    """Raised when a polled predicate does not become true within its timeout.

    The message identifies the unmet predicate via the ``description``
    parameter passed to ``wait_until``.
    """


def wait_until(
    predicate: Callable[[], bool],
    *,
    timeout_s: float = 300.0,
    initial_interval_s: float = 1.0,
    backoff_factor: float = 2.0,
    max_interval_s: float = 30.0,
    description: str = "predicate",
) -> bool:
    """Poll a predicate with capped exponential backoff.

    Evaluates ``predicate()`` immediately on the first attempt (no sleep
    before the first check). If it returns a truthy value, ``wait_until``
    returns ``True`` immediately. Otherwise it sleeps for the computed
    backoff interval and retries until either:

    - The predicate returns truthy (returns ``True``).
    - The elapsed time exceeds ``timeout_s`` (raises ``TimeoutError``).

    Backoff schedule:
        - Starts at ``initial_interval_s`` (default 1 s).
        - Multiplies the interval by ``backoff_factor`` (default 2×) after
          each attempt.
        - Caps the interval at ``max_interval_s`` (default 30 s).
        - No fixed sleeps — only the computed backoff intervals are used.

    Parameters
    ----------
    predicate : Callable[[], bool]
        A zero-argument callable that returns truthy when the desired
        condition is met.
    timeout_s : float
        Maximum wall-clock seconds to poll. Defaults to 300 s.
        Must not exceed ``MAX_CONFIGURABLE_TIMEOUT_S`` (900 s).
    initial_interval_s : float
        Initial sleep interval in seconds before the second attempt.
    backoff_factor : float
        Multiplicative factor applied to the interval after each attempt.
    max_interval_s : float
        Upper bound on the computed sleep interval.
    description : str
        Human-readable name for the predicate; included in the timeout
        error message so failures are diagnosable.

    Returns
    -------
    bool
        ``True`` when the predicate becomes truthy.

    Raises
    ------
    TimeoutError
        If the predicate does not become truthy within ``timeout_s``.
    ValueError
        If ``timeout_s`` exceeds ``MAX_CONFIGURABLE_TIMEOUT_S``.
    """
    if timeout_s > MAX_CONFIGURABLE_TIMEOUT_S:
        raise ValueError(
            f"timeout_s ({timeout_s}) exceeds the maximum configurable "
            f"timeout of {MAX_CONFIGURABLE_TIMEOUT_S} seconds"
        )

    start = time.time()
    interval = initial_interval_s
    attempts = 0

    while True:
        attempts += 1

        # Evaluate the predicate — stop on first truthy result (Req 8.3)
        if predicate():
            return True

        elapsed = time.time() - start

        # Check if we have exceeded the timeout budget
        if elapsed >= timeout_s:
            raise TimeoutError(
                f"Predicate '{description}' did not become true within "
                f"{timeout_s:.1f}s ({attempts} attempts, elapsed {elapsed:.1f}s)"
            )

        # Compute remaining time budget; if the next sleep would exceed
        # the timeout, sleep only for the remaining time (then do one
        # final check).
        remaining = timeout_s - elapsed
        sleep_duration = min(interval, remaining, max_interval_s)

        # Sleep for the computed backoff interval — no fixed sleeps (Req 8.2)
        time.sleep(sleep_duration)

        # Advance the backoff interval (capped at max_interval_s)
        interval = min(interval * backoff_factor, max_interval_s)
