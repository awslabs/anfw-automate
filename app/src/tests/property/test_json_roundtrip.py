"""Property test: ConfigEntry.get_json() produces JSON with the expected keys and values.

**Validates: Requirements 4.2**
"""

import json
import os

import pytest
from hypothesis import given, settings, HealthCheck

from tests.property.strategies import account_id, region, vpc_id

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
    reg=region,
)
def test_get_json_round_trip(account, vpc, reg, set_rule_order):
    """Property 2: get_json() produces JSON with keys {VPC, Account, Region, CIDR, Rules}
    matching constructor inputs.

    **Validates: Requirements 4.2**
    """
    entry = ConfigEntry(vpc=vpc, account=account, region=reg, version="v")
    raw = entry.get_json()
    parsed = json.loads(raw)

    # Assert the expected keys are present
    assert set(parsed.keys()) == {"VPC", "Account", "Region", "CIDR", "Rules"}

    # Assert values match constructor inputs
    assert parsed["VPC"] == vpc.replace("vpc-", "")
    assert parsed["Account"] == account
    assert parsed["Region"] == reg

    # CIDR defaults to empty string (ip_set_space not configured)
    assert parsed["CIDR"] == ""

    # Rules defaults to empty dict (no rules added)
    assert parsed["Rules"] == {}
