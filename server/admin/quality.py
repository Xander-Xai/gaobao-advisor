"""Deterministic data-quality rules over the synthetic admissions dataset.

Rules are intentionally simple and explainable: the goal is a real asynchronous
workflow with auditable findings, not a general-purpose data profiler. Every
rule has a stable ``rule_code`` so the UI and tests can assert on it.
"""

from __future__ import annotations

import datetime
from typing import Any

from sqlalchemy.orm import Session

from db.models import AdmissionScore, EnrollmentPlan, School

MAX_SCHOOLS = 500
MAX_ROWS_PER_SCHOOL = 2_000
MAX_ISSUES = 500
VALID_LEVELS = {"985", "211", "双一流", "普通"}
SUBJECT_TYPES = {"物理类", "历史类", "物理", "历史", "综合", "理工", "文史"}


def _issue(
    issues: list[dict[str, Any]],
    seen: set[tuple[str, str, int, str]],
    *,
    rule_code: str,
    severity: str,
    entity_type: str,
    entity_id: int,
    field_name: str,
    message: str,
    suggestion: str | None = None,
) -> None:
    if len(issues) >= MAX_ISSUES:
        return
    key = (rule_code, entity_type, entity_id, field_name)
    if key in seen:
        return
    seen.add(key)
    issues.append(
        {
            "rule_code": rule_code,
            "severity": severity,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "field_name": field_name,
            "message": message,
            "suggestion": suggestion,
        }
    )


def collect_issues(session: Session, filters: dict[str, Any]) -> tuple[int, list[dict[str, Any]]]:
    """Return ``(checked_rows, issue_drafts)`` for the requested scope."""
    query = session.query(School)
    if filters.get("school_id") is not None:
        query = query.filter(School.id == int(filters["school_id"]))
    if filters.get("province"):
        query = query.filter(School.province == str(filters["province"]))
    if filters.get("level"):
        query = query.filter(School.level == str(filters["level"]))
    schools = query.order_by(School.id.asc()).limit(MAX_SCHOOLS).all()

    checked_rows = 0
    issues: list[dict[str, Any]] = []
    seen: set[tuple[str, str, int, str]] = set()
    current_year = datetime.datetime.now(datetime.timezone.utc).year

    if not schools:
        _issue(
            issues,
            seen,
            rule_code="no_schools_matched",
            severity="INFO",
            entity_type="filter",
            entity_id=0,
            field_name="",
            message="当前筛选条件下没有可质检的院校记录",
            suggestion="放宽省份/层次/院校筛选后重试",
        )
        return 0, issues

    for school in schools:
        checked_rows += 1
        if not school.name or not school.name.strip():
            _issue(
                issues,
                seen,
                rule_code="school_name_missing",
                severity="ERROR",
                entity_type="school",
                entity_id=school.id,
                field_name="name",
                message="院校名称为空",
                suggestion="补齐院校名称后再发布",
            )
        if not school.province or not school.province.strip():
            _issue(
                issues,
                seen,
                rule_code="school_province_missing",
                severity="ERROR",
                entity_type="school",
                entity_id=school.id,
                field_name="province",
                message="院校省份为空",
                suggestion="补充省份信息",
            )
        if school.level not in VALID_LEVELS:
            _issue(
                issues,
                seen,
                rule_code="school_level_unknown",
                severity="WARNING",
                entity_type="school",
                entity_id=school.id,
                field_name="level",
                message=f"院校层次「{school.level}」不在已知枚举内",
                suggestion=f"使用 {sorted(VALID_LEVELS)} 之一",
            )
        if school.special_type != "SYNTHETIC_DEMO_DATA":
            _issue(
                issues,
                seen,
                rule_code="non_synthetic_source",
                severity="WARNING",
                entity_type="school",
                entity_id=school.id,
                field_name="special_type",
                message="该院校记录未标记为 SYNTHETIC_DEMO_DATA，需要人工确认数据来源",
                suggestion="补充来源与授权记录后再进入演示数据集",
            )

        score_query = session.query(AdmissionScore).filter(AdmissionScore.school_id == school.id)
        if filters.get("year") is not None:
            score_query = score_query.filter(AdmissionScore.year == int(filters["year"]))
        if filters.get("subject_type"):
            score_query = score_query.filter(AdmissionScore.subject_type == str(filters["subject_type"]))
        scores = score_query.order_by(AdmissionScore.id.asc()).limit(MAX_ROWS_PER_SCHOOL).all()
        checked_rows += len(scores)

        if not scores:
            _issue(
                issues,
                seen,
                rule_code="school_without_scores",
                severity="WARNING",
                entity_type="school",
                entity_id=school.id,
                field_name="admission_scores",
                message="院校没有任何录取分数记录",
                suggestion="确认该院校是否仍在招生，或补充分数数据",
            )

        for score in scores:
            if score.min_score is None:
                _issue(
                    issues,
                    seen,
                    rule_code="score_missing",
                    severity="ERROR",
                    entity_type="admission_score",
                    entity_id=score.id,
                    field_name="min_score",
                    message="最低分为空",
                    suggestion="补齐最低分或标记为无分数院校",
                )
            elif score.min_score < 0 or score.min_score > 750:
                _issue(
                    issues,
                    seen,
                    rule_code="score_out_of_range",
                    severity="ERROR",
                    entity_type="admission_score",
                    entity_id=score.id,
                    field_name="min_score",
                    message=f"最低分 {score.min_score} 超出 0-750 合理范围",
                    suggestion="核对原始数据并修正分数",
                )
            if score.min_score is not None and score.max_score is not None and score.min_score > score.max_score:
                _issue(
                    issues,
                    seen,
                    rule_code="score_order_invalid",
                    severity="ERROR",
                    entity_type="admission_score",
                    entity_id=score.id,
                    field_name="min_score,max_score",
                    message="最低分高于最高分",
                    suggestion="交换或修正 min_score/max_score",
                )
            if score.min_rank is not None and score.min_rank <= 0:
                _issue(
                    issues,
                    seen,
                    rule_code="rank_invalid",
                    severity="WARNING",
                    entity_type="admission_score",
                    entity_id=score.id,
                    field_name="min_rank",
                    message="最低位次必须为正整数",
                    suggestion="核对一分一段表映射",
                )
            if score.year < 2000 or score.year > current_year + 1:
                _issue(
                    issues,
                    seen,
                    rule_code="year_out_of_range",
                    severity="WARNING",
                    entity_type="admission_score",
                    entity_id=score.id,
                    field_name="year",
                    message=f"录取年份 {score.year} 超出合理范围",
                    suggestion="确认年份字段是否写错",
                )
            if score.subject_type not in SUBJECT_TYPES:
                _issue(
                    issues,
                    seen,
                    rule_code="subject_type_unknown",
                    severity="INFO",
                    entity_type="admission_score",
                    entity_id=score.id,
                    field_name="subject_type",
                    message=f"科类「{score.subject_type}」不在演示数据枚举内",
                    suggestion="补充科类映射规则",
                )

        plans = (
            session.query(EnrollmentPlan)
            .filter(EnrollmentPlan.school_id == school.id)
            .order_by(EnrollmentPlan.id.asc())
            .limit(MAX_ROWS_PER_SCHOOL)
            .all()
        )
        checked_rows += len(plans)
        for plan in plans:
            if plan.plan_count is None:
                _issue(
                    issues,
                    seen,
                    rule_code="plan_count_missing",
                    severity="WARNING",
                    entity_type="enrollment_plan",
                    entity_id=plan.id,
                    field_name="plan_count",
                    message="招生计划数为空",
                    suggestion="补齐计划数或标记为不适用",
                )
            elif plan.plan_count <= 0:
                _issue(
                    issues,
                    seen,
                    rule_code="plan_count_invalid",
                    severity="ERROR",
                    entity_type="enrollment_plan",
                    entity_id=plan.id,
                    field_name="plan_count",
                    message=f"招生计划数 {plan.plan_count} 必须大于 0",
                    suggestion="修正计划数",
                )
            if plan.tuition is not None and (plan.tuition < 0 or plan.tuition > 200_000):
                _issue(
                    issues,
                    seen,
                    rule_code="tuition_out_of_range",
                    severity="WARNING",
                    entity_type="enrollment_plan",
                    entity_id=plan.id,
                    field_name="tuition",
                    message=f"学费 {plan.tuition} 超出合理范围",
                    suggestion="核对学费单位（元/年）",
                )

    if len(issues) >= MAX_ISSUES:
        issues.append(
            {
                "rule_code": "issue_limit_reached",
                "severity": "INFO",
                "entity_type": "job",
                "entity_id": 0,
                "field_name": "",
                "message": f"问题数量达到上限 {MAX_ISSUES}，请缩小质检范围",
                "suggestion": "按省份/院校拆分任务",
            }
        )
    return checked_rows, issues
