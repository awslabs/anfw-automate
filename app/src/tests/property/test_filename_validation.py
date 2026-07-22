"""Property test: validate_file_name(f) returns True iff f matches <region>-config.(yaml|yml).

**Validates: Requirements 4.5**
"""

import re
import string

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from tests.property.strategies import region

from RuleCollect.event_handler import EventHandler

# The reference regex matching what validate_file_name should accept:
# An AWS region followed by -config.yaml or -config.yml
_REGION_PATTERN = r"(us(-gov)?|ap|ca|cn|eu|sa)-(central|(north|south)?(east|west)?)-\d"
_VALID_FILENAME_RE = re.compile(
    rf"^{_REGION_PATTERN}-config\.(yaml|yml)$"
)


# Strategy for generating valid filenames: region + "-config." + extension
_valid_filename = st.builds(
    lambda r, ext: f"{r}-config.{ext}",
    region,
    st.sampled_from(["yaml", "yml"]),
)

# Strategy for generating arbitrary text that is unlikely to be a valid filename
_arbitrary_text = st.text(
    alphabet=string.ascii_letters + string.digits + "-_./!@# ",
    min_size=0,
    max_size=60,
)


@pytest.mark.property
@settings(max_examples=100)
@given(filename=_valid_filename)
def test_valid_filenames_accepted(filename):
    """Property 5a: validate_file_name returns True for valid <region>-config.(yaml|yml) filenames.

    **Validates: Requirements 4.5**
    """
    handler = EventHandler()
    assert handler.validate_file_name(filename) is True, (
        f"Expected validate_file_name({filename!r}) to return True"
    )


@pytest.mark.property
@settings(max_examples=100)
@given(text=_arbitrary_text)
def test_invalid_filenames_rejected(text):
    """Property 5b: validate_file_name returns False for strings that don't match the pattern.

    **Validates: Requirements 4.5**
    """
    # Only test strings that do NOT match the valid filename pattern
    assume(not _VALID_FILENAME_RE.search(text))

    handler = EventHandler()
    assert handler.validate_file_name(text) is False, (
        f"Expected validate_file_name({text!r}) to return False"
    )


@pytest.mark.property
@settings(max_examples=100)
@given(filename=st.one_of(_valid_filename, _arbitrary_text))
def test_filename_validation_equivalence(filename):
    """Property 5: validate_file_name(f) == bool(re.search(region-config pattern, f))

    The equivalence property: validate_file_name agrees with the reference regex.

    **Validates: Requirements 4.5**
    """
    handler = EventHandler()
    # The reference regex uses search (matching the implementation behaviour)
    expected = bool(re.search(
        rf"((us(-gov)?|ap|ca|cn|eu|sa)-(central|(north|south)?(east|west)?)-\d)-config\.(yaml|yml)",
        filename,
    ))
    actual = handler.validate_file_name(filename)
    assert actual == expected, (
        f"validate_file_name({filename!r}) returned {actual}, expected {expected}"
    )
