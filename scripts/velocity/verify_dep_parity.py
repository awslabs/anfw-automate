#!/usr/bin/env python3
"""Verify dependency parity between uv.lock and a reference snapshot.

This script parses a uv.lock file and compares the resolved package versions
against a reference JSON file (typically a snapshot captured from the pre-migration
poetry.lock). On mismatch it reports the dependency name with both versions and
exits non-zero.

Usage:
    python verify_dep_parity.py \
        --lockfile app/src/uv.lock \
        --reference scripts/velocity/dep_reference.json

    # Generate a new reference snapshot from uv.lock:
    python verify_dep_parity.py \
        --lockfile app/src/uv.lock \
        --generate-reference scripts/velocity/dep_reference.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def parse_uv_lock(lockfile: Path) -> dict[str, str]:
    """Parse a uv.lock file and return a mapping of package name -> version.

    The uv.lock format is TOML-like with repeated [[package]] sections.
    Each section has a 'name' and 'version' field. We skip the root project
    entry (source = { editable = "." }).
    """
    packages: dict[str, str] = {}
    content = lockfile.read_text(encoding="utf-8")

    # Split on [[package]] markers
    sections = re.split(r"^\[\[package\]\]\s*$", content, flags=re.MULTILINE)

    for section in sections[1:]:  # skip preamble before first [[package]]
        name = None
        version = None
        is_editable = False

        for line in section.splitlines():
            line = line.strip()
            if not line or line.startswith("[") or line.startswith("#"):
                # Stop at nested tables or blank lines after we have what we need
                if name and version:
                    break
                if line.startswith("["):
                    break
                continue

            # Match name = "..."
            name_match = re.match(r'^name\s*=\s*"([^"]+)"', line)
            if name_match:
                name = name_match.group(1)
                continue

            # Match version = "..."
            version_match = re.match(r'^version\s*=\s*"([^"]+)"', line)
            if version_match:
                version = version_match.group(1)
                continue

            # Detect editable (root project) entries
            if "editable" in line:
                is_editable = True

        if name and version and not is_editable:
            packages[name] = version

    return packages


def load_reference(reference_path: Path) -> dict[str, str]:
    """Load a reference JSON file mapping package names to versions."""
    data = json.loads(reference_path.read_text(encoding="utf-8"))
    return data.get("packages", data)


def compare(
    uv_packages: dict[str, str], reference: dict[str, str]
) -> list[dict[str, str]]:
    """Compare uv.lock packages against the reference.

    Returns a list of mismatch records with keys: name, uv_version, ref_version.
    """
    mismatches: list[dict[str, str]] = []
    all_names = sorted(set(reference.keys()) | set(uv_packages.keys()))

    for name in all_names:
        ref_ver = reference.get(name)
        uv_ver = uv_packages.get(name)

        if ref_ver is None:
            # New dependency not in reference — report as addition
            mismatches.append(
                {"name": name, "uv_version": uv_ver or "N/A", "ref_version": "MISSING"}
            )
        elif uv_ver is None:
            # Dependency removed from uv.lock
            mismatches.append(
                {"name": name, "uv_version": "MISSING", "ref_version": ref_ver}
            )
        elif uv_ver != ref_ver:
            mismatches.append(
                {"name": name, "uv_version": uv_ver, "ref_version": ref_ver}
            )

    return mismatches


def generate_reference(uv_packages: dict[str, str], output_path: Path) -> None:
    """Write a reference JSON snapshot from the parsed uv.lock packages."""
    data = {
        "_comment": (
            "Reference snapshot of resolved dependency versions from uv.lock. "
            "Used by verify_dep_parity.py to assert migration parity."
        ),
        "packages": dict(sorted(uv_packages.items())),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"✓ Reference snapshot written to {output_path} ({len(uv_packages)} packages)")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify dependency parity between uv.lock and a reference snapshot."
    )
    parser.add_argument(
        "--lockfile",
        type=Path,
        default=Path("app/src/uv.lock"),
        help="Path to the uv.lock file (default: app/src/uv.lock)",
    )
    parser.add_argument(
        "--reference",
        type=Path,
        default=Path("scripts/velocity/dep_reference.json"),
        help="Path to the reference JSON file (default: scripts/velocity/dep_reference.json)",
    )
    parser.add_argument(
        "--generate-reference",
        type=Path,
        metavar="OUTPUT",
        help="Generate a reference JSON from uv.lock instead of comparing",
    )

    args = parser.parse_args()

    # Parse uv.lock
    if not args.lockfile.exists():
        print(f"✗ Lockfile not found: {args.lockfile}", file=sys.stderr)
        return 1

    uv_packages = parse_uv_lock(args.lockfile)

    if not uv_packages:
        print(f"✗ No packages found in {args.lockfile}", file=sys.stderr)
        return 1

    print(f"Parsed {len(uv_packages)} packages from {args.lockfile}")

    # Generate mode
    if args.generate_reference:
        generate_reference(uv_packages, args.generate_reference)
        return 0

    # Compare mode
    if not args.reference.exists():
        print(f"✗ Reference file not found: {args.reference}", file=sys.stderr)
        print("  Run with --generate-reference to create one.", file=sys.stderr)
        return 1

    reference = load_reference(args.reference)
    mismatches = compare(uv_packages, reference)

    if mismatches:
        print(f"\n✗ DEPENDENCY PARITY FAILED — {len(mismatches)} mismatch(es):\n")
        print(f"  {'Package':<30} {'uv.lock':<20} {'Reference':<20}")
        print(f"  {'-' * 30} {'-' * 20} {'-' * 20}")
        for m in mismatches:
            print(f"  {m['name']:<30} {m['uv_version']:<20} {m['ref_version']:<20}")
        print()
        return 1

    print(f"✓ Dependency parity verified: all {len(uv_packages)} packages match reference.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
