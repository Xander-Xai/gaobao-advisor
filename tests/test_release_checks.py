import json
from pathlib import Path

import pytest

from scripts.check_docs import check_public_docs, check_version_consistency
from scripts.check_licenses import audit_npm_lock, audit_python_report


def test_docs_check_rejects_placeholder_broken_link_and_version_drift(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "3.0.0"\n', encoding="utf-8")
    (tmp_path / "README.md").write_text(
        "https://github.com/your-org/project\n[missing](docs/missing.md)\n当前版本：2.9.0\n",
        encoding="utf-8",
    )

    issues = check_public_docs(tmp_path, [Path("README.md")])

    assert any("placeholder" in issue for issue in issues)
    assert any("broken local link" in issue for issue in issues)
    assert any("version drift" in issue for issue in issues)


def test_docs_check_accepts_existing_relative_links_and_matching_version(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "3.0.0"\n', encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "guide.md").write_text("# Guide\n", encoding="utf-8")
    (tmp_path / "README.md").write_text(
        "[guide](docs/guide.md#guide)\n当前版本：3.0.0\n",
        encoding="utf-8",
    )

    assert check_public_docs(tmp_path, [Path("README.md")]) == []


def test_version_check_rejects_backend_frontend_drift(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "3.1.0"\n', encoding="utf-8")
    (tmp_path / "server").mkdir()
    (tmp_path / "server" / "__init__.py").write_text('__version__ = "3.1.0"\n', encoding="utf-8")
    (tmp_path / "frontend").mkdir()
    (tmp_path / "frontend" / "package.json").write_text('{"version":"3.0.0"}\n', encoding="utf-8")

    issues = check_version_consistency(tmp_path)

    assert any("frontend/package.json" in issue for issue in issues)


@pytest.mark.parametrize("license_name", ["AGPL-3.0-only", "SSPL-1.0", "UNKNOWN"])
def test_npm_license_check_rejects_prohibited_or_unknown_licenses(tmp_path: Path, license_name: str):
    lock = tmp_path / "package-lock.json"
    lock.write_text(
        json.dumps(
            {
                "packages": {
                    "": {"name": "example"},
                    "node_modules/example": {"version": "1.0.0", "license": license_name},
                }
            }
        ),
        encoding="utf-8",
    )

    assert audit_npm_lock(lock)


def test_license_check_accepts_current_permissive_expressions(tmp_path: Path):
    lock = tmp_path / "package-lock.json"
    lock.write_text(
        json.dumps(
            {
                "packages": {
                    "": {"name": "example"},
                    "node_modules/example": {
                        "version": "1.0.0",
                        "license": "(MPL-2.0 OR Apache-2.0)",
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    assert audit_npm_lock(lock) == []
    assert audit_python_report([{"Name": "example", "License": "MIT License"}]) == []


def test_python_license_check_rejects_gpl_family():
    issues = audit_python_report([{"Name": "example", "License": "GNU General Public License v3"}])

    assert issues
