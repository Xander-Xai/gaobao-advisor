"""Read ``project.version`` from pyproject.toml on Python 3.10 and newer.

``tomllib`` only entered the standard library in Python 3.11, but CI runs the
test matrix on 3.10 as well. This module exposes one small helper so the release
scripts do not each need their own compatibility branch.
"""

from __future__ import annotations

import re
from pathlib import Path

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on Python 3.10
    tomllib = None  # type: ignore[assignment]

try:  # optional, commonly present as a transitive dependency
    import tomli as _tomli
except ModuleNotFoundError:  # pragma: no cover
    _tomli = None

_PROJECT_SECTION_RE = re.compile(r"^\[project\]\s*$", re.MULTILINE)
_ANY_SECTION_RE = re.compile(r"^\[[^\]]+\]\s*$", re.MULTILINE)
_VERSION_LINE_RE = re.compile(r"""^\s*version\s*=\s*["']([^"']+)["']""", re.MULTILINE)


def _parse_with_loader(path: Path):
    loader = tomllib if tomllib is not None else _tomli
    if loader is None:
        return None
    with path.open("rb") as stream:
        try:
            return loader.load(stream)
        except Exception:  # pragma: no cover - malformed TOML
            return None


def _regex_project_version(text: str) -> str | None:
    """Extract ``[project] version`` without a TOML parser, scoped to the section."""
    section_match = _PROJECT_SECTION_RE.search(text)
    if section_match is None:
        return None
    remainder = text[section_match.end() :]
    next_section = _ANY_SECTION_RE.search(remainder)
    section_body = remainder if next_section is None else remainder[: next_section.start()]
    version_match = _VERSION_LINE_RE.search(section_body)
    return version_match.group(1) if version_match else None


def read_project_version(root: Path | str, filename: str = "pyproject.toml") -> str | None:
    """Return the declared project version, or ``None`` when it cannot be read."""
    path = Path(root) / filename
    if not path.is_file():
        return None

    parsed = _parse_with_loader(path)
    if isinstance(parsed, dict):
        return parsed.get("project", {}).get("version")

    return _regex_project_version(path.read_text(encoding="utf-8"))
