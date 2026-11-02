"""Property test: add_rule_entry raises FormatError for reserved keywords.

**Validates: Requirements 4.3**
"""

import os

import pytest
from hypothesis import given, settings, HealthCheck

from tests.property.strategies import account_id, reserved_keyword, vpc_id

from lib.rule_config import ConfigEntry


@pytest.fixture(autouse=True)
def set_rule_order(monkeypatch):
    """Ensure RULE_ORDER is set so ConfigEntry initializes correctly."""
    monkeypatch.setenv("RULE_ORDER", "STRICT_ORDER")


@pytest.mark.property
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    account=account_id,
    vpc=vpc_id,
    keyword=reserved_keyword,
)
def test_reserved_keyword_rejection(account, vpc, keyword, set_rule_order):
    """Property 3: add_rule_entry raises FormatError when a custom rule
    contains a reserved Suricata meta-keyword in its rule options.

    **Validates: Requirements 4.3**
    """
    vpc_stripped = vpc.replace("vpc-", "")

    # Build a custom rule that passes the base regex but contains a reserved keyword
    custom_rule = (
        f'pass http $a{account}{vpc_stripped} any -> $EXTERNAL_NET any '
        f'(content:"example.com"; {keyword}:test;)'
    )

    entry = ConfigEntry(
        vpc=vpc,
        account=account,
        region="eu-west-1",
        version="v",
    )

    with pytest.raises(ConfigEntry.FormatError):
        entry.add_rule_entry(rule_key="custom", rule=custom_rule)
