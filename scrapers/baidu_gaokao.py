#!/usr/bin/env python3
"""
百度高考 API 采集器 — 公开无认证，来源等级 T2
对接 db/models.py 的 ORM，直接灌库。

API 端点（实测可用）：
- 院校列表:  https://gaokao.baidu.com/gk/gkschool/list?rn=N&pn=P
- 院校分数线: https://gaokao.baidu.com/gk/gkschool/schoolscore?curriculum=X&school=X&province=X&year=X
- 专业分数线: https://gaokao.baidu.com/gk/gkschool/majorscore?rn=N&school=X&province=X&year=X&pn=P
- 招生计划:   https://gaokao.baidu.com/gk/gkschool/getrecruitingscheme?curriculum=X&school=X&province=X&year=X

数据来源: 百度高考 (gaokao.baidu.com)，底层数据由中国教育在线提供
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from collections.abc import Iterator

# 确保项目根目录在 path 中
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from utils import safe_int

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://gaokao.baidu.com/",
}

BASE_URL = "https://gaokao.baidu.com"
PAGE_SIZE = 20
DELAY = 0.2  # 秒，请求间隔（从 0.4 降至 0.2，平衡速度与限频）


def _fetch_json(url: str, retries: int = 3) -> dict | None:
    """通用 JSON 请求，带重试"""
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8", errors="ignore"))
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(1.5 * (attempt + 1))
            else:
                print(f"  [WARN] 请求失败 ({attempt+1}/{retries}): {url[:80]}... | {e}")
                return None
    return None


# ══════════════════════════════════════════════════════════
# 1. 院校列表采集
# ══════════════════════════════════════════════════════════

def fetch_school_list(page: int = 1, rn: int = PAGE_SIZE) -> dict | None:
    """获取院校列表（分页）"""
    url = f"{BASE_URL}/gk/gkschool/list?rn={rn}&pn={page}"
    return _fetch_json(url)


def iter_schools() -> Iterator[dict]:
    """迭代获取全部院校（约 3000+ 所）"""
    page = 1
    while True:
        data = fetch_school_list(page=page, rn=50)
        if not data or "data" not in data:
            break
        items = data["data"].get("ranking", {}).get("tRow", [])
        if not items:
            break
        for item in items:
            yield item
        page_info = data["data"].get("pageInfo", {})
        if not page_info.get("hasNext"):
            break
        page += 1
        time.sleep(DELAY)


# ══════════════════════════════════════════════════════════
# 2. 录取分数线采集
# ══════════════════════════════════════════════════════════

def fetch_school_score(school: str, province: str, year: int = 2024,
                       curriculum: str = "3+3综合") -> list[dict]:
    """获取某学校在某省的录取分数线（不分页，最多20条）"""
    params = {
        "curriculum": curriculum,
        "school": school,
        "province": province,
        "year": str(year),
    }
    url = f"{BASE_URL}/gk/gkschool/schoolscore?" + urllib.parse.urlencode(params)
    data = _fetch_json(url)
    if not data or "data" not in data:
        return []
    score_data = data["data"].get("school_score", {})
    return score_data.get("dataList", [])


# ══════════════════════════════════════════════════════════
# 3. 专业分数线采集（分页）
# ══════════════════════════════════════════════════════════

def fetch_major_score(school: str, province: str, year: int = 2024,
                      page: int = 1, rn: int = 50) -> list[dict]:
    """获取某学校在某省的专业录取分数线"""
    params = {
        "rn": rn,
        "school": school,
        "province": province,
        "year": str(year),
        "pn": page,
    }
    url = f"{BASE_URL}/gk/gkschool/majorscore?" + urllib.parse.urlencode(params)
    data = _fetch_json(url)
    if not data or "data" not in data:
        return []
    major_data = data["data"].get("major_score", {})
    return major_data.get("dataList", [])


# ══════════════════════════════════════════════════════════
# 4. 招生计划采集
# ══════════════════════════════════════════════════════════

def fetch_enrollment_plan(school: str, province: str, year: int = 2024,
                          page: int = 1, rn: int = 50) -> list[dict]:
    """获取某学校在某省的招生计划"""
    # 根据省份自动选 curriculum（百度 API 需要精确匹配）
    PROVINCE_CURRICULUM = {
        "北京": "3+3综合", "天津": "3+3综合", "上海": "3+3综合",
        "山东": "3+3综合", "海南": "3+3综合", "浙江": "3+3综合",
    }
    curriculum = PROVINCE_CURRICULUM.get(province, "物理类")  # 其他省默认物理类

    params = {
        "curriculum": curriculum,
        "school": school,
        "province": province,
        "year": str(year),
        "pn": page,
        "rn": rn,
    }
    url = f"{BASE_URL}/gk/gkschool/getrecruitingscheme?" + urllib.parse.urlencode(params)
    data = _fetch_json(url)
    if not data or "data" not in data:
        return []
    return data["data"].get("list", [])


# ══════════════════════════════════════════════════════════
# 5. 数据解析工具
# ══════════════════════════════════════════════════════════

TAG_LEVEL_MAP = {
    "985": ("985", 1, 1, 1),
    "211": ("211", 0, 1, 1),
    "双一流": ("双一流", 0, 0, 1),
}

def parse_school_tags(tags: list) -> tuple:
    """从 tag 数组解析 level / is_985 / is_211 / is_dfc"""
    is_985 = is_211 = is_dfc = 0
    level = "普通"
    for tag in tags or []:
        if tag == "985":
            is_985 = is_211 = is_dfc = 1
            level = "985"
        elif tag == "211" and not is_985:
            is_211 = is_dfc = 1
            level = "211"
        elif tag == "双一流" and not is_985 and not is_211:
            is_dfc = 1
            level = "双一流"
    return level, is_985, is_211, is_dfc


# ══════════════════════════════════════════════════════════
# 6. 导入数据库
# ══════════════════════════════════════════════════════════

def import_schools_to_db(db_session, School, max_schools: int = None,
                         skip_existing: bool = True) -> dict:
    """导入院校列表到数据库。返回统计信息。
    skip_existing=True 时，只填充空字段（city, ranking, description），不覆盖已有数据。
    """
    stats = {"fetched": 0, "new": 0, "updated": 0, "skipped": 0}
    print(f"\n[院校列表] 开始采集（最多 {max_schools or '全部'} 所）...")

    for item in iter_schools():
        stats["fetched"] += 1
        if max_schools and stats["new"] + stats["updated"] >= max_schools:
            break

        name = item.get("college_name", "").strip()
        if not name:
            stats["skipped"] += 1
            continue

        level, is_985, is_211, is_dfc = parse_school_tags(item.get("tag", []))

        existing = db_session.query(School).filter(School.name == name).first()
        if existing:
            if skip_existing:
                # 增量更新：只填充空字段，不覆盖已有数据
                api_city = item.get("city", "") or item.get("location", "")
                if not existing.city and api_city:
                    existing.city = api_city
                api_rank = safe_int(item.get("rank"))
                if not existing.ranking and api_rank:
                    existing.ranking = api_rank
                api_tags = item.get("tag", [])
                api_desc = item.get("tag_text") or ("、".join(api_tags) if api_tags else "")
                if not existing.description and api_desc:
                    existing.description = api_desc
                # province 和 school_type 始终同步（API 是权威来源）
                if item.get("province"):
                    existing.province = item["province"]
                if item.get("school_type"):
                    existing.school_type = item["school_type"]
                stats["updated"] += 1
            else:
                stats["skipped"] += 1
        else:
            tags = item.get("tag", [])
            school = School(
                name=name,
                province=item.get("province", ""),
                city=item.get("city", "") or item.get("location", ""),
                level=level,
                school_type=item.get("school_type", "综合"),
                ranking=safe_int(item.get("rank")),
                is_985=is_985,
                is_211=is_211,
                is_double_first_class=is_dfc,
                description="、".join(tags) if tags else "",
            )
            db_session.add(school)
            stats["new"] += 1

        # 每 50 条 commit 一次
        if (stats["new"] + stats["updated"]) % 50 == 0:
            db_session.commit()
            print(f"  进度: {stats['new']} 新增 / {stats['updated']} 更新 / {stats['fetched']} 已扫描")

    db_session.commit()
    print(f"[完成] 院校: 新增 {stats['new']} / 更新 {stats['updated']} / 总扫描 {stats['fetched']}")
    return stats


def import_scores_to_db(db_session, School, AdmissionScore,
                        schools: list = None, provinces: list = None,
                        years: list = None, max_per_school: int = 50,
                        checkpoint_path: str = None,
                        start_school_index: int = 0,
                        on_progress: callable = None) -> dict:
    """为指定学校采集录取分数线。

    Args:
        schools: 目标学校 ORM 对象列表
        provinces: 省份列表，None 则用 ALL_PROVINCES
        years: 年份列表，None 则 [2024, 2023, 2022]
        max_per_school: 每校最多保留的分数线条数
        checkpoint_path: 断点文件路径，非 None 则每 10 校自动保存
        start_school_index: 从第几所学校开始（断点续传用）
        on_progress: 回调函数 (school_index, total, stats) -> None

    返回: 统计信息 dict
    """
    from scrapers.provinces import ALL_PROVINCES, PROVINCE_CURRICULUMS

    if provinces is None:
        provinces = ALL_PROVINCES
    if years is None:
        years = [2024, 2023, 2022]

    stats = {"requests": 0, "new_scores": 0, "errors": 0}
    total = len(schools)
    print(f"\n[录取分数线] 开始采集: {total}校 × {len(provinces)}省 × {len(years)}年")

    for idx, school in enumerate(schools):
        actual_idx = start_school_index + idx

        for province in provinces:
            for year in years:
                curriculums = PROVINCE_CURRICULUMS.get(province, ["物理类", "历史类"])
                for curriculum in curriculums:
                    # 快速跳过：如果该校在此省份+年份+curriculum已有数据，跳过API调用
                    existing_count = db_session.query(AdmissionScore).filter(
                        AdmissionScore.school_id == school.id,
                        AdmissionScore.province == province,
                        AdmissionScore.year == year,
                        AdmissionScore.subject_type == curriculum,
                    ).count()
                    if existing_count > 0:
                        stats["requests"] += 0  # 不计入请求统计
                        continue

                    try:
                        scores = fetch_school_score(
                            school.name, province, year, curriculum
                        )
                        stats["requests"] += 1
                        if not scores:
                            time.sleep(DELAY / 2)
                            continue

                        for s in scores[:max_per_school]:
                            min_score = safe_int(s.get("minScore"))
                            if min_score is None:
                                continue
                            min_rank = safe_int(s.get("minScoreOrder"))

                            existing = db_session.query(AdmissionScore).filter(
                                AdmissionScore.school_id == school.id,
                                AdmissionScore.province == province,
                                AdmissionScore.year == year,
                                AdmissionScore.batch == s.get("batchName", "本科批"),
                                AdmissionScore.subject_type == curriculum,
                                AdmissionScore.major_id.is_(None),
                            ).first()

                            if not existing:
                                as_rec = AdmissionScore(
                                    school_id=school.id,
                                    major_id=None,
                                    province=province,
                                    year=year,
                                    batch=s.get("batchName", "本科批"),
                                    subject_type=curriculum,
                                    min_score=min_score,
                                    min_rank=min_rank,
                                    plan_count=safe_int(s.get("enrollNum")),
                                )
                                db_session.add(as_rec)
                                stats["new_scores"] += 1

                        db_session.commit()
                        time.sleep(DELAY)

                    except Exception as e:
                        stats["errors"] += 1
                        # 安全获取学校名（session 可能已损坏）
                        school_name = getattr(school, "name", "unknown")
                        print(f"  [ERROR] {school_name} {province} {year}: {e}")
                        # WSL2 transient OperationalError 后尝试安全回滚
                        try:
                            db_session.rollback()
                        except Exception:
                            pass
                        continue

        # 定期保存断点
        if checkpoint_path and (idx + 1) % 10 == 0:
            from scrapers.checkpoint import save_checkpoint
            save_checkpoint(checkpoint_path, {
                "last_run": __import__("datetime").datetime.now().isoformat(),
                "school_index": actual_idx + 1,
                "total_schools": total,
                "current_school": school.name,
                "stats": stats,
            })

        if on_progress:
            on_progress(actual_idx + 1, total, stats)
        else:
            print(f"  [{actual_idx+1}/{total}] {school.name}: {stats['new_scores']} 条新增")

    # 最终保存断点
    if checkpoint_path:
        from scrapers.checkpoint import save_checkpoint
        save_checkpoint(checkpoint_path, {
            "last_run": __import__("datetime").datetime.now().isoformat(),
            "school_index": start_school_index + total,
            "total_schools": total,
            "current_school": schools[-1].name if schools else "",
            "stats": stats,
        })

    print(f"[完成] 录取分数线: 新增 {stats['new_scores']} / 请求 {stats['requests']} / 错误 {stats['errors']}")
    return stats


# ══════════════════════════════════════════════════════════
# 7. 主入口
# ══════════════════════════════════════════════════════════

if __name__ == "__main__":
    from db.database import get_session, init_db
    init_db()
    db = get_session()

    print("=" * 60)
    print("  百度高考 API 数据采集器")
    print("=" * 60)

    # 测试：拉取前 2 页
    print("\n[测试] 拉取前 2 页院校列表...")
    schools = []
    for i, item in enumerate(iter_schools()):
        schools.append(item)
        if i >= 5:
            break
    print(f"  拉取到 {len(schools)} 所院校（示例）:")
    for s in schools[:3]:
        print(f"    - {s.get('college_name')} ({s.get('province')}/{s.get('school_type')}) tags={s.get('tag', [])}")

    # 测试：拉取某校分数线
    if schools:
        name = schools[0].get("college_name")
        print(f"\n[测试] 拉取 {name} 2024年 北京 录取分数线...")
        scores = fetch_school_score(name, "北京", 2024)
        print(f"  拉取到 {len(scores)} 条")
        for s in scores[:3]:
            print(f"    - {s.get('batchName')}/{s.get('majorGroup')} minScore={s.get('minScore')} rank={s.get('minScoreOrder')}")
