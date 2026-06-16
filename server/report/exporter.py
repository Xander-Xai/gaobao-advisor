"""Report exporter — generates HTML (with SVG cover) and PNG from Report."""

from __future__ import annotations

import html as html_lib
from pathlib import Path

from server.report.cover import CoverGenerator
from server.report.models import Report


class ReportExporter:
    """Export a Report to HTML or PNG."""

    @staticmethod
    def to_html(report: Report) -> str:
        """Generate a full HTML page with SVG cover and structured content."""
        cover_svg = CoverGenerator.generate_svg(report)

        student_line = ""
        if report.student_name:
            student_line = f"<span>{html_lib.escape(report.student_name)}</span> · "
        student_line += f"{html_lib.escape(report.province)} · {report.score}分"
        if report.subject:
            student_line += f" · {html_lib.escape(report.subject)}"
        if report.interest:
            student_line += f" · {html_lib.escape(report.interest)}"

        confidence_pct = f"{report.confidence * 100:.0f}%"

        facts_items = "".join(
            f"<li>{html_lib.escape(f)}</li>" for f in report.facts
        )
        suggestions_items = "".join(
            f"<li>{html_lib.escape(s)}</li>" for s in report.suggestions
        )
        risks_items = "".join(
            f"<li>{html_lib.escape(r)}</li>" for r in report.risks
        )
        actions_items = "".join(
            f"<li>{html_lib.escape(a)}</li>" for a in report.next_actions
        )

        return f"""\
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>高考志愿填报分析报告</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: "KaiTi", "STKaiti", "Microsoft YaHei", serif; background: #FFF8F0; color: #333; }}
  .cover {{ text-align: center; margin-bottom: 30px; }}
  .cover svg {{ max-width: 100%; height: auto; }}
  .container {{ max-width: 800px; margin: 0 auto; padding: 20px; }}
  .student-info {{ text-align: center; font-size: 18px; color: #8B0000; margin: 20px 0; padding: 10px; border: 1px solid #FFD700; border-radius: 8px; background: #FFFDF5; }}
  .section {{ margin: 24px 0; padding: 20px; background: #fff; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }}
  .section h2 {{ font-size: 20px; color: #8B0000; border-bottom: 2px solid #FFD700; padding-bottom: 8px; margin-bottom: 12px; }}
  .section ul {{ padding-left: 20px; line-height: 1.8; }}
  .section li {{ margin-bottom: 4px; }}
  .confidence {{ text-align: center; font-size: 14px; color: #666; margin-top: 20px; }}
  .footer {{ text-align: center; font-size: 12px; color: #999; margin-top: 40px; padding: 20px 0; border-top: 1px solid #eee; }}
</style>
</head>
<body>
<div class="container">
  <div class="cover">{cover_svg}</div>
  <div class="student-info">{student_line}</div>
  <div class="section">
    <h2>分析摘要</h2>
    <p>{html_lib.escape(report.summary)}</p>
  </div>
  <div class="section">
    <h2>关键事实</h2>
    <ul>{facts_items}</ul>
  </div>
  <div class="section">
    <h2>院校推荐</h2>
    <ul>{suggestions_items}</ul>
  </div>
  <div class="section">
    <h2>风险提示</h2>
    <ul>{risks_items}</ul>
  </div>
  <div class="section">
    <h2>建议行动</h2>
    <ul>{actions_items}</ul>
  </div>
  <div class="confidence">置信度：{confidence_pct}</div>
  <div class="footer">© 高考志愿AI顾问 · 助力每一个梦想</div>
</div>
</body>
</html>"""

    @staticmethod
    def svg_to_png(svg_data: str, output_path: str | Path) -> Path:
        """Convert SVG string to PNG file using cairosvg.

        Raises ImportError if cairosvg is not installed.
        """
        try:
            import cairosvg  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "cairosvg is required for PNG export. "
                "Install with: pip install cairosvg"
            ) from exc

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cairosvg.svg2png(bytestring=svg_data.encode("utf-8"), write_to=str(output_path))
        return output_path
