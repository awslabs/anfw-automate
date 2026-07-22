"""Integration test session fixtures.

Provides run-id, boto3 sessions, resolved IntEnv, serial-execution default,
and a finally-wrapped revert-on-failure fixture that always calls
MutationCleaner.

Requirements: 7.1, 10.1, 10.6
"""

from __future__ import annotations

import logging

import boto3
import pytest

from tests.integration.env.mutation_cleaner import MutationCleaner, RevertResult
from tests.integration.env.run_scope import RunScope
from tests.integration.env.stable import IntEnv, StableEnvResolver

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Serial execution marker — integration tests run serially by default (Req 10.6)
# ---------------------------------------------------------------------------


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Mark all integration test items for serial execution.

    By default, integration tests run one at a time against the shared stable
    firewall policy to avoid Network Firewall API rate-limit pressure and
    shared-policy contention.

    If pytest-xdist is installed, this applies the ``serial`` marker so xdist
    does not parallelize them. Without xdist, tests already run sequentially.
    """
    for item in items:
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.serial)


# ---------------------------------------------------------------------------
# Session-scoped fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def boto3_session() -> boto3.Session:
    """Provide a boto3.Session configured for the INT account.

    Uses the default credential chain (env vars, instance profile, or
    AWS config profile) which should resolve to the allowlisted INT account.
    """
    return boto3.Session()


@pytest.fixture(scope="session")
def int_env(boto3_session: boto3.Session) -> IntEnv:
    """Resolve the IntEnv from stable stacks via StableEnvResolver.

    Calls assert_is_int_account() before resolving to guarantee we are
    operating against the allowlisted INT account and never against production.

    The resolved IntEnv is immutable and shared across all integration tests
    in the session.
    """
    resolver = StableEnvResolver()
    resolver.assert_is_int_account()

    # Create a RunScope to get the run_id for resolution
    scope = RunScope.create()
    return resolver.resolve(run_id=scope.run_id)


@pytest.fixture(scope="session")
def run_scope() -> RunScope:
    """Create a fresh RunScope with a unique Run_Id for this session.

    The Run_Id follows the format ``int-<shortsha>-<epoch>`` and is used to
    isolate this run's ephemeral artifacts (S3 config keys and rule group
    names) within the shared stable infrastructure.

    Validates: Requirement 7.1
    """
    return RunScope.create()


@pytest.fixture(scope="session")
def mutation_cleaner(
    int_env: IntEnv,
    run_scope: RunScope,
    boto3_session: boto3.Session,
) -> MutationCleaner:
    """Create a MutationCleaner that captures baseline and always reverts.

    Lifecycle:
    1. Creates the MutationCleaner with the resolved IntEnv and boto3 session.
    2. Captures the firewall policy baseline BEFORE any test mutations.
    3. Yields the cleaner for tests to use (artifacts tracked via RunScope).
    4. In the finally block: ALWAYS calls revert(run_scope) regardless of
       test outcome (pass/fail/error) to restore baseline.

    Validates: Requirements 10.1, 10.6
    """
    cleaner = MutationCleaner(env=int_env, session=boto3_session)
    cleaner.capture_baseline()

    try:
        yield cleaner
    finally:
        logger.info(
            "mutation_cleaner teardown: reverting run '%s' mutations",
            run_scope.run_id,
        )
        result: RevertResult = cleaner.revert(run_scope)

        if result.mutations_reverted and result.baseline_restored:
            logger.info(
                "Revert complete for run '%s': mutations_reverted=%s, "
                "baseline_restored=%s",
                run_scope.run_id,
                result.mutations_reverted,
                result.baseline_restored,
            )
        else:
            logger.error(
                "Revert INCOMPLETE for run '%s': mutations_reverted=%s, "
                "baseline_restored=%s, failed_artifacts=%s",
                run_scope.run_id,
                result.mutations_reverted,
                result.baseline_restored,
                result.failed_artifacts,
            )
