"""Property test: generated predefined rule names match the expected format.

**Validates: Requirements 4.1, 4.7, 4.8**
"""

import os
import re

import pytest
from hypothesis import given, settings, HealthCheck

from tests.property.strategies import account_id, domain, predefined_protocol, vpc_id

from lib.rule_config import ConfigEntry


os.environ.setdefault("RULE_ORDER", "STRICT_ORDER")


@pytest.mark.property
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    account=account_id,
    vpc=vpc_id,
    protocol=predefined_protocol,
    dom=domain,
)
def test_predefined_rule_name_format(account, vpc, protocol, dom):
    """Property 1: Every generated predefined rule name matches
    ^{account}-{vpc_stripped}-[0-9a-f]{10}$

    **Validates: Requirements 4.1, 4.7, 4.8**
    """
    vpc_stripped = vpc.replace("vpc-", "")

    entry = ConfigEntry(
        vpc=vpc,
        account=account,
        region="eu-west-1",
        version="v",
    )
    entry.add_rule_entry(rule_key=protocol, rule=dom)

    pattern = rf"^{re.escape(account)}-{re.escape(vpc_stripped)}-[0-9a-f]{{10}}$"
    for key in entry.rules:
        assert re.fullmatch(pattern, key), (
            f"Rule name {key!r} does not match expected pattern {pattern!r}"
        )
