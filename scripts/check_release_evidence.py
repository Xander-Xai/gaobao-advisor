#!/usr/bin/env python3
"""Fail the release-evidence gate while compliance review is outstanding.

This command never attempts to satisfy a compliance requirement. It reads
``config/compliance_attestation.yaml`` and reports whether a human reviewer has
approved each item a public release depends on. While any item is ``blocked``,
``draft`` or missing a reviewer, the command exits non-zero and states exactly
what is missing.

Skipping this command, deleting the attestation file, or setting an item to
``approved`` without an actual review would produce a false green. The command
treats a missing file as blocked for the same reason.

Examples
--------
    python scripts/check_release_evidence.py
    python scripts/check_release_evidence.py --format json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.toml_version import read_project_version  # noqa: E402

DEFAULT_ATTESTATION = Path("config/compliance_attestation.yaml")
APPROVED = "approved"
REQUIRED_ITEMS = (
    "data_rights",
    "privacy_disclosure",
    "public_redistribution",
    "third_party_notices",
)


class AttestationError(RuntimeError):
    """Raised when the attestation file cannot be parsed."""


def _parse_scalar(raw: str):
    value = raw.strip()
    if value in ("null", "~", ""):
        return None
    if value in ("true", "false"):
        return value == "true"
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    return value


def load_attestation(path: Path) -> dict:
    """Parse the two-level YAML subset the attestation file uses.

    A tiny parser keeps this gate dependency-free (the project deliberately does
    not depend on PyYAML). It understands top-level scalars, one nested mapping
    (``items``) and one mapping of folded strings (``reasons``).
    """
    path = Path(path)
    if not path.is_file():
        raise AttestationError(f"attestation file is missing: {path}")

    data: dict = {"items": {}, "reasons": {}}
    section: str | None = None
    pending_key: str | None = None
    pending_indent = 0

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        stripped = line.strip()

        if stripped in ("items:", "reasons:"):
            section = stripped[:-1]
            pending_key = None
            continue

        if indent == 0:
            section = None
            pending_key = None
            key, _, value = stripped.partition(":")
            data[key.strip()] = _parse_scalar(value)
            continue

        if section is None:
            continue

        if pending_key is not None and indent > pending_indent:
            data[section][pending_key] = f"{data[section][pending_key]} {stripped}".strip()
            continue

        if ":" in stripped:
            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip()
            if value in (">-", ">", "|", "|-"):
                pending_key = key
                pending_indent = indent
                data[section][key] = ""
            else:
                pending_key = None
                data[section][key] = _parse_scalar(value)

    return data


def _business_version(root: Path) -> str:
    return read_project_version(root) or "unknown"


def evaluate(attestation: dict, root: Path = Path(".")) -> dict:
    """Return the gate status without reading or writing anything else."""
    items: dict = attestation.get("items", {})
    reasons: dict = attestation.get("reasons", {})
    reviewer = attestation.get("reviewer")
    reviewed_at = attestation.get("reviewed_at")

    blockers: list[dict] = []
    for name in REQUIRED_ITEMS:
        status = items.get(name, "missing")
        if status != APPROVED:
            blockers.append(
                {
                    "item": name,
                    "status": status,
                    "reason": reasons.get(name, "no reason recorded"),
                }
            )

    if not reviewer:
        blockers.append({"item": "reviewer", "status": "missing", "reason": "no human reviewer recorded"})
    if not reviewed_at:
        blockers.append({"item": "reviewed_at", "status": "missing", "reason": "no review date recorded"})

    return {
        "status": "approved" if not blockers else "blocked",
        "project_version": _business_version(root),
        "reviewer": reviewer,
        "reviewed_at": reviewed_at,
        "items": {name: items.get(name, "missing") for name in REQUIRED_ITEMS},
        "blockers": blockers,
    }


def render(result: dict) -> str:
    lines = [
        "=" * 72,
        f"  RELEASE EVIDENCE GATE — {result['status'].upper()}",
        "=" * 72,
        f"\nproject version : {result['project_version']}",
        f"reviewer        : {result['reviewer'] or '(none recorded)'}",
        f"reviewed at     : {result['reviewed_at'] or '(none recorded)'}",
        "\n-- attestation items " + "-" * 50,
    ]
    for name, status in result["items"].items():
        lines.append(f"   {name:<24} {status}")

    if result["blockers"]:
        lines.append("\n-- this gate is BLOCKED by " + "-" * 44)
        for blocker in result["blockers"]:
            lines.append(f"   [{blocker['status']}] {blocker['item']}")
            lines.append(f"        {blocker['reason']}")
        lines.append(
            "\nPublic release stays blocked until a human with the authority to do so\n"
            "reviews each item and records the decision in config/compliance_attestation.yaml.\n"
            "Engineering and demo readiness are reported separately and are not affected."
        )
    else:
        lines.append("\nAll attestation items are approved by a recorded reviewer.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--attestation", type=Path, default=DEFAULT_ATTESTATION)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    try:
        attestation = load_attestation(args.attestation)
    except AttestationError as exc:
        print(f"BLOCKED {exc}", file=sys.stderr)
        print(
            "A missing attestation is treated as blocked, not as approval.",
            file=sys.stderr,
        )
        return 2

    result = evaluate(attestation, args.root)
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(render(result))

    return 0 if result["status"] == APPROVED else 1


if __name__ == "__main__":
    raise SystemExit(main())
