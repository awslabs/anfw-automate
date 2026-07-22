"""Reusable Hypothesis strategies for property-based testing.

Provides focused, composable strategies for generating valid inputs to the
anfw-automate rule engine. Uses only `hypothesis.strategies` — no external
strategy libraries (hypothesis_regex, hypothesis.extra.pandas, etc.).

These strategies mirror the domain constraints found in:
- app/src/lib/rule_config.py (ConfigEntry, RESERVED_META_KEYWORDS)
- app/src/data/protocols.yaml (PredfinedRuleProtocols)
"""

import string

from hypothesis import strategies as st

from lib.rule_config import RESERVED_META_KEYWORDS

# ---------------------------------------------------------------------------
# Account ID: exactly 12 decimal digits (AWS account format)
# ---------------------------------------------------------------------------
account_id = st.text(alphabet=string.digits, min_size=12, max_size=12)

# ---------------------------------------------------------------------------
# VPC ID: lowercase alphanumeric, 8-17 chars.
# Optionally prefixed with "vpc-" (ConfigEntry strips the prefix internally).
# ---------------------------------------------------------------------------
_vpc_body = st.text(
    alphabet=string.ascii_lowercase + string.digits,
    min_size=8,
    max_size=17,
)
vpc_id = st.one_of(
    _vpc_body,
    _vpc_body.map(lambda v: f"vpc-{v}"),
)

# ---------------------------------------------------------------------------
# Region: sampled from the supported AWS regions used in testing
# ---------------------------------------------------------------------------
region = st.sampled_from(
    ["eu-west-1", "eu-central-1", "us-east-1", "us-west-2", "ap-southeast-1"]
)

# ---------------------------------------------------------------------------
# Domain: valid domains that are NOT TLD-only.
# Must not match the pattern ^\.[a-zA-Z]{2,}$ (which is TLD-only).
# Examples: "example.com", ".subdomain.example.io"
# ---------------------------------------------------------------------------
_tlds = ["com", "net", "io", "org", "test", "dev"]
_label = st.text(
    alphabet=string.ascii_lowercase + string.digits,
    min_size=1,
    max_size=20,
)

# Plain domain: label.tld (e.g., "example.com")
_plain_domain = st.builds(
    lambda label, tld: f"{label}.{tld}",
    _label,
    st.sampled_from(_tlds),
)

# Dotprefix domain: .label.tld (e.g., ".subdomain.example.io")
_dotprefix_domain = st.builds(
    lambda label, tld: f".{label}.{tld}",
    _label,
    st.sampled_from(_tlds),
)

domain = st.one_of(_plain_domain, _dotprefix_domain)

# ---------------------------------------------------------------------------
# Predefined protocol: one of the PredfinedRuleProtocols keys from protocols.yaml
# ---------------------------------------------------------------------------
predefined_protocol = st.sampled_from(["http", "https", "tls"])

# ---------------------------------------------------------------------------
# TLD-only domain: domains that ARE TLD-only (for negative testing).
# Matches ^\.[a-zA-Z]{2,}$ — e.g., ".com", ".net", ".org"
# ---------------------------------------------------------------------------
tld_only_domain = st.builds(
    lambda tld: f".{tld}",
    st.text(alphabet=string.ascii_letters, min_size=2, max_size=10),
)

# ---------------------------------------------------------------------------
# Reserved keyword: one of the RESERVED_META_KEYWORDS from rule_config.py
# (msg, sid, rev, gid, classtype, reference, priority, metadata, target)
# ---------------------------------------------------------------------------
reserved_keyword = st.sampled_from(RESERVED_META_KEYWORDS)
