#!/usr/bin/env python3
"""
高考数据模块 v2.0 — 数据库优先 + 百度搜索兜底
数据查询优先级: 本地数据库(T1-T2) → 百度搜索(T4)
"""
import os, json

HERE = os.path.dirname(os.path.abspath(__file__))

# ── 招生政策库（内存字典，T1 来源） ──
POLICIES = {
    "强基计划": {
        "title": "强基计划",
        "summary": "教育部自2020年起实施，聚焦高端芯片、智能科技、新材料等关键领域。36所双一流A类高校参与，高考成绩占比不低于85%。",
        "key_points": ["报名时间一般在4月", "只能报考1所高校", "录取在提前批之前", "入校后原则上不得转专业"],
        "source": "教育部阳光高考平台"
    },
    "提前批": {
        "title": "提前批次录取",
        "summary": "在普通批次之前录取，包括军事、公安、公费师范生、定向医学生等。未被录取不影响后续批次。",
        "key_points": ["一般在6月底填报", "不影响后续批次录取", "部分有体检/面试要求"],
        "source": "各省教育考试院"
    },
    "综合评价": {
        "title": "综合评价招生",
        "summary": "综合高考成绩、校测成绩和学业水平考试成绩录取。高考成绩占比不低于60%。",
        "key_points": ["部分高校在部分省份试点", "需要额外申请和参加校测", "代表高校：南科大、上科大、昆山杜克"],
        "source": "各高校招生简章"
    },
    "专项计划": {
        "title": "高校专项计划",
        "summary": "面向农村和脱贫地区学生的定向招生，包括国家专项、地方专项和高校专项。可降5-20分录取。",
        "key_points": ["国家专项面向困难县", "地方专项面向各省农村学生", "高校专项95所高校需单独报名"],
        "source": "教育部高校招生工作规定"
    },
    "新高考": {
        "title": "新高考改革",
        "summary": "取消文理分科，实行3+1+2或3+3模式。选科组合直接影响可报专业范围。",
        "key_points": ["3+1+2：物理/历史二选一+其余四选二", "3+3：六选三", "赋分制按排名百分比赋分"],
        "source": "各省教育厅"
    },
}

# ── 尝试加载数据库层 ──
HAS_DB = False
_db_session = None
_crud = None

def _ensure_db():
    """延迟初始化数据库连接"""
    global HAS_DB, _db_session, _crud
    if HAS_DB:
        return True
    try:
        from db.database import init_db, get_session
        from db import crud as _crud_mod
        init_db()
        _db_session = get_session()
        _crud = _crud_mod
        HAS_DB = True
        return True
    except Exception:
        HAS_DB = False
        return False


def query_admission(school, province, year=2024, major=None):
    """
    查询录取数据 — 数据库优先，百度API 兜底
    返回: list of dicts（每条包含 school, province, year, min_score, min_rank, data_source 等）
    """
    results = []

    # 优先查数据库（T1 级）
    if _ensure_db():
        try:
            db_results = _crud.query_admission_from_db(
                _db_session, school, province, year=year
            )
            if db_results:
                results = db_results
        except Exception:
            pass

    # 数据库没有 → 百度高考 API（T2 级，结构化 JSON）
    if not results:
        try:
            from scrapers.baidu_gaokao import fetch_school_score
            # 根据省份选择正确的 curriculum
            _curriculums = {
                "北京": ["3+3综合"], "天津": ["3+3综合"], "上海": ["3+3综合"],
                "山东": ["3+3综合"], "海南": ["3+3综合"], "浙江": ["3+3综合"],
                "四川": ["理科", "文科"], "河南": ["理科", "文科"],
                "山西": ["理科", "文科"], "陕西": ["理科", "文科"],
                "云南": ["理科", "文科"], "内蒙古": ["理科", "文科"],
                "宁夏": ["理科", "文科"], "青海": ["理科", "文科"],
                "新疆": ["理科", "文科"],
            }
            # 其他省份默认 3+1+2（物理类/历史类）
            curriculums = _curriculums.get(province, ["物理类", "历史类"])
            for curriculum in curriculums:
                api_scores = fetch_school_score(school, province, year, curriculum)
                if api_scores:
                    for s in api_scores:
                        results.append({
                            "school": school,
                            "level": "",
                            "province": province,
                            "year": year,
                            "batch": s.get("batchName", ""),
                            "subject_type": curriculum,
                            "min_score": _safe_int(s.get("minScore")),
                            "min_rank": _safe_int(s.get("minScoreOrder")),
                            "major": s.get("majorGroup", "院校线"),
                            "data_source": f"百度高考 API（来源：中国教育在线 {year}年数据）",
                        })
                    break  # 找到就停
        except Exception:
            pass

    # 仍然没有 → 老式百度搜索（T4 级，仅供参考）
    if not results:
        try:
            from scrapers.baidu import search_admission_snippets
            snippets = search_admission_snippets(school, province, year)
            for s in snippets:
                results.append({
                    "school": school,
                    "province": province,
                    "year": year,
                    "snippet": s[:400],
                    "data_source": f"百度搜索（T4 级，仅供参考，请核实官方数据）",
                    "min_score": None,
                    "min_rank": None,
                })
        except Exception:
            pass

    return results


def _safe_int(value, default=None):
    if value in (None, "", "-", "暂无"):
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def query_yi_fen_yi_duan(province, score, subject_type="物理", year=2024):
    """
    查询一分一段表：分数 → 位次
    数据源: 数据库录取数据反推（T3 级，仅作参考）
    精确数据: 建议查省考试院官方

    返回: dict {rank: 位次, source: 数据来源, confidence: 置信度}
    """
    if not _ensure_db():
        return None

    try:
        # 智能匹配 subject_type
        subject_aliases = {
            "物理": ["物理", "物理类", "3+3综合", "综合", "理科"],
            "物理类": ["物理", "物理类", "3+3综合", "综合", "理科"],
            "物": ["物理", "物理类", "3+3综合", "综合", "理科"],
            "历史": ["历史", "历史类", "3+3综合", "综合", "文科"],
            "历史类": ["历史", "历史类", "3+3综合", "综合", "文科"],
            "史": ["历史", "历史类", "3+3综合", "综合", "文科"],
            "理科": ["物理", "物理类", "3+3综合", "综合", "理科"],
            "文科": ["历史", "历史类", "3+3综合", "综合", "文科"],
        }
        candidates = subject_aliases.get(subject_type, [subject_type])
        placeholders = ",".join(["?"] * len(candidates))

        from db.models import AdmissionScore
        query_results = _db_session.query(AdmissionScore).filter(
            AdmissionScore.province == province,
            AdmissionScore.year == year,
            AdmissionScore.subject_type.in_(candidates),
            AdmissionScore.min_score.isnot(None),
            AdmissionScore.min_rank.isnot(None),
        ).all()

        if not query_results:
            return {
                "rank": None,
                "source": "无数据",
                "confidence": "无",
                "message": f"暂无{province} {year}年{subject_type}的位次数据（建议查省考试院）",
            }

        # 构建分数-位次映射
        score_to_rank = {}
        for r in query_results:
            s = r.min_score
            rank = r.min_rank
            if s not in score_to_rank or rank < score_to_rank[s]:
                score_to_rank[s] = rank

        # 精确匹配
        if score in score_to_rank:
            return {
                "rank": score_to_rank[score],
                "score": score,
                "province": province,
                "year": year,
                "source": f"本地数据库（基于 {len(query_results)} 条录取数据反推）",
                "confidence": "中（T3 级，仅作参考）",
            }

        # 向下找最接近的分数
        sorted_desc = sorted(score_to_rank.items(), key=lambda x: -x[0])
        for s, r in sorted_desc:
            if s <= score:
                return {
                    "rank": r,
                    "score": score,
                    "matched_score": s,
                    "province": province,
                    "year": year,
                    "source": f"本地数据库（基于 {len(query_results)} 条录取数据反推，最近匹配 {s}分）",
                    "confidence": "中-低（T3 级，仅作参考）",
                }

        # 分数低于所有数据点
        return {
            "rank": sorted_desc[-1][1],
            "score": score,
            "matched_score": sorted_desc[-1][0],
            "province": province,
            "year": year,
            "source": f"本地数据库（分数低于所有录取数据，按最低分 {sorted_desc[-1][0]} 对应位次估算）",
            "confidence": "低",
        }
    except Exception as e:
        return {
            "rank": None,
            "source": "查询出错",
            "confidence": "无",
            "message": str(e),
        }


def query_match_schools_v2(score, province, subject_type, strategy="稳", year=2024):
    """
    分数匹配院校推荐 v2（基于位次法）
    冲: 位次上浮 5-15%
    稳: 位次 ±5%
    保: 位次下降 10-20%

    先用一分一段算出用户位次，再用位次匹配录取数据
    """
    if not _ensure_db():
        return []

    # Step 1: 算出用户位次
    rank_info = query_yi_fen_yi_duan(province, score, subject_type, year)
    user_rank = rank_info.get("rank") if rank_info else None
    if not user_rank:
        # 降级用原始分数匹配
        return _crud.query_match_schools(_db_session, score, province, subject_type, strategy)

    # Step 2: 根据 strategy 调整位次范围
    if strategy == "冲":
        lo_rank = int(user_rank * 0.85)
        hi_rank = user_rank
    elif strategy == "保":
        lo_rank = user_rank
        hi_rank = int(user_rank * 1.25)
    else:  # 稳
        lo_rank = int(user_rank * 0.95)
        hi_rank = int(user_rank * 1.10)

    # Step 3: 查 min_rank 在 [lo_rank, hi_rank] 之间的录取数据
    try:
        from db.models import AdmissionScore, School
        subject_aliases = {
            "物理": ["物理", "物理类", "3+3综合", "综合", "理科"],
            "物理类": ["物理", "物理类", "3+3综合", "综合", "理科"],
            "物": ["物理", "物理类", "3+3综合", "综合", "理科"],
            "历史": ["历史", "历史类", "3+3综合", "综合", "文科"],
            "历史类": ["历史", "历史类", "3+3综合", "综合", "文科"],
            "史": ["历史", "历史类", "3+3综合", "综合", "文科"],
            "理科": ["物理", "物理类", "3+3综合", "综合", "理科"],
            "文科": ["历史", "历史类", "3+3综合", "综合", "文科"],
        }
        candidates = subject_aliases.get(subject_type, [subject_type])

        rows = _db_session.query(AdmissionScore).join(School).filter(
            AdmissionScore.province == province,
            AdmissionScore.year == year,
            AdmissionScore.subject_type.in_(candidates),
            AdmissionScore.min_rank >= lo_rank,
            AdmissionScore.min_rank <= hi_rank,
            AdmissionScore.min_rank.isnot(None),
        ).limit(50).all()

        # 去重（按 school_id），每校取最低分（最易录取）那条
        seen = {}
        for r in rows:
            sid = r.school_id
            if sid not in seen or r.min_rank > seen[sid].min_rank:  # 录取位次最大 = 最好考
                seen[sid] = r

        results = []
        for r in sorted(seen.values(), key=lambda x: x.min_rank or 0, reverse=True):
            results.append({
                "school_id": r.school_id,
                "school_name": r.school.name,
                "school_level": r.school.level,
                "is_985": r.school.is_985,
                "is_211": r.school.is_211,
                "province": r.province,
                "year": r.year,
                "batch": r.batch,
                "subject_type": r.subject_type,
                "min_score": r.min_score,
                "min_rank": r.min_rank,
                "data_source": f"数据库位次法（{year}年{province}{subject_type}，用户位次 {user_rank:,}，策略 {strategy}）",
            })
        return results[:15]
    except Exception as e:
        # 出错时降级到旧版分数匹配
        return _crud.query_match_schools(_db_session, score, province, subject_type, strategy)


def query_match_schools(score, province, subject_type, strategy="稳"):
    """
    分数匹配院校推荐（冲/稳/保）
    返回: list of dicts
    """
    if _ensure_db():
        try:
            return _crud.query_match_schools(
                _db_session, score, province, subject_type, strategy
            )
        except Exception:
            pass
    return []


def query_school_info(school_name):
    """查询院校基本信息"""
    if _ensure_db():
        try:
            school = _crud.get_school_by_name(_db_session, school_name)
            if school:
                return {
                    "name": school.name,
                    "province": school.province,
                    "city": school.city,
                    "level": school.level,
                    "school_type": school.school_type,
                    "ranking": school.ranking,
                    "is_985": school.is_985,
                    "is_211": school.is_211,
                    "is_double_first_class": school.is_double_first_class,
                    "data_source": "数据库（T1 级，教育部官方名单）",
                }
        except Exception:
            pass
    return None


def query_major_info(major_name):
    """查询专业就业数据"""
    if _ensure_db():
        try:
            major = _crud.get_major_by_name(_db_session, major_name)
            if major:
                return {
                    "name": major.name,
                    "category": major.category,
                    "sub_category": major.sub_category,
                    "employment_rate": major.employment_rate,
                    "avg_salary": major.avg_salary,
                    "median_salary": major.median_salary,
                    "job_directions": major.job_directions,
                    "is_hot": major.is_hot,
                    "data_source": "数据库（T2 级，麦可思/各校就业质量报告）",
                }
        except Exception:
            pass
    return None


def query_subject_ranking(school_name, category=None):
    """查询学科排名"""
    if _ensure_db():
        try:
            school = _crud.get_school_by_name(_db_session, school_name)
            if school:
                rankings = _crud.get_subject_rankings(
                    _db_session, school_id=school.id, major_category=category
                )
                return [{
                    "school": school.name,
                    "category": r.major_category,
                    "source": r.ranking_source,
                    "year": r.ranking_year,
                    "position": r.ranking_position,
                    "grade": r.grade,
                    "data_source": f"数据库（T1 级，{r.ranking_source} {r.ranking_year}年评估）",
                } for r in rankings]
        except Exception:
            pass
    return []


def search_policy(keyword):
    """搜索招生政策"""
    matched = []
    for key, policy in POLICIES.items():
        if key in keyword or keyword in key:
            matched.append(policy)
    if not matched:
        for key, policy in POLICIES.items():
            for char in keyword:
                if char in key:
                    matched.append(policy)
                    break
            if matched:
                break
    return matched


def format_admission_info(results):
    """格式化录取数据为 Agent 可用文本（带数据来源标注）"""
    if not results:
        return "暂无该学校录取数据。建议访问各省教育考试院官网查询。"

    lines = []
    for i, r in enumerate(results[:5]):
        source = r.get("data_source", "未知来源")

        # 数据库结果（有具体分数）
        if r.get("min_score") is not None:
            major_info = r.get("major", "院校线")
            score_info = f"最低分{r['min_score']}"
            rank_info = f"位次{r['min_rank']}" if r.get("min_rank") else ""
            lines.append(
                f"{i+1}. {r.get('school','')}({r.get('level','')}) {major_info} | "
                f"{r.get('province','')} {r.get('year','')}年 {r.get('subject_type','')} | "
                f"{score_info} {rank_info} | 来源：{source}"
            )
        # 百度搜索结果（只有文本片段）
        elif r.get("snippet"):
            lines.append(f"{i+1}. {r['snippet'][:300]} | 来源：{source}")

    return "\n".join(lines) if lines else "暂无该学校录取数据。"


def get_db_stats():
    """获取数据库统计信息"""
    if _ensure_db():
        try:
            db = _db_session
            from db.models import School, Major, AdmissionScore, SubjectRanking
            return {
                "schools": db.query(School).count(),
                "majors": db.query(Major).count(),
                "admission_scores": db.query(AdmissionScore).count(),
                "subject_rankings": db.query(SubjectRanking).count(),
                "policies": len(POLICIES),
            }
        except Exception:
            pass
    return {"status": "数据库不可用"}


if __name__ == "__main__":
    print("=== 数据模块测试 ===\n")

    stats = get_db_stats()
    print(f"数据库统计: {json.dumps(stats, ensure_ascii=False, indent=2)}\n")

    print("测试: 武汉大学 湖北 2024")
    results = query_admission("武汉大学", "湖北", 2024)
    print(format_admission_info(results))

    print("\n测试: 计算机科学与技术 专业信息")
    info = query_major_info("计算机科学与技术")
    if info:
        print(json.dumps(info, ensure_ascii=False, indent=2))

    print("\n测试: 分数匹配 600分 湖北 物理类 稳")
    matches = query_match_schools(600, "湖北", "物理类", "稳")
    for m in matches[:5]:
        print(f"  {m.get('school_name','')} - {m.get('min_score','')}分 {m.get('min_rank','')}位次")
