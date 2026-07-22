"""Property test: identical inputs yield byte-identical rule names.

**Validates: Requirements 4.6**
"""

import os

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
def test_rule_name_determinism(account, vpc, protocol, dom):
    """Property 6: Rule-name determinism — identical inputs yield byte-identical
    rule names, independent of the random `sid`.

    Two separate ConfigEntry instances built from the same inputs must produce
    the exact same rule name keys. This proves the name depends on the hashed
    inputs, not on the random sid value embedded in the rule body.

    **Validates: Requirements 4.6**
    """
    entry_a = ConfigEntry(
        vpc=vpc,
        account=account,
        region="eu-west-1",
        version="v",
    )
    entry_a.add_rule_entry(rule_key=protocol, rule=dom)

    entry_b = ConfigEntry(
        vpc=vpc,
        account=account,
        region="eu-west-1",
        version="v",
    )
    entry_b.add_rule_entry(rule_key=protocol, rule=dom)

    assert set(entry_a.rules.keys()) == set(entry_b.rules.keys()), (
        f"Rule names differ for identical inputs: "
        f"{sorted(entry_a.rules.keys())} vs {sorted(entry_b.rules.keys())}"
    )
