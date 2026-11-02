"""Property test: validation raises FormatError for TLD-only domains.

**Validates: Requirements 4.4**
"""

import pytest
from hypothesis import given, settings, HealthCheck

from tests.property.strategies import account_id, vpc_id, tld_only_domain, predefined_protocol

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
    tld_domain=tld_only_domain,
    protocol=predefined_protocol,
)
def test_tld_only_domain_rejection(account, vpc, tld_domain, protocol, set_rule_order):
    """Property 4: validation raises FormatError for TLD-only domains.

    A TLD-only domain is a leading dot followed by two or more alphabetic
    characters with no further labels (e.g., ".com", ".net", ".org").
    The _is_valid_domain check inside add_rule_entry rejects these inputs.

    **Validates: Requirements 4.4**
    """
    entry = ConfigEntry(
        vpc=vpc,
        account=account,
        region="eu-west-1",
        version="v",
    )

    with pytest.raises(ConfigEntry.FormatError):
        entry.add_rule_entry(rule_key=protocol, rule=tld_domain)
