"""SVG cover generator for gaokao advisory reports (金榜题名封面)."""

from __future__ import annotations

import html as html_lib
from datetime import datetime

from config.loader import load_brand
from server.report.models import Report


class CoverGenerator:
    """Generate a 金榜题名 SVG cover for a Report."""

    _SVG_TEMPLATE = """\
<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 500">
  <defs>
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#FFD700;stop-opacity:1" />
      <stop offset="50%" style="stop-color:#FFA500;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#FF8C00;stop-opacity:1" />
    </linearGradient>
  </defs>
  <!-- Background -->
  <rect width="800" height="500" fill="url(#bgGrad)" />
  <!-- Border -->
  <rect x="10" y="10" width="780" height="480" fill="none" stroke="#8B0000" stroke-width="4" rx="8" />
  <rect x="20" y="20" width="760" height="460" fill="none" stroke="#8B0000" stroke-width="2" rx="6" />
  <!-- Title -->
  <text x="400" y="140" font-family="KaiTi, STKaiti, serif" font-size="72" fill="#DC143C" text-anchor="middle" font-weight="bold">{report_title}</text>
  <!-- Decorative line -->
  <line x1="200" y1="170" x2="600" y2="170" stroke="#8B0000" stroke-width="2" />
  <circle cx="200" cy="170" r="4" fill="#8B0000" />
  <circle cx="600" cy="170" r="4" fill="#8B0000" />
  <!-- Subtitle -->
  <text x="400" y="210" font-family="KaiTi, STKaiti, serif" font-size="22" fill="#8B0000" text-anchor="middle">{subtitle}</text>
  <!-- Year badge -->
  <rect x="320" y="230" width="160" height="36" rx="18" fill="#8B0000" />
  <text x="400" y="254" font-family="KaiTi, STKaiti, serif" font-size="18" fill="#FFD700" text-anchor="middle">{year_badge}</text>
  <!-- Student info -->
  {student_info}
  <!-- Footer -->
  <text x="400" y="460" font-family="KaiTi, STKaiti, serif" font-size="14" fill="#8B0000" text-anchor="middle" opacity="0.7">{footer_text}</text>
</svg>"""

    @classmethod
    def generate_svg(cls, report: Report) -> str:
        """Generate an SVG cover string for the given report."""
        brand = load_brand()
        report_cfg = brand.get("report", {})
        brand_cfg = brand.get("brand", {})
        brand_name = brand_cfg.get("name", "高考志愿AI顾问")
        cover_title = report_cfg.get("cover_title", "金榜题名")
        subtitle = report_cfg.get("subtitle", "高考志愿填报分析报告")
        year = report_cfg.get("year", datetime.now().year)

        year_badge = f"{year} 年度"
        footer_text = brand_cfg.get("copyright", "© 高考志愿AI顾问 · 助力每一个梦想")

        # Escape all user-provided and config-provided values for SVG safety
        safe_cover_title = html_lib.escape(str(cover_title), quote=True)
        safe_subtitle = html_lib.escape(str(subtitle), quote=True)
        safe_year_badge = html_lib.escape(str(year_badge), quote=True)
        safe_footer = html_lib.escape(str(footer_text), quote=True)
        safe_brand_name = html_lib.escape(str(brand_name), quote=True)

        parts: list[str] = []
        if report.student_name:
            parts.append(html_lib.escape(report.student_name, quote=True))
        if report.province:
            parts.append(html_lib.escape(report.province, quote=True))
        if report.score:
            parts.append(f"{html_lib.escape(str(report.score), quote=True)}分")

        if parts:
            info_text = " · ".join(parts)
            student_info = (
                f'<text x="400" y="320" font-family="KaiTi, STKaiti, serif" '
                f'font-size="24" fill="#8B0000" text-anchor="middle">{info_text}</text>'
            )
        else:
            student_info = (
                '<text x="400" y="320" font-family="KaiTi, STKaiti, serif" '
                f'font-size="24" fill="#8B0000" text-anchor="middle">{safe_subtitle}</text>'
            )

        # Use format() safely — all placeholders are fixed, values are already escaped
        svg = cls._SVG_TEMPLATE.format(
            report_title=safe_cover_title,
            subtitle=safe_subtitle,
            student_info=student_info,
            year_badge=safe_year_badge,
            footer_text=safe_footer,
        )
        # Replace placeholder words with brand config (escaped)
        svg = svg.replace("金榜题名", safe_cover_title)
        svg = svg.replace("高考志愿AI顾问", safe_brand_name)
        return svg
