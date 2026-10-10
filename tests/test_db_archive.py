"""Tests for backup/restore format detection and the safe restore command."""

from __future__ import annotations

import gzip
import hashlib
import sqlite3
from pathlib import Path

import pytest

from scripts import db_archive
from scripts.db_archive import (
    FORMAT_SQL_DUMP,
    FORMAT_SQLITE,
    FORMAT_UNKNOWN,
    ArchiveError,
    detect_format,
    extract_sqlite,
    read_manifest,
    sha256_file,
    verify_sqlite,
    write_manifest,
)
from scripts.restore_db import main as restore_main


def _make_sqlite(path: Path, rows: int = 3) -> Path:
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE schools (id INTEGER PRIMARY KEY, name TEXT)")
    connection.executemany("INSERT INTO schools (name) VALUES (?)", [(f"示例中学{i}",) for i in range(rows)])
    connection.commit()
    connection.close()
    return path


def test_detects_sqlite_by_magic_bytes(tmp_path: Path) -> None:
    database = _make_sqlite(tmp_path / "plain.db")

    detected = detect_format(database)

    assert detected.name == FORMAT_SQLITE
    assert detected.encoding == "plain"
    assert detected.inner is None


def test_gzipped_sqlite_is_identified_despite_sql_dump_name(tmp_path: Path) -> None:
    database = _make_sqlite(tmp_path / "source.db")
    misnamed = tmp_path / "gaokao_db_20260101_000000.sql.gz"
    misnamed.write_bytes(gzip.compress(database.read_bytes()))

    detected = detect_format(misnamed)

    assert detected.describe() == f"gzip -> {FORMAT_SQLITE}"
    assert detected.encoding == "gzip"
    assert detected.inner is not None
    assert detected.inner.name == FORMAT_SQLITE
    assert detected.declared_extension == ".sql.gz"


def test_real_sql_dump_is_not_treated_as_sqlite(tmp_path: Path) -> None:
    dump = tmp_path / "dump.sql"
    dump.write_text("PRAGMA foreign_keys=OFF;\nCREATE TABLE schools (id integer);\nINSERT INTO schools VALUES (1);\n")

    assert detect_format(dump).name == FORMAT_SQL_DUMP


def test_gzipped_sql_dump_reports_inner_format(tmp_path: Path) -> None:
    dump = tmp_path / "dump.sql.gz"
    dump.write_bytes(gzip.compress(b"CREATE TABLE schools (id integer);\n"))

    detected = detect_format(dump)

    assert detected.inner is not None
    assert detected.inner.name == FORMAT_SQL_DUMP


def test_unknown_content_is_rejected(tmp_path: Path) -> None:
    blob = tmp_path / "payload.bin"
    blob.write_bytes(b"\x00\x01\x02 not a database")

    assert detect_format(blob).name == FORMAT_UNKNOWN


def test_truncated_gzip_raises_archive_error(tmp_path: Path) -> None:
    database = _make_sqlite(tmp_path / "source.db")
    broken = tmp_path / "broken.sql.gz"
    broken.write_bytes(gzip.compress(database.read_bytes())[:20])

    with pytest.raises(ArchiveError):
        detect_format(broken)


def test_extract_sqlite_refuses_to_overwrite_without_consent(tmp_path: Path) -> None:
    database = _make_sqlite(tmp_path / "source.db")
    archive = tmp_path / "archive.sql.gz"
    archive.write_bytes(gzip.compress(database.read_bytes()))
    destination = tmp_path / "restored.db"
    destination.write_bytes(b"existing")

    with pytest.raises(ArchiveError):
        extract_sqlite(archive, destination)

    assert destination.read_bytes() == b"existing"


def test_extract_sqlite_rejects_non_sqlite_payload(tmp_path: Path) -> None:
    archive = tmp_path / "dump.sql.gz"
    archive.write_bytes(gzip.compress(b"CREATE TABLE t (id integer);\n"))

    with pytest.raises(ArchiveError):
        extract_sqlite(archive, tmp_path / "out.db")


def test_verify_sqlite_reports_integrity_and_counts(tmp_path: Path) -> None:
    database = _make_sqlite(tmp_path / "source.db", rows=4)

    report = verify_sqlite(database)

    assert report["integrity"] == "ok"
    assert report["tables"] == ["schools"]
    assert report["counts"] == {"schools": 4}


def test_manifest_round_trip_records_digest_and_counts(tmp_path: Path) -> None:
    database = _make_sqlite(tmp_path / "source.db", rows=2)
    archive = tmp_path / "backup.sql.gz"
    archive.write_bytes(gzip.compress(database.read_bytes()))

    entry = db_archive.build_manifest_entry(archive, database)
    manifest_path = write_manifest([entry], tmp_path / "MANIFEST.json")
    manifest = read_manifest(manifest_path)

    assert manifest[archive.name].sha256 == sha256_file(archive)
    assert manifest[archive.name].tables == {"schools": 2}
    assert manifest[archive.name].uncompressed_bytes == database.stat().st_size


def test_restore_dry_run_writes_nothing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    database = _make_sqlite(tmp_path / "source.db")
    archive = tmp_path / "backup.sql.gz"
    archive.write_bytes(gzip.compress(database.read_bytes()))
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    target = tmp_path / "target.db"

    code = restore_main(
        [
            "--archive",
            str(archive),
            "--target",
            str(target),
            "--sha256",
            digest,
            "--confirm-data-rights",
            "--staging",
            str(tmp_path / "staging.db"),
        ]
    )

    output = capsys.readouterr().out
    assert code == 0
    assert "DRY RUN" in output
    assert not target.exists()
    assert not (tmp_path / "staging.db").exists()


def test_restore_requires_data_rights_confirmation(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    database = _make_sqlite(tmp_path / "source.db")
    archive = tmp_path / "backup.sql.gz"
    archive.write_bytes(gzip.compress(database.read_bytes()))

    code = restore_main(["--archive", str(archive), "--target", str(tmp_path / "target.db"), "--apply"])

    assert code == 1
    assert "data rights not confirmed" in capsys.readouterr().out


def test_restore_rejects_sha256_mismatch(tmp_path: Path) -> None:
    database = _make_sqlite(tmp_path / "source.db")
    archive = tmp_path / "backup.sql.gz"
    archive.write_bytes(gzip.compress(database.read_bytes()))

    code = restore_main(
        [
            "--archive",
            str(archive),
            "--target",
            str(tmp_path / "target.db"),
            "--sha256",
            "0" * 64,
            "--confirm-data-rights",
        ]
    )

    assert code == 1


def test_restore_refuses_existing_target_without_replace(tmp_path: Path) -> None:
    database = _make_sqlite(tmp_path / "source.db")
    archive = tmp_path / "backup.sql.gz"
    archive.write_bytes(gzip.compress(database.read_bytes()))
    target = _make_sqlite(tmp_path / "target.db", rows=1)

    code = restore_main(["--archive", str(archive), "--target", str(target), "--confirm-data-rights", "--apply"])

    assert code == 1
    assert verify_sqlite(target)["counts"] == {"schools": 1}


def test_restore_snapshots_existing_target_before_replacing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    database = _make_sqlite(tmp_path / "source.db", rows=7)
    archive = tmp_path / "backup.sql.gz"
    archive.write_bytes(gzip.compress(database.read_bytes()))
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    target = _make_sqlite(tmp_path / "target.db", rows=1)
    backup_dir = tmp_path / "backups"
    monkeypatch.setattr("scripts.restore_db.BACKUP_DIR", backup_dir)

    code = restore_main(
        [
            "--archive",
            str(archive),
            "--target",
            str(target),
            "--sha256",
            digest,
            "--confirm-data-rights",
            "--replace-target",
            "--apply",
        ]
    )

    assert code == 0
    assert verify_sqlite(target)["counts"] == {"schools": 7}
    snapshots = list(backup_dir.glob("pre_restore_*"))
    assert len(snapshots) == 1
    assert verify_sqlite(snapshots[0])["counts"] == {"schools": 1}


def test_restore_aborts_when_target_is_the_archive(tmp_path: Path) -> None:
    database = _make_sqlite(tmp_path / "source.db")
    archive = tmp_path / "backup.sql.gz"
    archive.write_bytes(gzip.compress(database.read_bytes()))

    code = restore_main(
        ["--archive", str(archive), "--target", str(archive), "--confirm-data-rights", "--replace-target", "--apply"]
    )

    assert code == 1


def test_make_sqlite_backup_uses_online_backup_api(tmp_path: Path) -> None:
    source = _make_sqlite(tmp_path / "source.db", rows=5)
    destination = tmp_path / "snapshot.db"

    db_archive.make_sqlite_backup(source, destination)
    report = verify_sqlite(destination)

    assert report["integrity"] == "ok"
    assert report["counts"] == {"schools": 5}
    assert source.exists()


def test_sha256_file_matches_hashlib(tmp_path: Path) -> None:
    payload = tmp_path / "payload.bin"
    payload.write_bytes(b"gaobao" * 1000)

    assert sha256_file(payload) == hashlib.sha256(payload.read_bytes()).hexdigest()


def test_repository_backup_naming_bug_is_reported_as_sqlite(tmp_path: Path) -> None:
    """The shipped *.sql.gz backups are gzipped SQLite files, not SQL dumps."""
    database = _make_sqlite(tmp_path / "source.db")
    misnamed = tmp_path / "gaokao_db_20260617_025354.sql.gz"
    misnamed.write_bytes(gzip.compress(database.read_bytes()))

    detected = detect_format(misnamed)

    assert detected.name == "gzip+inner"
    assert detected.inner is not None
    assert detected.inner.name == FORMAT_SQLITE
    assert detected.declared_extension == ".sql.gz"
