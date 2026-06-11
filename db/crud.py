"""
CRUD 操作 — 数据库查询层
"""
import json
from typing import Optional
from sqlalchemy.orm import Session
from db.models import School, Major, AdmissionScore, EnrollmentPlan, SubjectRanking

# ── 院校查询 ──

def get_school_by_name(db: Session, name: str) -> Optional[School]:
    """精确匹配院校（支持模糊：先精确，再 LIKE）"""
    school = db.query(School).filter(School.name == name).first()
    if school:
        return school
    return db.query(School).filter(School.name.contains(name)).first()


def get_schools_by_province(db: Session, province: str) -> list:
    return db.query(School).filter(School.province == province).all()


def get_schools_by_level(db: Session, level: str) -> list:
    return db.query(School).filter(School.level == level).all()


# ── 专业查询 ──

def get_major_by_name(db: Session, name: str) -> Optional[Major]:
    major = db.query(Major).filter(Major.name == name).first()
    if major:
        return major
    return db.query(Major).filter(Major.name.contains(name)).first()


def get_hot_majors(db: Session, limit: int = 20) -> list:
    return db.query(Major).filter(Major.is_hot == 1).order_by(
        Major.avg_salary.desc().nullslast()
    ).limit(limit).all()


def get_majors_by_category(db: Session, category: str) -> list:
    return db.query(Major).filter(Major.category == category).all()


# ── 录取分数线查询 ──

def get_admission_scores(
    db: Session,
    school_id: Optional[int] = None,
    province: Optional[str] = None,
    year: Optional[int] = None,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    subject_type: Optional[str] = None,
    min_score_floor: Optional[int] = None,
    max_score_ceil: Optional[int] = None,
    limit: int = 50,
) -> list[dict]:
    """多条件查询录取分数线"""
    q = db.query(AdmissionScore).join(School, AdmissionScore.school_id == School.id)
    q = q.outerjoin(Major, AdmissionScore.major_id == Major.id)

    if school_id:
        q = q.filter(AdmissionScore.school_id == school_id)
    if province:
        q = q.filter(AdmissionScore.province == province)
    if year:
        q = q.filter(AdmissionScore.year == year)
    if year_from:
        q = q.filter(AdmissionScore.year >= year_from)
    if year_to:
        q = q.filter(AdmissionScore.year <= year_to)
    if subject_type:
        q = q.filter(AdmissionScore.subject_type == subject_type)
    if min_score_floor is not None:
        q = q.filter(AdmissionScore.min_score >= min_score_floor)
    if max_score_ceil is not None:
        q = q.filter(AdmissionScore.min_score <= max_score_ceil)

    rows = q.order_by(AdmissionScore.year.desc(), AdmissionScore.min_score.desc()).limit(limit).all()

    return [{
        "id": r.id,
        "school_id": r.school_id,
        "major_id": r.major_id,
        "school_name": r.school.name if r.school else None,
        "major_name": r.major.name if r.major else None,
        "province": r.province,
        "year": r.year,
        "batch": r.batch,
        "subject_type": r.subject_type,
        "min_score": r.min_score,
        "avg_score": r.avg_score,
        "max_score": r.max_score,
        "min_rank": r.min_rank,
        "plan_count": r.plan_count,
    } for r in rows]


def get_scores_by_school(db: Session, school_id: int,
                         province: Optional[str] = None,
                         year: Optional[int] = None) -> list:
    q = db.query(AdmissionScore).filter(AdmissionScore.school_id == school_id)
    if province:
        q = q.filter(AdmissionScore.province == province)
    if year:
        q = q.filter(AdmissionScore.year == year)
    return q.order_by(AdmissionScore.year.desc()).all()


# ── 招生计划查询 ──

def get_enrollment_plans(db: Session,
                         school_id: Optional[int] = None,
                         major_id: Optional[int] = None,
                         province: Optional[str] = None,
                         year: Optional[int] = None) -> list:
    q = db.query(EnrollmentPlan)
    if school_id:
        q = q.filter(EnrollmentPlan.school_id == school_id)
    if major_id:
        q = q.filter(EnrollmentPlan.major_id == major_id)
    if province:
        q = q.filter(EnrollmentPlan.province == province)
    if year:
        q = q.filter(EnrollmentPlan.year == year)
    return q.all()


# ── 学科排名查询 ──

def get_subject_rankings(db: Session,
                         school_id: Optional[int] = None,
                         major_category: Optional[str] = None) -> list:
    q = db.query(SubjectRanking)
    if school_id:
        q = q.filter(SubjectRanking.school_id == school_id)
    if major_category:
        q = q.filter(SubjectRanking.major_category == major_category)
    return q.all()


# ── 策略性查询（给 agent 用）──

def query_admission_from_db(db: Session, school_name: str, province: str,
                            year: Optional[int] = None) -> list[dict]:
    """根据学校名+省份查录取数据，返回格式化结果"""
    school = get_school_by_name(db, school_name)
    if not school:
        return []

    scores = get_scores_by_school(db, school.id, province=province, year=year)
    results = []
    for s in scores:
        major = db.query(Major).filter(Major.id == s.major_id).first() if s.major_id else None
        results.append({
            "school": school.name,
            "level": school.level,
            "province": s.province,
            "year": s.year,
            "batch": s.batch,
            "subject_type": s.subject_type,
            "min_score": s.min_score,
            "avg_score": s.avg_score,
            "min_rank": s.min_rank,
            "major": major.name if major else "院校线",
            "data_source": f"数据库（来源：{school.name}官方/省考试院 {s.year}年数据）",
        })
    return results


def query_match_schools(db: Session, score: int, province: str,
                        subject_type: str, strategy: str = "稳") -> list[dict]:
    """分数匹配院校推荐（冲/稳/保）"""
    if strategy == "冲":
        lo, hi = score, score + 30
    elif strategy == "保":
        lo, hi = score - 60, score
    else:  # 稳
        lo, hi = score - 20, score + 10

    rows = get_admission_scores(
        db, province=province, subject_type=subject_type,
        min_score_floor=lo, max_score_ceil=hi, limit=30
    )

    seen = set()
    results = []
    for r in rows:
        sid = r["school_id"]
        if sid in seen:
            continue
        seen.add(sid)
        results.append(r)

    results.sort(key=lambda x: x["min_score"] or 0, reverse=True)
    return results[:15]


def format_admission_info_db(results: list[dict]) -> str:
    """将数据库查询结果格式化为 Agent 可用文本（带来源标注）"""
    if not results:
        return ""

    lines = ["以下为数据库中的录取参考数据：\n"]
    for i, r in enumerate(results[:5]):
        major_info = r.get("major", "院校线")
        score_info = f"最低分{r['min_score']}" if r.get("min_score") else ""
        rank_info = f"最低位次{r['min_rank']}" if r.get("min_rank") else ""
        source = r.get("data_source", "数据库")
        lines.append(
            f"{i+1}. {r['school']}({r.get('level','')}) {major_info} | "
            f"{r['province']} {r['year']}年 {r.get('subject_type','')} | "
            f"{score_info} {rank_info} | 来源：{source}"
        )
    return "\n".join(lines)
