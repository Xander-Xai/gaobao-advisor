#!/usr/bin/env python3
"""Validate the small public documentation surface used by a release."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.toml_version import read_project_version  # noqa: E402

PUBLIC_DOCS = (
    Path("README.md"),
    Path("frontend/README.md"),
    Path("CONTRIBUTING.md"),
    Path("SECURITY.md"),
    Path("PRIVACY.md"),
    Path("SUPPORT.md"),
    Path("DATA_LICENSE.md"),
    Path("DATA_SOURCES.md"),
    Path("THIRD_PARTY_NOTICES.md"),
    Path("docs/open-source-guide.md"),
    Path("docs/faq-troubleshooting.md"),
)

LINK_RE = re.compile(r"!?\[[^\]]*]\(([^)]+)\)")
VERSION_RE = re.compile(r"(?:当前版本|project version|release)\s*[:：]\s*v?(\d+\.\d+\.\d+)", re.IGNORECASE)
PLACEHOLDERS = (
    (re.compile(r"\byour[-_ ]org\b", re.IGNORECASE), "your-org"),
    (re.compile(r"\bexample\.com\b", re.IGNORECASE), "example.com"),
    (re.compile(r"\bTODO(?:\([^)]*\))?\b", re.IGNORECASE), "TODO"),
)


def _project_version(root: Path) -> str | None:
    return read_project_version(root)


def _link_target(root: Path, document: Path, raw_target: str) -> Path | None:
    target = raw_target.strip().split(maxsplit=1)[0].strip("<>")
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc or target.startswith(("#", "mailto:")):
        return None
    path = unquote(parsed.path)
    if not path:
        return None
    candidate = root / path.lstrip("/") if path.startswith("/") else document.parent / path
    try:
        return candidate.resolve().relative_to(root.resolve())
    except ValueError:
        return Path("..") / candidate.name


def check_public_docs(root: Path, documents: list[Path] | tuple[Path, ...] = PUBLIC_DOCS) -> list[str]:
    """Return actionable issues for public Markdown files without changing them."""
    issues: list[str] = []
    project_version = _project_version(root)

    for relative in documents:
        document = root / relative
        if not document.exists():
            issues.append(f"missing public document: {relative}")
            continue
        text = document.read_text(encoding="utf-8")
        for pattern, label in PLACEHOLDERS:
            if pattern.search(text):
                issues.append(f"placeholder {label!r} in {relative}")

        for match in LINK_RE.finditer(text):
            target = _link_target(root, document, match.group(1))
            if target is not None and (target.parts[:1] == ("..",) or not (root / target).exists()):
                issues.append(f"broken local link in {relative}: {match.group(1)}")

        if project_version:
            for documented_version in VERSION_RE.findall(text):
                if documented_version != project_version:
                    issues.append(
                        f"version drift in {relative}: documented {documented_version}, project {project_version}"
                    )

    return issues


def check_version_consistency(root: Path) -> list[str]:
    """Ensure runtime and distribution manifests advertise one project version."""
    expected = _project_version(root)
    if not expected:
        return ["missing project.version in pyproject.toml"]

    versions: dict[str, str | None] = {}
    server_init = root / "server/__init__.py"
    if server_init.exists():
        match = re.search(r'^__version__\s*=\s*["\']([^"\']+)', server_init.read_text(encoding="utf-8"), re.M)
        versions["server/__init__.py"] = match.group(1) if match else None

    frontend_package = root / "frontend/package.json"
    if frontend_package.exists():
        versions["frontend/package.json"] = json.loads(frontend_package.read_text(encoding="utf-8")).get("version")

    frontend_lock = root / "frontend/package-lock.json"
    if frontend_lock.exists():
        lock = json.loads(frontend_lock.read_text(encoding="utf-8"))
        versions["frontend/package-lock.json"] = lock.get("packages", {}).get("", {}).get("version")

    openapi_json = root / "openapi.json"
    if openapi_json.exists():
        versions["openapi.json"] = json.loads(openapi_json.read_text(encoding="utf-8")).get("info", {}).get("version")

    openapi_yaml = root / "openapi.yaml"
    if openapi_yaml.exists():
        match = re.search(r"^\s*version:\s*['\"]?([^'\"\s]+)", openapi_yaml.read_text(encoding="utf-8"), re.M)
        versions["openapi.yaml"] = match.group(1) if match else None

    issues = []
    for path, actual in versions.items():
        if actual != expected:
            issues.append(f"version drift in {path}: {actual or 'missing'}, project {expected}")
    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("paths", nargs="*", type=Path)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    issues = check_public_docs(root, args.paths or PUBLIC_DOCS)
    if not args.paths:
        issues.extend(check_version_consistency(root))
    if issues:
        for issue in issues:
            print(f"FAIL {issue}", file=sys.stderr)
        return 1
    print(f"PASS public documentation checks ({len(args.paths or PUBLIC_DOCS)} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
