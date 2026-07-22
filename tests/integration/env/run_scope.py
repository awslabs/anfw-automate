"""RunScope — per-run isolation via Run_Id naming.

Provides the RunScope dataclass and Run_Id computation for the ephemeral
integration tier. Each test run gets a unique Run_Id of the form
``int-<shortsha>-<epoch>`` that is embedded in S3 config object keys and
generated rule-group names to isolate runs within shared stable infrastructure.

Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8
"""

from __future__ import annotations

import re
import subprocess
import time
from dataclasses import dataclass, field


class RunIdError(Exception):
    """Raised when a Run_Id cannot be computed (e.g. git SHA unavailable)."""


# Regex for valid Run_Id and derived names: lowercase alphanumeric + hyphens only.
_VALID_NAME_RE = re.compile(r"^[a-z0-9-]+$")

# AWS Network Firewall naming limit.
_MAX_NAME_LENGTH = 128

# Module-level collision tracker: maps (shortsha, epoch) -> count of ids issued.
_collision_counter: dict[tuple[str, int], int] = {}


def _get_git_shortsha() -> str:
    """Retrieve the 8-char lowercase hex commit SHA via git.

    Raises:
        RunIdError: If git is not available or HEAD cannot be resolved.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short=8", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise RunIdError(
            f"Cannot compute Run_Id: git SHA unavailable ({exc})"
        ) from exc

    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise RunIdError(
            f"Cannot compute Run_Id: git rev-parse failed — {stderr}"
        )

    shortsha = result.stdout.strip().lower()
    if not re.fullmatch(r"[0-9a-f]{8}", shortsha):
        raise RunIdError(
            f"Cannot compute Run_Id: unexpected SHA format '{shortsha}'"
        )
    return shortsha


def _compute_run_id(shortsha: str, epoch: int) -> str:
    """Compose the Run_Id with collision disambiguation.

    Format: int-<shortsha>-<epoch>[-<disambiguator>]

    If the same (shortsha, epoch) pair is seen more than once, a numeric
    disambiguator is appended (-1, -2, ...) to guarantee uniqueness while
    respecting the 128-char naming limit.
    """
    key = (shortsha, epoch)
    count = _collision_counter.get(key, 0)
    _collision_counter[key] = count + 1

    if count == 0:
        run_id = f"int-{shortsha}-{epoch}"
    else:
        run_id = f"int-{shortsha}-{epoch}-{count}"

    # Validate format and length.
    if len(run_id) > _MAX_NAME_LENGTH:
        raise RunIdError(
            f"Run_Id exceeds {_MAX_NAME_LENGTH} chars: '{run_id}'"
        )
    if not _VALID_NAME_RE.fullmatch(run_id):
        raise RunIdError(
            f"Run_Id contains invalid characters: '{run_id}'"
        )
    return run_id


@dataclass
class RunScope:
    """Tracks the per-run ephemeral artifacts created by an integration run.

    Attributes:
        run_id: The unique run identifier (int-<shortsha>-<epoch>).
        config_keys: S3 object keys this run created.
        rule_group_names: Network Firewall rule group names this run created.
    """

    run_id: str
    config_keys: list[str] = field(default_factory=list)
    rule_group_names: list[str] = field(default_factory=list)

    @classmethod
    def create(cls) -> "RunScope":
        """Compute a new Run_Id and return a fresh RunScope.

        - Gets shortsha via ``git rev-parse --short=8 HEAD``
        - Gets epoch seconds via ``time.time()``
        - Format: ``int-{shortsha}-{epoch}``
        - Aborts with RunIdError if git SHA is unavailable
        - Validates: ≤128 chars, alphanumeric + hyphens only
        - Appends numeric disambiguator on collision (same SHA + same epoch second)

        Raises:
            RunIdError: If the SHA cannot be obtained or the resulting name
                is invalid.
        """
        shortsha = _get_git_shortsha()
        epoch = int(time.time())
        run_id = _compute_run_id(shortsha, epoch)
        return cls(run_id=run_id)

    def s3_key(self, region: str) -> str:
        """Generate an S3 config key embedding the run_id.

        Format: ``{run_id}/{region}-config.yaml``

        The key is recorded in ``config_keys`` for later cleanup by the
        MutationCleaner.
        """
        key = f"{self.run_id}/{region}-config.yaml"
        self.config_keys.append(key)
        return key

    def rule_group_name(self, prefix: str) -> str:
        """Generate a rule group name embedding the run_id, ≤128 chars.

        Format: ``{prefix}-{run_id}``

        If the raw concatenation would exceed 128 chars, the prefix is
        truncated to fit. The generated name is recorded in
        ``rule_group_names`` for later cleanup.

        Raises:
            RunIdError: If even the run_id alone exceeds 128 chars (should
                never happen given the format, but guards the invariant).
        """
        # Reserve space for the separator.
        max_prefix_len = _MAX_NAME_LENGTH - len(self.run_id) - 1  # 1 for '-'
        if max_prefix_len < 0:
            raise RunIdError(
                f"Run_Id alone exceeds naming limit: '{self.run_id}'"
            )

        # Truncate prefix if needed.
        truncated_prefix = prefix[:max_prefix_len]

        name = f"{truncated_prefix}-{self.run_id}"

        # Validate the generated name.
        if not _VALID_NAME_RE.fullmatch(name):
            # Sanitize: replace invalid chars with hyphens, collapse multiples.
            name = re.sub(r"[^a-z0-9-]", "-", name.lower())
            name = re.sub(r"-{2,}", "-", name).strip("-")

        # Final length check (should always pass after truncation).
        if len(name) > _MAX_NAME_LENGTH:
            name = name[:_MAX_NAME_LENGTH]

        self.rule_group_names.append(name)
        return name


def reset_collision_counter() -> None:
    """Reset the module-level collision counter (for testing)."""
    _collision_counter.clear()
