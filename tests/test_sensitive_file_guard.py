"""Prevention controls for databases, dumps, backups and real env files."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from scripts.check_sensitive_files import check_paths, is_sensitive_path

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize(
    "path",
    [
        "data/gaokao.db",
        "data/gaokao.db-wal",
        "backups/gaokao.sql.gz",
        "export.sql",
        "dump.zip",
        ".env",
        ".env.production",
        "certs/server.pem",
        "logs/app.log",
    ],
)
def test_sensitive_paths_are_blocked(path):
    assert is_sensitive_path(path) is True


@pytest.mark.parametrize(
    "path",
    [".env.example", ".streamlit/secrets.toml.example", "server/main.py", "frontend/package-lock.json"],
)
def test_public_examples_are_allowed(path):
    assert is_sensitive_path(path) is False


def test_tracked_db_is_rejected_in_a_git_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo, check=True)
    sensitive = repo / "data" / "gaokao.db"
    sensitive.parent.mkdir()
    sensitive.write_bytes(b"SQLite format 3\x00")
    subprocess.run(["git", "add", "data/gaokao.db"], cwd=repo, check=True)

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check_sensitive_files.py"), "--tracked"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "data/gaokao.db" in result.stderr
    assert "SQLite format" not in result.stderr


def test_large_tracked_file_is_rejected(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    big = tmp_path / "big.bin"
    big.write_bytes(b"x" * 2048)
    assert check_paths(["big.bin"], max_bytes=1024) == ["file larger than 1024 bytes: big.bin (2048 bytes)"]
