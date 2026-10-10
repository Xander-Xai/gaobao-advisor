#!/usr/bin/env python3
"""Restore a database backup without destroying the data already on disk.

The command is dry-run by default. It identifies the archive from its bytes
rather than its file name, verifies a recorded SHA-256 when one is supplied,
refuses to overwrite an existing database, and snapshots the current database
before any write. Writing additionally requires the operator to confirm that
the data rights for the archive have been cleared.

Examples
--------
Inspect only::

    python scripts/restore_db.py --archive backups/gaokao_db_20260617_025354.sql.gz

Restore into a scratch path once rights are cleared::

    python scripts/restore_db.py --archive <file> --target data/restore-check.db \
        --sha256 <digest> --confirm-data-rights --apply
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.db_archive import (  # noqa: E402
    ArchiveError,
    FORMAT_SQLITE,
    build_manifest_entry,
    detect_format,
    extract_sqlite,
    verify_sqlite,
)

DEFAULT_TARGET = Path("data/gaokao.db")
BACKUP_DIR = Path("backups")
PRE_RESTORE_PREFIX = "pre_restore_"


def _now() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")


def _describe(path: Path) -> str:
    if not path.exists():
        return "absent"
    return f"{path.stat().st_size:,} bytes"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--archive", required=True, type=Path, help="Backup archive to restore")
    parser.add_argument(
        "--target", type=Path, default=DEFAULT_TARGET, help=f"Destination database (default: {DEFAULT_TARGET})"
    )
    parser.add_argument("--sha256", default=None, help="Expected digest of the archive; restore aborts on mismatch")
    parser.add_argument("--manifest", type=Path, default=None, help="Optional manifest to verify the archive against")
    parser.add_argument("--staging", type=Path, default=None, help="Where the extracted SQLite file is materialised")
    parser.add_argument("--expect-format", default=FORMAT_SQLITE, help="Required payload format (default: sqlite)")
    parser.add_argument(
        "--confirm-data-rights",
        action="store_true",
        help="Assert that the operator has cleared the rights to use and redistribute this data",
    )
    parser.add_argument("--apply", action="store_true", help="Perform the restore; without it the command only reports")
    parser.add_argument(
        "--skip-existing-backup",
        action="store_true",
        help="Do not snapshot the current database (only allowed together with --replace-target)",
    )
    parser.add_argument(
        "--replace-target",
        action="store_true",
        help="Overwrite an existing target database; implies the target is removed first",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    archive = args.archive.expanduser()
    target = args.target.expanduser()
    staging = (args.staging or (target.parent / f".restore-staging-{_now()}.db")).expanduser()

    failures: list[str] = []
    print("=" * 72)
    print("  DATABASE RESTORE — dry run unless --apply is supplied")
    print("=" * 72)

    print("\n[1] Archive identification (by content, not by file name)")
    try:
        detected = detect_format(archive)
    except ArchiveError as exc:
        print(f"    FAIL {exc}")
        return 2

    print(f"    path              : {archive}")
    print(f"    declared name     : {detected.declared_extension or '(none)'}")
    print(f"    actual content    : {detected.describe()}")
    print(f"    size              : {detected.size_bytes:,} bytes")
    if detected.uncompressed_bytes is not None:
        print(f"    uncompressed      : {detected.uncompressed_bytes:,} bytes")
    print(f"    sha256            : {detected.sha256}")

    misnamed = detected.describe().endswith(FORMAT_SQLITE) and not archive.name.endswith((".db", ".sqlite", ".sqlite3"))
    if misnamed:
        print("    NOTE: the extension implies a SQL dump but the bytes are a SQLite database.")

    if detected.inner is not None and detected.inner.name != args.expect_format:
        failures.append(f"payload is {detected.inner.name!r}, expected {args.expect_format!r}")
    elif detected.inner is None and detected.name != args.expect_format:
        failures.append(f"archive is {detected.name!r}, expected {args.expect_format!r}")

    print("\n[2] Integrity verification")
    if args.sha256:
        if detected.sha256.lower() == args.sha256.lower():
            print("    OK   sha256 matches the value supplied on the command line")
        else:
            failures.append(f"sha256 mismatch: expected {args.sha256}, found {detected.sha256}")
            print("    FAIL sha256 mismatch")
    else:
        print("    SKIP no --sha256 supplied; the archive was NOT verified against a recorded digest")

    if args.manifest and args.manifest.is_file():
        from scripts.db_archive import read_manifest

        entries = read_manifest(args.manifest)
        entry = entries.get(archive.name)
        if entry is None:
            print(f"    WARN {archive.name} is not listed in {args.manifest}")
        elif entry.sha256.lower() == detected.sha256.lower():
            print(f"    OK   sha256 matches manifest entry for {archive.name}")
        else:
            failures.append(f"manifest digest mismatch for {archive.name}")
            print(f"    FAIL manifest digest mismatch for {archive.name}")
    elif args.manifest:
        print(f"    WARN manifest not found: {args.manifest}")

    if not args.confirm_data_rights:
        failures.append("data rights not confirmed (pass --confirm-data-rights)")

    print("\n[3] Destination")
    print(f"    target            : {target} ({_describe(target)})")
    print(f"    staging           : {staging}")
    resolved_target = target.resolve()
    if resolved_target == archive.resolve():
        failures.append("target and archive are the same file")
    if target.exists() and not args.replace_target:
        failures.append(f"target already exists: {target} (pass --replace-target to overwrite)")

    print("\n[4] Pre-restore safety snapshot")
    snapshot: Path | None = None
    if target.exists():
        snapshot = BACKUP_DIR / f"{PRE_RESTORE_PREFIX}{_now()}{target.suffix or '.db'}"
        print(f"    current database  : {_describe(target)}")
        print(f"    would be copied to: {snapshot}")
        if args.skip_existing_backup:
            failures.append("--skip-existing-backup requires --replace-target to be meaningful")
    else:
        print("    no current database at the target; nothing to snapshot")

    print("\n[5] Action")
    if not args.apply:
        print("    DRY RUN — no file was created, moved or deleted.")
    else:
        print("    APPLY — the restore below will modify the filesystem.")

    if failures:
        print("\n[6] Blocked")
        for failure in failures:
            print(f"    FAIL {failure}")
        print("\nNothing was written.")
        return 1

    if not args.apply:
        print("\n[6] Result")
        print("    Restore is permitted. Re-run with --apply to execute it.")
        return 0

    print("\n[6] Executing")
    try:
        if snapshot is not None:
            BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, snapshot)
            print(f"    snapshotted current database to {snapshot}")

        staging.parent.mkdir(parents=True, exist_ok=True)
        staging.unlink(missing_ok=True)
        extract_sqlite(archive, staging, overwrite=True)
        report = verify_sqlite(staging)
        if report["integrity"] != "ok":
            staging.unlink(missing_ok=True)
            print(f"    FAIL extracted database failed integrity_check: {report['integrity']}")
            return 3
        print(f"    extracted {report['integrity']} database with {len(report['tables'])} tables")

        target.parent.mkdir(parents=True, exist_ok=True)
        for suffix in ("-wal", "-shm"):
            Path(str(target) + suffix).unlink(missing_ok=True)
        shutil.move(str(staging), str(target))
    except ArchiveError as exc:
        print(f"    FAIL {exc}")
        return 2

    entry = build_manifest_entry(archive, target)
    print(f"    restored into {target}")
    print(f"    tables            : {len(report['tables'])}")
    for name in report["tables"]:
        print(f"      {name:<24} {report['counts'][name]:,}")
    print(f"    archive sha256    : {entry.sha256}")
    if snapshot is not None:
        print(f"    rollback with     : cp {snapshot} {target}")
    print("\nRestore complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
