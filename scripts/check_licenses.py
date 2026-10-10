#!/usr/bin/env python3
"""Fail a release when dependency licenses need legal review."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REVIEW_REQUIRED = re.compile(
    r"(?:\bA?GPL(?:-|\b)|GNU (?:Affero )?General Public License|"
    r"GNU Lesser General Public License|\bLGPL(?:-|\b)|\bSSPL(?:-|\b)|"
    r"Server Side Public License|Business Source License|\bBUSL(?:-|\b)|"
    r"Commons Clause|Proprietary|UNLICENSED|UNKNOWN)",
    re.IGNORECASE,
)


def _license_issue(name: str, version: str, license_name: str | None, ecosystem: str) -> str | None:
    normalized = (license_name or "UNKNOWN").strip() or "UNKNOWN"
    if REVIEW_REQUIRED.search(normalized):
        return f"{ecosystem} dependency {name}@{version} requires license review: {normalized}"
    return None


def audit_npm_lock(lock_path: Path) -> list[str]:
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    issues: list[str] = []
    for package_path, package in lock.get("packages", {}).items():
        if not package_path or package.get("dev"):
            continue
        name = package_path.removeprefix("node_modules/")
        issue = _license_issue(name, package.get("version", "unknown"), package.get("license"), "npm")
        if issue:
            issues.append(issue)
    return issues


def audit_python_report(report: list[dict[str, str]]) -> list[str]:
    issues: list[str] = []
    for package in report:
        name = package.get("Name") or package.get("name") or "unknown"
        version = package.get("Version") or package.get("version") or "unknown"
        license_name = package.get("License") or package.get("license")
        issue = _license_issue(name, version, license_name, "Python")
        if issue:
            issues.append(issue)
    return issues


def load_python_licenses(python: str) -> list[dict[str, str]]:
    result = subprocess.run(
        ["pip-licenses", "--python", python, "--from=mixed", "--format=json"],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--npm-lock", type=Path, default=Path("frontend/package-lock.json"))
    parser.add_argument("--python", default=sys.executable, help="Python interpreter inspected by pip-licenses")
    parser.add_argument("--python-report", type=Path, help="reuse a pip-licenses JSON report")
    parser.add_argument("--skip-python", action="store_true")
    args = parser.parse_args(argv)

    issues = audit_npm_lock(args.npm_lock)
    if not args.skip_python:
        try:
            report = (
                json.loads(args.python_report.read_text(encoding="utf-8"))
                if args.python_report
                else load_python_licenses(args.python)
            )
            issues.extend(audit_python_report(report))
        except (FileNotFoundError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
            print(f"FAIL unable to inventory Python licenses: {exc}", file=sys.stderr)
            return 1

    if issues:
        for issue in issues:
            print(f"FAIL {issue}", file=sys.stderr)
        return 1
    print("PASS dependency licenses contain no prohibited or unreviewed identifiers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
