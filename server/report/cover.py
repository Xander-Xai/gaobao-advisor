"""SVG cover generator for gaokao advisory reports (金榜题名封面)."""

from __future__ import annotations

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
  <text x="400" y="140" font-family="KaiTi, STKaiti, serif" font-size="72" fill="#DC143C" text-anchor="middle" font-weight="bold">金榜题名</text>
  <!-- Decorative line -->
  <line x1="200" y1="170" x2="600" y2="170" stroke="#8B0000" stroke-width="2" />
  <circle cx="200" cy="170" r="4" fill="#8B0000" />
  <circle cx="600" cy="170" r="4" fill="#8B0000" />
  <!-- Subtitle -->
  <text x="400" y="210" font-family="KaiTi, STKaiti, serif" font-size="22" fill="#8B0000" text-anchor="middle">高考志愿填报分析报告</text>
  <!-- Year badge -->
  <rect x="320" y="230" width="160" height="36" rx="18" fill="#8B0000" />
  <text x="400" y="254" font-family="KaiTi, STKaiti, serif" font-size="18" fill="#FFD700" text-anchor="middle">2026 年度</text>
  <!-- Student info -->
  {student_info}
  <!-- Footer -->
  <text x="400" y="460" font-family="KaiTi, STKaiti, serif" font-size="14" fill="#8B0000" text-anchor="middle" opacity="0.7">© 高考志愿AI顾问 · 助力每一个梦想</text>
</svg>"""

    @classmethod
    def generate_svg(cls, report: Report) -> str:
        """Generate an SVG cover string for the given report."""
        parts: list[str] = []
        if report.student_name:
            parts.append(report.student_name)
        if report.province:
            parts.append(report.province)
        if report.score:
            parts.append(f"{report.score}分")

        if parts:
            info_text = " · ".join(parts)
            student_info = (
                f'<text x="400" y="320" font-family="KaiTi, STKaiti, serif" '
                f'font-size="24" fill="#8B0000" text-anchor="middle">{info_text}</text>'
            )
        else:
            student_info = (
                '<text x="400" y="320" font-family="KaiTi, STKaiti, serif" '
                'font-size="24" fill="#8B0000" text-anchor="middle">高考志愿填报分析报告</text>'
            )

        return cls._SVG_TEMPLATE.format(student_info=student_info)
