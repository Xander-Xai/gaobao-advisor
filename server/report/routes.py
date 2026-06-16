"""Report API routes — generate, retrieve, and export advisory reports."""

from __future__ import annotations

from fastapi import APIRouter, Response
from pydantic import BaseModel

from server.report.cover import CoverGenerator
from server.report.exporter import ReportExporter
from server.report.models import Report
from server.report.storage import ReportStorage

router = APIRouter(prefix="/api/v1", tags=["report"])

_storage = ReportStorage()


class GenerateRequest(BaseModel):
    """Request body for report generation."""

    session_id: str
    student_name: str | None = None


class GenerateResponse(BaseModel):
    """Response body for report generation."""

    report_id: str
    status: str
    message: str


@router.post("/report/generate", response_model=GenerateResponse)
async def generate_report(body: GenerateRequest):
    """Create a minimal Report (MVP placeholder) and persist it."""
    report = Report(
        session_id=body.session_id,
        student_name=body.student_name,
        province="",
        summary="报告生成中，请稍候。",
    )
    _storage.save(report)
    return GenerateResponse(
        report_id=report.id,
        status="created",
        message="Report generated successfully.",
    )


@router.get("/report/{report_id}")
async def get_report(report_id: str):
    """Return report data as a JSON dict."""
    report = _storage.load(report_id)
    if report is None:
        return Response(content='{"error": "Report not found"}', media_type="application/json", status_code=404)
    return report.to_dict()


@router.get("/report/{report_id}/html")
async def get_report_html(report_id: str):
    """Return the full HTML report page."""
    report = _storage.load(report_id)
    if report is None:
        return Response(content="Report not found", status_code=404)
    html = ReportExporter.to_html(report)
    return Response(content=html, media_type="text/html")


@router.get("/report/{report_id}/cover.svg")
async def get_report_cover(report_id: str):
    """Return the SVG cover image for a report."""
    report = _storage.load(report_id)
    if report is None:
        return Response(content="Report not found", status_code=404)
    svg = CoverGenerator.generate_svg(report)
    return Response(content=svg, media_type="image/svg+xml")
