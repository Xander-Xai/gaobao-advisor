"""Guards the single source of truth for the application version.

The canonical version lives in ``server/__init__.py``. Packaging metadata
(``pyproject.toml``) and the published OpenAPI documents must not drift from it.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from server import __version__

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_pyproject_version_matches_runtime() -> None:
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'(?m)^version = "([^"]+)"', pyproject)
    assert match is not None, "pyproject.toml has no [project].version"
    assert match.group(1) == __version__


def test_openapi_versions_match_runtime() -> None:
    openapi_json = json.loads((REPO_ROOT / "openapi.json").read_text(encoding="utf-8"))
    assert openapi_json["info"]["version"] == __version__

    openapi_yaml = (REPO_ROOT / "openapi.yaml").read_text(encoding="utf-8")
    assert re.search(rf"(?m)^  version: {re.escape(__version__)}$", openapi_yaml)
