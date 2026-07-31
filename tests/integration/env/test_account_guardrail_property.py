"""Property-based test for the account guardrail (Property 11).

**Property 11: Account guardrail** — The INT harness never operates against a
non-allowlisted (e.g. prod) account; it runs only against the fixed,
allowlisted INT account.

**Validates: Requirements 5.2, 5.5**

For all account identifiers that are NOT the allowlisted INT account,
assert_is_int_account raises AccountGuardError naming the rejected account.
"""

from __future__ import annotations

import string
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from tests.integration.env.stable import (
    AccountGuardError,
    StableEnvResolver,
)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Valid 12-digit AWS account ids
account_id_strategy = st.text(alphabet=string.digits, min_size=12, max_size=12)

# The fixed allowlisted account used in the rejection tests
ALLOWLISTED_ACCOUNT = "123456789012"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(account_id: str) -> Path:
    """Write a temporary config.toml and return its path."""
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False)
    f.write(f'[int_account]\naccount_id = "{account_id}"\n')
    f.close()
    return Path(f.name)


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


@pytest.mark.property
class TestAccountGuardrailProperty:
    """Property 11: Account guardrail — never operates on non-allowlisted accounts."""

    @given(caller_account=account_id_strategy)
    @settings(max_examples=200)
    def test_non_allowlisted_account_always_rejected(
        self, caller_account: str
    ) -> None:
        """For all accounts != allowlisted, guardrail raises and names the account.

        **Validates: Requirements 5.2, 5.7**
        """
        assume(caller_account != ALLOWLISTED_ACCOUNT)

        config_file = _make_config(ALLOWLISTED_ACCOUNT)

        with patch("tests.integration.env.stable.boto3.client") as mock_client:
            mock_sts = MagicMock()
            mock_sts.get_caller_identity.return_value = {"Account": caller_account}
            mock_client.return_value = mock_sts

            resolver = StableEnvResolver(config_path=config_file)

            with pytest.raises(AccountGuardError) as exc_info:
                resolver.assert_is_int_account()

            # The error MUST name the rejected account
            assert caller_account in str(exc_info.value)
            # The error MUST reference the allowlisted account
            assert ALLOWLISTED_ACCOUNT in str(exc_info.value)

    @given(allowlisted=account_id_strategy)
    @settings(max_examples=200)
    def test_allowlisted_account_always_passes(
        self, allowlisted: str
    ) -> None:
        """For all valid account ids, guardrail passes when caller == allowlisted.

        **Validates: Requirements 5.1, 5.5**
        """
        assume(len(allowlisted) == 12 and allowlisted.isdigit())
        # Exclude empty-like values that the loader would reject
        assume(allowlisted != "000000000000")

        config_file = _make_config(allowlisted)

        with patch("tests.integration.env.stable.boto3.client") as mock_client:
            mock_sts = MagicMock()
            mock_sts.get_caller_identity.return_value = {"Account": allowlisted}
            mock_client.return_value = mock_sts

            resolver = StableEnvResolver(config_path=config_file)
            # Should NOT raise — the caller IS the allowlisted account
            resolver.assert_is_int_account()
