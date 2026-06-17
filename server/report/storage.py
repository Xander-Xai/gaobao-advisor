"""File-based report storage — saves/loads Report as JSON."""

from __future__ import annotations

import json
from pathlib import Path

from server.report.models import Report

_DEFAULT_BASE = Path(__file__).resolve().parent.parent.parent / "data" / "reports"


class ReportStorage:
    """File-based storage for Report objects.

    Reports are stored as JSON files at: base_dir/{session_id}/{report_id}.json
    """

    def __init__(self, base_dir: str | Path | None = None) -> None:
        self._base = Path(base_dir) if base_dir else _DEFAULT_BASE

    def save(self, report: Report) -> Path:
        """Save a Report to disk. Returns the file path written."""
        dest = self._base / report.session_id / f"{report.id}.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return dest

    def load(self, report_id: str) -> Report | None:
        """Search all session dirs for a report by id. Returns None if not found."""
        if not self._base.exists():
            return None
        for session_dir in sorted(self._base.iterdir()):
            if not session_dir.is_dir():
                continue
            candidate = session_dir / f"{report_id}.json"
            if candidate.exists():
                return self._load_file(candidate)
        return None

    def load_by_session(self, report_id: str, session_id: str) -> Report | None:
        """Direct load by session_id — no search needed."""
        path = self._base / session_id / f"{report_id}.json"
        if path.exists():
            return self._load_file(path)
        return None

    def list_by_session(self, session_id: str) -> list[Report]:
        """Return all reports for a given session, sorted by creation time."""
        session_dir = self._base / session_id
        if not session_dir.exists():
            return []
        reports: list[Report] = []
        for fp in sorted(session_dir.glob("*.json")):
            reports.append(self._load_file(fp))
        return reports

    @staticmethod
    def _load_file(path: Path) -> Report:
        data = json.loads(path.read_text(encoding="utf-8"))
        return Report.from_dict(data)
