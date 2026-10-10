#!/usr/bin/env python3
"""Verify requirements.lock satisfies every constraint in requirements.txt.

`requirements.lock` is generated from `requirements.txt`. If the two drift apart
the audited lock no longer describes what the manifest asks for — the exact bug
that let a `<0.9.0` cap pull the lock back onto a vulnerable langsmith.

The check is intentionally conservative and dependency-free: it parses the
simple `name<op>version` grammar both files use.

Examples
--------
    python scripts/check_lock_consistency.py
    python scripts/check_lock_consistency.py --manifest requirements.txt --lock requirements.lock
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

NAME_RE = re.compile(r"^([A-Za-z0-9_.\-]+)\s*((?:[<>=!~]=?[^,;]*)(?:\s*,\s*[<>=!~]=?[^,;]*)*)")
PIN_RE = re.compile(r"^([A-Za-z0-9_.\-]+)==(\S+)")
OPERATOR_RE = re.compile(r"^(>=|<=|==|!=|>|<|~=)\s*(.+)$")

# Constraints that only apply on some platforms or Python versions are out of
# scope: the lock is compiled for one target.
ENVIRONMENT_MARKERS = (";", "sys_platform", "platform_", "python_version", "extra ==")


def _version_tuple(raw: str) -> tuple[int, int, int]:
    numbers = re.findall(r"\d+", raw)
    padded = (numbers + ["0", "0", "0"])[:3]
    return tuple(int(part) for part in padded)  # type: ignore[return-value]


def _normalise(name: str) -> str:
    return name.strip().lower().replace("_", "-")


def load_lock(path: Path) -> dict[str, str]:
    """Return ``{normalised name: pinned version}`` from a pip-compile lock."""
    pinned: dict[str, str] = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        match = PIN_RE.match(line.strip())
        if match:
            pinned[_normalise(match.group(1))] = match.group(2)
    return pinned


def load_manifest(path: Path) -> list[tuple[str, list[str]]]:
    """Return ``[(normalised name, [constraint, ...])]`` from a requirements file."""
    requirements: list[tuple[str, list[str]]] = []
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or any(marker in line for marker in ENVIRONMENT_MARKERS):
            continue
        match = NAME_RE.match(line)
        if not match:
            continue
        name = _normalise(match.group(1))
        spec = match.group(2) or ""
        constraints = [part.strip() for part in re.split(r",(?![^[]*\])", spec) if part.strip()]
        requirements.append((name, constraints))
    return requirements


def compare(pinned: dict[str, str], requirements: list[tuple[str, list[str]]]) -> list[str]:
    """Return one message per unmet or missing constraint."""
    problems: list[str] = []
    for name, constraints in requirements:
        actual = pinned.get(name)
        if actual is None:
            if constraints:
                problems.append(f"{name}: required by the manifest but not pinned in the lock")
            continue
        for constraint in constraints:
            operator_match = OPERATOR_RE.match(constraint)
            if not operator_match:
                continue
            operator, target = operator_match.group(1), operator_match.group(2).strip()
            if not re.match(r"^\d", target):
                continue
            left, right = _version_tuple(actual), _version_tuple(target)
            unmet = (
                (operator == ">=" and left < right)
                or (operator == ">" and left <= right)
                or (operator == "<=" and left > right)
                or (operator == "<" and left >= right)
                or (operator == "==" and actual != target)
                or (operator == "!=" and actual == target)
            )
            if unmet:
                problems.append(
                    f"{name}: lock pins {actual}, which violates the manifest constraint '{operator}{target}'"
                )
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manifest", type=Path, default=Path("requirements.txt"))
    parser.add_argument("--lock", type=Path, default=Path("requirements.lock"))
    args = parser.parse_args(argv)

    for path in (args.manifest, args.lock):
        if not path.is_file():
            print(f"FAIL missing file: {path}", file=sys.stderr)
            return 2

    pinned = load_lock(args.lock)
    requirements = load_manifest(args.manifest)
    problems = compare(pinned, requirements)

    if problems:
        for problem in problems:
            print(f"FAIL {problem}", file=sys.stderr)
        print(
            f"\n{len(problems)} constraint(s) unsatisfied. Regenerate the lock with "
            f"`uv pip compile {args.manifest} -o {args.lock}` and re-run pip-audit.",
            file=sys.stderr,
        )
        return 1

    print(f"PASS {args.lock} satisfies all {len(requirements)} manifest requirement(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
