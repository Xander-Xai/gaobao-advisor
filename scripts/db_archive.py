#!/usr/bin/env python3
"""Backup archive detection shared by the backup and restore commands.

Historical backups in this repository are named ``*.sql.gz`` but hold a
gzipped SQLite database file rather than a SQL dump. Every consumer therefore
identifies an archive by its magic bytes and never by its extension.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import sqlite3
import tempfile
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

GZIP_MAGIC = b"\x1f\x8b"
SQLITE_MAGIC = b"SQLite format 3\x00"
SQL_DUMP_MARKERS = (
    b"CREATE TABLE",
    b"CREATE INDEX",
    b"INSERT INTO",
    b"BEGIN TRANSACTION",
    b"PRAGMA foreign_keys",
    b"-- PostgreSQL database dump",
    b"-- MySQL dump",
    b"SET SQL_MODE",
)
SNIFF_BYTES = 4096

FORMAT_SQLITE = "sqlite"
FORMAT_SQL_DUMP = "sql-dump"
FORMAT_GZIP_WRAPPED = "gzip+inner"
FORMAT_UNKNOWN = "unknown"


class ArchiveError(RuntimeError):
    """Raised when an archive cannot be identified or is internally broken."""


@dataclass(frozen=True)
class DetectedFormat:
    """What an archive actually is, independent of how it was named."""

    name: str
    encoding: str
    sha256: str
    size_bytes: int
    uncompressed_bytes: int | None = None
    inner: DetectedFormat | None = None
    declared_extension: str = ""

    def describe(self) -> str:
        if self.inner is not None:
            return f"{self.encoding} -> {self.inner.name}"
        return self.name


@dataclass
class ManifestEntry:
    """One row of the backup manifest."""

    path: str
    sha256: str
    format: str
    encoding: str
    size_bytes: int
    uncompressed_bytes: int | None
    created_at: str
    tables: dict[str, int] = field(default_factory=dict)

    def to_json(self) -> dict:
        return {
            "path": self.path,
            "sha256": self.sha256,
            "format": self.format,
            "encoding": self.encoding,
            "size_bytes": self.size_bytes,
            "uncompressed_bytes": self.uncompressed_bytes,
            "created_at": self.created_at,
            "tables": self.tables,
        }

    @classmethod
    def from_json(cls, raw: dict) -> ManifestEntry:
        return cls(
            path=raw["path"],
            sha256=raw["sha256"],
            format=raw["format"],
            encoding=raw["encoding"],
            size_bytes=raw["size_bytes"],
            uncompressed_bytes=raw.get("uncompressed_bytes"),
            created_at=raw.get("created_at", ""),
            tables=raw.get("tables", {}),
        )


def sha256_file(path: Path, chunk_size: int = 1 << 20) -> str:
    """Stream a file through SHA-256 without loading it into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sniff(payload: bytes) -> str:
    if payload.startswith(SQLITE_MAGIC):
        return FORMAT_SQLITE
    stripped = payload.lstrip()
    if any(marker in stripped[:2048].upper() for marker in SQL_DUMP_MARKERS):
        return FORMAT_SQL_DUMP
    if stripped[:1] in (b"-", b"/", b"*"):
        return FORMAT_SQL_DUMP
    return FORMAT_UNKNOWN


def detect_format(path: Path) -> DetectedFormat:
    """Identify an archive from its bytes, never from its file name."""
    path = Path(path)
    if not path.is_file():
        raise ArchiveError(f"not a file: {path}")

    size = path.stat().st_size
    digest = sha256_file(path)
    declared = "".join(path.suffixes)

    with path.open("rb") as handle:
        head = handle.read(SNIFF_BYTES)

    if head.startswith(GZIP_MAGIC):
        try:
            with gzip.open(path, "rb") as decompressed:
                inner_head = decompressed.read(SNIFF_BYTES)
                uncompressed = len(inner_head) + len(decompressed.read())
        except (OSError, EOFError, zlib.error) as exc:
            raise ArchiveError(f"gzip stream is truncated or corrupt: {path}") from exc

        inner = DetectedFormat(
            name=_sniff(inner_head),
            encoding="plain",
            sha256="",
            size_bytes=0,
            uncompressed_bytes=uncompressed,
            declared_extension=declared,
        )
        return DetectedFormat(
            name=FORMAT_GZIP_WRAPPED,
            encoding="gzip",
            sha256=digest,
            size_bytes=size,
            uncompressed_bytes=uncompressed,
            inner=inner,
            declared_extension=declared,
        )

    kind = _sniff(head)
    return DetectedFormat(
        name=kind,
        encoding="plain",
        sha256=digest,
        size_bytes=size,
        uncompressed_bytes=size,
        declared_extension=declared,
    )


def extract_sqlite(archive: Path, destination: Path, overwrite: bool = False) -> Path:
    """Materialise the SQLite file carried by an archive at ``destination``."""
    destination = Path(destination)
    if destination.exists() and not overwrite:
        raise ArchiveError(f"refusing to overwrite existing file: {destination}")

    archive = Path(archive)
    detected = detect_format(archive)

    destination.parent.mkdir(parents=True, exist_ok=True)
    opener = gzip.open if detected.encoding == "gzip" else open
    with opener(archive, "rb") as source, destination.open("wb") as target:
        while chunk := source.read(1 << 20):
            target.write(chunk)

    if detected.inner is not None and detected.inner.name != FORMAT_SQLITE:
        destination.unlink(missing_ok=True)
        raise ArchiveError(f"{archive} carries a {detected.inner.name!r} payload, not a SQLite database")
    return destination


def verify_sqlite(path: Path) -> dict:
    """Run SQLite's own integrity check and report the user tables present."""
    path = Path(path)
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        counts = {name: connection.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0] for name in tables}
    finally:
        connection.close()
    return {"integrity": integrity, "tables": tables, "counts": counts}


def build_manifest_entry(path: Path, database_path: Path | None = None) -> ManifestEntry:
    """Describe one archive, optionally recording its table row counts."""
    detected = detect_format(path)
    counts: dict[str, int] = {}
    if database_path is not None and Path(database_path).exists():
        report = verify_sqlite(Path(database_path))
        if report["integrity"] == "ok":
            counts = report["counts"]
    return ManifestEntry(
        path=Path(path).name,
        sha256=detected.sha256,
        format=detected.name,
        encoding=detected.encoding,
        size_bytes=detected.size_bytes,
        uncompressed_bytes=detected.uncompressed_bytes,
        created_at=datetime.fromtimestamp(Path(path).stat().st_mtime, tz=timezone.utc).isoformat(),
        tables=counts,
    )


def write_manifest(entries: list[ManifestEntry], path: Path) -> Path:
    """Persist the manifest next to the archives it describes."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "archives": [entry.to_json() for entry in entries],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def read_manifest(path: Path) -> dict[str, ManifestEntry]:
    """Load a manifest written by :func:`write_manifest`."""
    path = Path(path)
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {entry["path"]: ManifestEntry.from_json(entry) for entry in payload.get("archives", [])}


def make_sqlite_backup(source: Path, destination: Path) -> tuple[Path, dict]:
    """Create a consistent SQLite backup using the online backup API."""
    source = Path(source)
    if not source.is_file():
        raise ArchiveError(f"source database not found: {source}")
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, suffix=".tmp", delete=False) as handle:
        staging = Path(handle.name)

    src = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    try:
        dst = sqlite3.connect(staging)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()

    staging.replace(destination)
    return destination, verify_sqlite(destination)


def read_head_text(path: Path, limit: int = 200) -> str:
    """Read the first bytes of a file for human-facing diagnostics."""
    with Path(path).open("rb") as handle:
        return handle.read(limit).decode("utf-8", errors="replace")


def as_stream(path: Path) -> io.BufferedReader:
    """Open an archive for streaming, transparently decompressing gzip."""
    detected = detect_format(path)
    if detected.encoding == "gzip":
        return gzip.open(path, "rb")
    return Path(path).open("rb")
