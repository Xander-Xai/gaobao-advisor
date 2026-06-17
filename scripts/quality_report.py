#!/usr/bin/env python3
"""quality_report — 生成 AI 回复质量报告。

用法:
    python3 scripts/quality_report.py --period daily
    python3 scripts/quality_report.py --period weekly --output docs/reports/quality-2026-06-17.md
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
from pathlib import Path
from typing import Any

# 确保项目根目录在 sys.path 上
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from db.database import SessionLocal
from db.models import Feedback, QualityScore


# ── 时间范围计算 ─────────────────────────────────────────────────────


def _date_range(period: str) -> tuple[datetime.datetime, datetime.datetime]:
    """根据 period 返回查询的起止时间。"""
    now = datetime.datetime.now(datetime.timezone.utc)
    if period == "weekly":
        start = now - datetime.timedelta(days=7)
    else:
        start = now - datetime.timedelta(days=1)
    return start, now


# ── 统计查询 ─────────────────────────────────────────────────────────


def _query_quality_stats(
    start: datetime.datetime,
    end: datetime.datetime,
) -> dict[str, Any]:
    """查询 quality_scores 表的统计数据。"""
    from sqlalchemy import func

    with SessionLocal() as db:
        base = db.query(QualityScore).filter(
            QualityScore.created_at >= start,
            QualityScore.created_at < end,
        )

        total = base.count()

        if total == 0:
            return {
                "total": 0,
                "avg": None,
                "min": None,
                "max": None,
                "factual_avg": None,
                "relevance_avg": None,
                "helpfulness_avg": None,
                "style_avg": None,
                "grade_distribution": {"excellent": 0, "pass": 0, "fail": 0},
                "hallucination_count": 0,
            }

        agg = base.with_entities(
            func.avg(QualityScore.aggregate_score).label("avg"),
            func.min(QualityScore.aggregate_score).label("min"),
            func.max(QualityScore.aggregate_score).label("max"),
            func.avg(QualityScore.factual_score).label("factual_avg"),
            func.avg(QualityScore.relevance_score).label("relevance_avg"),
            func.avg(QualityScore.helpfulness_score).label("helpfulness_avg"),
            func.avg(QualityScore.style_score).label("style_avg"),
        ).first()

        # 等级分布
        excellent = base.filter(QualityScore.aggregate_score >= 85).count()
        fail = base.filter(QualityScore.aggregate_score < 60).count()
        passing = total - excellent - fail

        # 幻觉标记统计
        hallucination_rows = base.filter(
            QualityScore.hallucination_flags.isnot(None),
            QualityScore.hallucination_flags != "",
        ).all()
        hallucination_count = 0
        hallucination_types: dict[str, int] = {}
        for row in hallucination_rows:
            try:
                flags = json.loads(row.hallucination_flags or "[]")
                if flags:
                    hallucination_count += 1
                    for flag in flags:
                        flag_type = flag.split(":")[0] if ":" in flag else flag
                        hallucination_types[flag_type] = hallucination_types.get(flag_type, 0) + 1
            except (json.JSONDecodeError, TypeError):
                hallucination_count += 1

        return {
            "total": total,
            "avg": round(agg.avg, 2) if agg.avg else None,
            "min": round(agg.min, 2) if agg.min else None,
            "max": round(agg.max, 2) if agg.max else None,
            "factual_avg": round(agg.factual_avg, 2) if agg.factual_avg else None,
            "relevance_avg": round(agg.relevance_avg, 2) if agg.relevance_avg else None,
            "helpfulness_avg": round(agg.helpfulness_avg, 2) if agg.helpfulness_avg else None,
            "style_avg": round(agg.style_avg, 2) if agg.style_avg else None,
            "grade_distribution": {
                "excellent": excellent,
                "pass": passing,
                "fail": fail,
            },
            "hallucination_count": hallucination_count,
            "hallucination_types": hallucination_types,
        }


def _query_feedback_stats(
    start: datetime.datetime,
    end: datetime.datetime,
) -> dict[str, Any]:
    """查询 feedbacks 表的满意度统计。"""

    with SessionLocal() as db:
        base = db.query(Feedback).filter(
            Feedback.created_at >= start,
            Feedback.created_at < end,
        )

        total = base.count()
        if total == 0:
            return {"total": 0, "helpful": 0, "not_helpful": 0, "satisfaction_rate": None}

        helpful = base.filter(Feedback.rating == "helpful").count()
        not_helpful = base.filter(Feedback.rating == "not_helpful").count()
        satisfaction_rate = round(helpful / total, 4) if total > 0 else None

        return {
            "total": total,
            "helpful": helpful,
            "not_helpful": not_helpful,
            "satisfaction_rate": satisfaction_rate,
        }


# ── 报告生成 ─────────────────────────────────────────────────────────


def _generate_report(
    period: str,
    quality_stats: dict[str, Any],
    feedback_stats: dict[str, Any],
    start: datetime.datetime,
    end: datetime.datetime,
) -> str:
    """生成 Markdown 格式的质量报告。"""
    period_label = "日报" if period == "daily" else "周报"
    date_str = end.strftime("%Y-%m-%d")
    start_str = start.strftime("%Y-%m-%d %H:%M")
    end_str = end.strftime("%Y-%m-%d %H:%M")

    lines: list[str] = []
    lines.append(f"# AI 回复质量{period_label} — {date_str}")
    lines.append("")
    lines.append(f"**统计周期**: {start_str} ~ {end_str}")
    lines.append("")

    # ── 质量评分统计 ──
    lines.append("## 质量评分统计")
    lines.append("")
    if quality_stats["total"] == 0:
        lines.append("> 本周期内无质量评分数据。")
    else:
        lines.append("| 指标 | 值 |")
        lines.append("|------|-----|")
        lines.append(f"| 评估总数 | {quality_stats['total']} |")
        lines.append(f"| 平均分 | {quality_stats['avg']} |")
        lines.append(f"| 最低分 | {quality_stats['min']} |")
        lines.append(f"| 最高分 | {quality_stats['max']} |")
        lines.append(f"| 事实性均分 | {quality_stats['factual_avg']} |")
        lines.append(f"| 相关性均分 | {quality_stats['relevance_avg']} |")
        lines.append(f"| 有用性均分 | {quality_stats['helpfulness_avg']} |")
        lines.append(f"| 风格均分 | {quality_stats['style_avg']} |")
    lines.append("")

    # ── 等级分布 ──
    lines.append("## 等级分布")
    lines.append("")
    dist = quality_stats["grade_distribution"]
    total = quality_stats["total"] or 1
    lines.append("| 等级 | 数量 | 占比 |")
    lines.append("|------|------|------|")
    lines.append(f"| excellent (>=85) | {dist['excellent']} | {round(dist['excellent']/total*100, 1)}% |")
    lines.append(f"| pass (60-84) | {dist['pass']} | {round(dist['pass']/total*100, 1)}% |")
    lines.append(f"| fail (<60) | {dist['fail']} | {round(dist['fail']/total*100, 1)}% |")
    lines.append("")

    # ── 幻觉统计 ──
    lines.append("## 幻觉检测统计")
    lines.append("")
    if quality_stats["hallucination_count"] == 0:
        lines.append("> 本周期内未检测到幻觉。")
    else:
        lines.append("| 指标 | 值 |")
        lines.append("|------|-----|")
        lines.append(f"| 含幻觉标记的回复数 | {quality_stats['hallucination_count']} |")
        if quality_stats.get("hallucination_types"):
            lines.append(f"| 幻觉类型分布 | {quality_stats['hallucination_types']} |")
    lines.append("")

    # ── 用户反馈统计 ──
    lines.append("## 用户反馈统计")
    lines.append("")
    if feedback_stats["total"] == 0:
        lines.append("> 本周期内无用户反馈数据。")
    else:
        lines.append("| 指标 | 值 |")
        lines.append("|------|-----|")
        lines.append(f"| 反馈总数 | {feedback_stats['total']} |")
        lines.append(f"| 有帮助 | {feedback_stats['helpful']} |")
        lines.append(f"| 无帮助 | {feedback_stats['not_helpful']} |")
        lines.append(f"| 满意度 | {feedback_stats['satisfaction_rate']} |")
    lines.append("")

    lines.append("---")
    lines.append(f"*报告生成时间: {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}*")
    lines.append("")

    return "\n".join(lines)


# ── 主入口 ───────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="生成 AI 回复质量报告")
    parser.add_argument(
        "--period",
        choices=["daily", "weekly"],
        default="daily",
        help="报告周期: daily (默认) 或 weekly",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="输出文件路径 (默认: docs/reports/quality-YYYY-MM-DD.md)",
    )
    args = parser.parse_args()

    start, end = _date_range(args.period)
    date_str = end.strftime("%Y-%m-%d")

    output_path = args.output or os.path.join(
        _project_root, "docs", "reports", f"quality-{date_str}.md"
    )

    # 查询数据
    quality_stats = _query_quality_stats(start, end)
    feedback_stats = _query_feedback_stats(start, end)

    # 生成报告
    report = _generate_report(args.period, quality_stats, feedback_stats, start, end)

    # 写入文件
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"报告已生成: {output_path}")


if __name__ == "__main__":
    main()
