"""File-based report storage — saves/loads Report as JSON."""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

from server.report.models import Report

logger = logging.getLogger(__name__)

_DEFAULT_BASE_ENV = os.getenv("GAOBAO__REPORTS_DIR", "")
_DEFAULT_BASE = (
    Path(_DEFAULT_BASE_ENV)
    if _DEFAULT_BASE_ENV
    else (Path(__file__).resolve().parent.parent.parent / "data" / "reports")
)


class ReportStorage:
    """File-based storage for Report objects.

    Reports are stored as JSON files at: base_dir/{session_id}/{report_id}.json
    """

    def __init__(self, base_dir: str | Path | None = None) -> None:
        raw_base = Path(base_dir) if base_dir else _DEFAULT_BASE
        if not isinstance(raw_base, Path):
            raw_base = Path(str(raw_base))
        self._base = raw_base.resolve()

    def _safe_path(self, *parts: str) -> Path:
        """Resolve a path under self._base, raising on traversal attempts."""
        resolved = self._base.joinpath(*parts).resolve()
        if not str(resolved).startswith(str(self._base)):
            raise ValueError(f"Path traversal detected: {resolved}")
        return resolved

    def save(self, report: Report) -> Path:
        """Save a Report to disk atomically. Returns the file path written."""
        session_part = report.session_id
        if not re.match(r"^[a-zA-Z0-9_\-]{4,64}$", session_part):
            raise ValueError(f"Invalid session_id: {session_part!r}")

        # Validate report_id contains only safe characters
        if not re.match(r"^[a-zA-Z0-9_\-]+$", report.id):
            raise ValueError(f"Invalid report_id: {report.id!r}")

        dest = self._safe_path(session_part, f"{report.id}.json")
        dest.parent.mkdir(parents=True, exist_ok=True)

        # Atomic write: write to temp file then rename
        tmp = dest.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(dest)
        return dest

    def load(self, report_id: str) -> Report | None:
        """Search all session dirs for a report by id. Returns None if not found."""
        # Validate report_id contains only safe characters
        if not re.match(r"^[a-zA-Z0-9_\-]+$", report_id):
            return None
        if not self._base.exists():
            return None
        for session_dir in sorted(self._base.iterdir()):
            if not session_dir.is_dir():
                continue
            try:
                candidate = self._safe_path(session_dir.name, f"{report_id}.json")
            except ValueError:
                continue
            if candidate.exists():
                return self._load_file(candidate)
        return None

    def load_by_session(self, report_id: str, session_id: str) -> Report | None:
        """Direct load by session_id — no search needed."""
        # Validate report_id contains only safe characters
        if not re.match(r"^[a-zA-Z0-9_\-]+$", report_id):
            return None
        try:
            path = self._safe_path(session_id, f"{report_id}.json")
        except ValueError:
            return None
        if path.exists():
            return self._load_file(path)
        return None

    def list_by_session(self, session_id: str) -> list[Report]:
        """Return all reports for a given session, sorted by creation time."""
        try:
            session_dir = self._safe_path(session_id)
        except ValueError:
            return []
        if not session_dir.exists():
            return []
        reports: list[Report] = []
        for fp in sorted(session_dir.glob("*.json")):
            if fp.suffix == ".tmp":
                continue
            try:
                reports.append(self._load_file(fp))
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                logger.warning("Skipping corrupt report file %s: %s", fp, exc)
        return reports

    @staticmethod
    def _load_file(path: Path) -> Report:
        data = json.loads(path.read_text(encoding="utf-8"))
        return Report.from_dict(data)
