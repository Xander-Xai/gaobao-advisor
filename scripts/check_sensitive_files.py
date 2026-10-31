#!/usr/bin/env python3
"""Block databases, dumps, backups and real environment files from Git.

Run manually (``--tracked``), from CI, or from the local pre-commit hook
(``--staged``). Only paths and sizes are printed; file contents are never
logged.
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import subprocess
import sys
from pathlib import Path

MAX_TRACKED_BYTES = 10 * 1024 * 1024

ALLOWED_EXAMPLES = {
    ".env.example",
    ".env.sample",
    ".streamlit/secrets.toml.example",
}

SENSITIVE_BASENAME_PATTERNS = (
    ".env",
    ".env.*",
    "*.db",
    "*.db-journal",
    "*.db-wal",
    "*.db-shm",
    "*.sqlite",
    "*.sqlite3",
    "*.sql",
    "*.sql.gz",
    "*.zip",
    "*.tar.gz",
    "*.tgz",
    "*.dump",
    "*.bak",
    "*.backup",
    "*.log",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "id_rsa",
    "id_ed25519",
)

SENSITIVE_PREFIXES = (
    "backups/",
    "backup/",
    "data/reports/",
    "gaobao-security-quarantine/",
    "security-quarantine/",
)


def is_sensitive_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    if normalized in ALLOWED_EXAMPLES:
        return False
    name = Path(normalized).name
    if any(normalized.startswith(prefix) for prefix in SENSITIVE_PREFIXES):
        return True
    return any(fnmatch.fnmatch(name, pattern) for pattern in SENSITIVE_BASENAME_PATTERNS)


def _git_paths(*args: str) -> list[str]:
    result = subprocess.run(
        ["git", *args, "-z"],
        capture_output=True,
        check=True,
    )
    return [item.decode("utf-8", "replace") for item in result.stdout.split(b"\0") if item]


def _tracked_paths() -> list[str]:
    return _git_paths("ls-files")


def _staged_paths() -> list[str]:
    return _git_paths("diff", "--cached", "--name-only", "--diff-filter=ACMR")


def check_paths(paths: list[str], *, max_bytes: int = MAX_TRACKED_BYTES) -> list[str]:
    problems: list[str] = []
    seen: set[str] = set()
    for path in paths:
        if path in seen:
            continue
        seen.add(path)
        if is_sensitive_path(path):
            problems.append(f"sensitive path: {path}")
            continue
        try:
            size = os.path.getsize(path)
        except OSError:
            continue
        if size > max_bytes:
            problems.append(f"file larger than {max_bytes} bytes: {path} ({size} bytes)")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--tracked", action="store_true", help="check every tracked file")
    mode.add_argument("--staged", action="store_true", help="check files staged for commit")
    mode.add_argument("--paths", nargs="+", help="check explicit paths")
    parser.add_argument("--max-bytes", type=int, default=MAX_TRACKED_BYTES)
    args = parser.parse_args(argv)

    try:
        if args.tracked:
            paths = _tracked_paths()
        elif args.staged:
            paths = _staged_paths()
        else:
            paths = list(args.paths or [])
    except subprocess.CalledProcessError as exc:
        print(f"git command failed: {exc}", file=sys.stderr)
        return 2

    problems = check_paths(paths, max_bytes=args.max_bytes)
    if not problems:
        print(f"sensitive-file guard: clean ({len(paths)} file(s) checked)")
        return 0
    print("sensitive-file guard: blocked", file=sys.stderr)
    for problem in problems:
        print(f"  - {problem}", file=sys.stderr)
    print(
        "Generate synthetic data with `python -m scripts.seed_demo_data --db data/demo.db --reset`; "
        "never commit databases, dumps, backups or real environment files.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
