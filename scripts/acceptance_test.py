#!/usr/bin/env python3
"""
数据验收脚本 — 全面检查数据完整性、准确性、关联性、时效性、业务场景

用法:
  python scripts/acceptance_test.py                    # 全部检查
  python scripts/acceptance_test.py --module integrity  # 只检查完整性
  python scripts/acceptance_test.py --module accuracy   # 只检查准确性
  python scripts/acceptance_test.py --module relation   # 只检查关联性
  python scripts/acceptance_test.py --module timeliness # 只检查时效性
  python scripts/acceptance_test.py --module business   # 只检查业务场景
  python scripts/acceptance_test.py --module security   # 只检查安全
  python scripts/acceptance_test.py --report            # 生成报告文件
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from db.database import get_session, init_db
from db.models import (
    AdmissionScore,
    EnrollmentPlan,
    Major,
    School,
    SubjectRanking,
    YiFenYiDuan,
)
from sqlalchemy import func, text

from scrapers.provinces import ALL_PROVINCES

REPORT_DIR = os.path.join(PROJECT_ROOT, "docs", "acceptance")


class AcceptanceReport:
    """验收报告收集器"""

    def __init__(self):
        self.results = {}
        self.summary = {"pass": 0, "fail": 0, "warn": 0}
        self.timestamp = datetime.now().isoformat()

    def add_result(self, module: str, check: str, status: str, detail: str = "", data: dict = None):
        """添加检查结果。status: PASS/FAIL/WARN"""
        if module not in self.results:
            self.results[module] = []
        self.results[module].append(
            {
                "check": check,
                "status": status,
                "detail": detail,
                "data": data or {},
            }
        )
        self.summary[status.lower()] += 1

    def print_report(self):
        """打印报告到终端"""
        print("\n" + "=" * 70)
        print("  数据验收报告")
        print(f"  时间: {self.timestamp}")
        print("=" * 70)

        for module, checks in self.results.items():
            print(f"\n{'─' * 70}")
            print(f"  [{module}]")
            print(f"{'─' * 70}")
            for c in checks:
                icon = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️"}[c["status"]]
                print(f"  {icon} {c['check']}: {c['detail']}")

        print(f"\n{'=' * 70}")
        print(f"  汇总: ✅ {self.summary['pass']} | ❌ {self.summary['fail']} | ⚠️ {self.summary['warn']}")
        total = sum(self.summary.values())
        pass_rate = self.summary["pass"] / total * 100 if total > 0 else 0
        print(f"  通过率: {pass_rate:.1f}%")
        print(f"{'=' * 70}")

    def save_report(self):
        """保存报告为文件"""
        os.makedirs(REPORT_DIR, exist_ok=True)
        filename = f"acceptance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        filepath = os.path.join(REPORT_DIR, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("# 数据验收报告\n\n")
            f.write(f"> 时间: {self.timestamp}\n\n")

            for module, checks in self.results.items():
                f.write(f"## {module}\n\n")
                f.write("| 状态 | 检查项 | 详情 |\n")
                f.write("|------|--------|------|\n")
                for c in checks:
                    icon = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️"}[c["status"]]
                    f.write(f"| {icon} | {c['check']} | {c['detail']} |\n")
                f.write("\n")

            f.write(f"## 汇总\n\n")
            f.write(f"- ✅ 通过: {self.summary['pass']}\n")
            f.write(f"- ❌ 失败: {self.summary['fail']}\n")
            f.write(f"- ⚠️ 警告: {self.summary['warn']}\n")
            total = sum(self.summary.values())
            pass_rate = self.summary["pass"] / total * 100 if total > 0 else 0
            f.write(f"- 通过率: {pass_rate:.1f}%\n")

        print(f"\n报告已保存: {filepath}")
        return filepath


# ── 模块1: 数据完整性 ──


def check_integrity(db, report: AcceptanceReport):
    """模块1: 数据完整性验收"""
    module = "数据完整性"

    # 1.1 省份覆盖
    provinces_with_data = set(r[0] for r in db.query(AdmissionScore.province).distinct().all())
    expected_provinces = set(ALL_PROVINCES) | {"西藏"}
    missing = expected_provinces - provinces_with_data
    if not missing:
        report.add_result(module, "省份覆盖", "PASS", f"全部 {len(expected_provinces)} 省覆盖")
    else:
        report.add_result(module, "省份覆盖", "FAIL", f"缺失: {', '.join(missing)}")

    # 1.2 年份覆盖
    years = sorted(r[0] for r in db.query(AdmissionScore.year).distinct().all())
    expected_years = [2022, 2023, 2024, 2025]
    missing_years = set(expected_years) - set(years)
    if not missing_years:
        report.add_result(module, "年份覆盖", "PASS", f"覆盖 {years}")
    else:
        report.add_result(module, "年份覆盖", "FAIL", f"缺失年份: {missing_years}")

    # 1.3 2025年各省数据量 vs 2024年
    low_ratio_provinces = []
    for province, in db.query(AdmissionScore.province).distinct().all():
        c24 = db.query(AdmissionScore).filter(AdmissionScore.province == province, AdmissionScore.year == 2024).count()
        c25 = db.query(AdmissionScore).filter(AdmissionScore.province == province, AdmissionScore.year == 2025).count()
        if c24 > 100 and c25 / c24 < 0.8:
            low_ratio_provinces.append(f"{province}({c25/c24*100:.0f}%)")

    if not low_ratio_provinces:
        report.add_result(module, "2025年数据充足率", "PASS", "所有省2025年 ≥ 2024年的80%")
    else:
        report.add_result(module, "2025年数据充足率", "FAIL", f"不足80%的省份: {', '.join(low_ratio_provinces)}")

    # 1.4 西藏数据量
    tibet_count = db.query(AdmissionScore).filter(AdmissionScore.province == "西藏").count()
    if tibet_count >= 2000:
        report.add_result(module, "西藏数据量", "PASS", f"{tibet_count:,} 条")
    elif tibet_count >= 100:
        report.add_result(module, "西藏数据量", "WARN", f"{tibet_count:,} 条 (目标≥2,000)")
    else:
        report.add_result(module, "西藏数据量", "FAIL", f"{tibet_count:,} 条 (目标≥2,000)")

    # 1.5 专业级分数线覆盖率
    total_scores = db.query(AdmissionScore).count()
    major_scores = db.query(AdmissionScore).filter(AdmissionScore.major_id.isnot(None)).count()
    ratio = major_scores / total_scores * 100 if total_scores > 0 else 0
    if ratio >= 30:
        report.add_result(module, "专业级分数线覆盖率", "PASS", f"{ratio:.1f}%")
    elif ratio >= 10:
        report.add_result(module, "专业级分数线覆盖率", "WARN", f"{ratio:.1f}% (目标≥30%)")
    else:
        report.add_result(module, "专业级分数线覆盖率", "FAIL", f"{ratio:.1f}% (目标≥30%)")

    # 1.6 一分一段表完整性
    score_combos = set(db.query(AdmissionScore.province, AdmissionScore.year).distinct().all())
    yfyd_combos = set(db.query(YiFenYiDuan.province, YiFenYiDuan.year).distinct().all())
    missing_yfyd = score_combos - yfyd_combos
    if not missing_yfyd:
        report.add_result(module, "一分一段表完整性", "PASS", "全部覆盖")
    else:
        report.add_result(module, "一分一段表完整性", "FAIL", f"缺失 {len(missing_yfyd)} 个组合")

    # 1.7 院校排名覆盖率
    total_schools = db.query(School).count()
    with_ranking = db.query(School).filter(School.ranking.isnot(None)).count()
    top_with_ranking = (
        db.query(School)
        .filter((School.is_985 == 1) | (School.is_211 == 1), School.ranking.isnot(None))
        .count()
    )
    top_total = db.query(School).filter((School.is_985 == 1) | (School.is_211 == 1)).count()
    top_pct = top_with_ranking / top_total * 100 if top_total > 0 else 0
    overall_pct = with_ranking / total_schools * 100 if total_schools > 0 else 0
    if top_pct >= 100 and overall_pct >= 40:
        report.add_result(module, "院校排名覆盖率", "PASS", f"985/211: {top_pct:.0f}%, 总体: {overall_pct:.1f}%")
    else:
        report.add_result(module, "院校排名覆盖率", "FAIL", f"985/211: {top_pct:.0f}% (目标100%), 总体: {overall_pct:.1f}%")

    # 1.8 学科排名数量
    sr_count = db.query(SubjectRanking).count()
    sr_schools = db.query(SubjectRanking.school_id).distinct().count()
    if sr_count >= 1000:
        report.add_result(module, "学科排名数量", "PASS", f"{sr_count} 条, 覆盖 {sr_schools} 所院校")
    else:
        report.add_result(module, "学科排名数量", "WARN", f"{sr_count} 条 (目标≥1,000), 覆盖 {sr_schools} 所院校")


# ── 模块2: 数据准确性 ──


def check_accuracy(db, report: AcceptanceReport):
    """模块2: 数据准确性验收"""
    module = "数据准确性"

    # 2.1 分数合理性
    bad_scores = (
        db.query(AdmissionScore)
        .filter(
            (AdmissionScore.min_score < 60)
            | ((AdmissionScore.min_score > 750) & (AdmissionScore.province != "海南"))
        )
        .count()
    )
    if bad_scores == 0:
        report.add_result(module, "分数合理性", "PASS", "0条越界")
    else:
        report.add_result(module, "分数合理性", "FAIL", f"{bad_scores}条越界")

    # 2.2 位次缺失率
    total = db.query(AdmissionScore).count()
    null_rank = db.query(AdmissionScore).filter(AdmissionScore.min_rank.is_(None)).count()
    rank_null_rate = null_rank / total * 100 if total > 0 else 0
    if rank_null_rate <= 2:
        report.add_result(module, "位次缺失率", "PASS", f"{rank_null_rate:.2f}%")
    elif rank_null_rate <= 5:
        report.add_result(module, "位次缺失率", "WARN", f"{rank_null_rate:.2f}%")
    else:
        report.add_result(module, "位次缺失率", "FAIL", f"{rank_null_rate:.2f}% (目标≤2%)")

    # 2.3 院校省份缺失
    null_province = db.query(School).filter((School.province.is_(None)) | (School.province == "")).count()
    if null_province == 0:
        report.add_result(module, "院校省份完整性", "PASS", "0所缺省份")
    else:
        report.add_result(module, "院校省份完整性", "FAIL", f"{null_province}所缺省份")

    # 2.4 完全重复检测
    dupes = db.execute(
        text("""
        SELECT school_id, province, year, subject_type, batch, major_id, COUNT(*) as cnt
        FROM admission_scores
        GROUP BY school_id, province, year, subject_type, batch, major_id
        HAVING cnt > 1
        LIMIT 1
    """)
    ).fetchone()
    if not dupes:
        report.add_result(module, "重复数据检测", "PASS", "0条完全重复")
    else:
        dupe_count = db.execute(
            text("""
            SELECT SUM(cnt - 1) FROM (
                SELECT COUNT(*) as cnt FROM admission_scores
                GROUP BY school_id, province, year, subject_type, batch, major_id
                HAVING cnt > 1
            )
        """)
        ).fetchone()[0]
        report.add_result(module, "重复数据检测", "FAIL", f"{dupe_count}条完全重复")

    # 2.5 科类名称异常
    abnormal_types = (
        db.query(AdmissionScore.subject_type, func.count(AdmissionScore.id))
        .filter(
            AdmissionScore.subject_type.notin_(["物理类", "历史类", "3+3综合", "理科", "文科", "综合"])
        )
        .group_by(AdmissionScore.subject_type)
        .all()
    )
    if not abnormal_types:
        report.add_result(module, "科类名称标准性", "PASS", "无异常科类")
    else:
        details = ", ".join(f"{t}:{c}" for t, c in abnormal_types)
        report.add_result(module, "科类名称标准性", "WARN", f"异常科类: {details}")


# ── 模块4: 数据关联性 ──


def check_relation(db, report: AcceptanceReport):
    """模块4: 数据关联性验收"""
    module = "数据关联性"

    # 4.1 悬空 major_id
    orphan_majors = db.execute(
        text("""
        SELECT COUNT(*) FROM admission_scores a
        LEFT JOIN majors m ON a.major_id = m.id
        WHERE a.major_id IS NOT NULL AND m.id IS NULL
    """)
    ).fetchone()[0]
    if orphan_majors == 0:
        report.add_result(module, "专业引用完整性", "PASS", "0条悬空 major_id")
    else:
        report.add_result(module, "专业引用完整性", "FAIL", f"{orphan_majors}条悬空 major_id")

    # 4.2 悬空 school_id
    orphan_schools = db.execute(
        text("""
        SELECT COUNT(*) FROM admission_scores a
        LEFT JOIN schools s ON a.school_id = s.id
        WHERE s.id IS NULL
    """)
    ).fetchone()[0]
    if orphan_schools == 0:
        report.add_result(module, "院校引用完整性", "PASS", "0条悬空 school_id")
    else:
        report.add_result(module, "院校引用完整性", "FAIL", f"{orphan_schools}条悬空 school_id")

    # 4.3 招生计划引用完整性
    orphan_ep_schools = db.execute(
        text("""
        SELECT COUNT(*) FROM enrollment_plans e
        LEFT JOIN schools s ON e.school_id = s.id
        WHERE s.id IS NULL
    """)
    ).fetchone()[0]
    orphan_ep_majors = db.execute(
        text("""
        SELECT COUNT(*) FROM enrollment_plans e
        LEFT JOIN majors m ON e.major_id = m.id
        WHERE m.id IS NULL
    """)
    ).fetchone()[0]
    if orphan_ep_schools == 0 and orphan_ep_majors == 0:
        report.add_result(module, "招生计划引用完整性", "PASS", "0条悬空引用")
    else:
        report.add_result(
            module, "招生计划引用完整性", "FAIL", f"悬空school_id: {orphan_ep_schools}, 悬空major_id: {orphan_ep_majors}"
        )

    # 4.4 无分数数据的院校
    total_schools = db.query(School).count()
    schools_with_scores = db.query(AdmissionScore.school_id).distinct().count()
    no_score_count = total_schools - schools_with_scores
    no_score_pct = no_score_count / total_schools * 100 if total_schools > 0 else 0
    if no_score_pct <= 2:
        report.add_result(module, "院校-分数线关联", "PASS", f"{no_score_count}所无分数 ({no_score_pct:.1f}%)")
    else:
        report.add_result(module, "院校-分数线关联", "WARN", f"{no_score_count}所无分数 ({no_score_pct:.1f}%, 目标≤2%)")


# ── 模块3: 数据时效性 ──


def check_timeliness(db, report: AcceptanceReport):
    """模块3: 数据时效性验收"""
    module = "数据时效性"

    # 3.1 数据新鲜度 - 数据库最后修改时间
    db_path = os.path.join(PROJECT_ROOT, "data", "gaokao.db")
    if os.path.exists(db_path):
        mtime = os.path.getmtime(db_path)
        last_modified = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
        report.add_result(module, "数据库最后更新", "PASS", last_modified)
    else:
        report.add_result(module, "数据库最后更新", "FAIL", "数据库文件不存在")

    # 3.2 2025年数据存在性
    count_2025 = db.query(AdmissionScore).filter(AdmissionScore.year == 2025).count()
    if count_2025 > 0:
        report.add_result(module, "2025年数据", "PASS", f"{count_2025:,} 条")
    else:
        report.add_result(module, "2025年数据", "FAIL", "无2025年数据")


# ── 模块5: 业务场景 ──


def check_business(db, report: AcceptanceReport):
    """模块5: 业务场景验收"""
    module = "业务场景"

    # Q1: 河南理科600分
    q1 = (
        db.query(AdmissionScore)
        .join(School)
        .filter(
            AdmissionScore.province == "河南",
            AdmissionScore.subject_type == "理科",
            AdmissionScore.year == 2024,
            AdmissionScore.min_score >= 580,
            AdmissionScore.min_score <= 620,
        )
        .count()
    )
    if q1 > 0:
        report.add_result(module, "Q1: 河南理科600分推荐", "PASS", f"{q1}所院校匹配")
    else:
        report.add_result(module, "Q1: 河南理科600分推荐", "FAIL", "无匹配院校")

    # Q2: 浙江650分推荐
    q2 = (
        db.query(AdmissionScore)
        .filter(
            AdmissionScore.province == "浙江",
            AdmissionScore.subject_type == "3+3综合",
            AdmissionScore.year == 2024,
            AdmissionScore.min_score >= 630,
            AdmissionScore.min_score <= 670,
        )
        .count()
    )
    if q2 > 0:
        report.add_result(module, "Q2: 浙江650分推荐", "PASS", f"{q2}条记录匹配")
    else:
        report.add_result(module, "Q2: 浙江650分推荐", "FAIL", "无匹配记录")

    # Q3: 山东580分211
    q3 = (
        db.query(AdmissionScore)
        .join(School)
        .filter(
            AdmissionScore.province == "山东",
            AdmissionScore.year == 2024,
            AdmissionScore.min_score >= 560,
            AdmissionScore.min_score <= 600,
            School.is_211 == 1,
        )
        .count()
    )
    if q3 > 0:
        report.add_result(module, "Q3: 山东580分211推荐", "PASS", f"{q3}条211记录匹配")
    else:
        report.add_result(module, "Q3: 山东580分211推荐", "FAIL", "无匹配211记录")

    # Q4: 西藏400分
    q4 = (
        db.query(AdmissionScore)
        .filter(
            AdmissionScore.province == "西藏",
            AdmissionScore.min_score <= 420,
        )
        .count()
    )
    if q4 > 0:
        report.add_result(module, "Q4: 西藏400分推荐", "PASS", f"{q4}条记录匹配")
    else:
        report.add_result(module, "Q4: 西藏400分推荐", "FAIL", "无匹配记录")

    # Q5: 湖南物理类530分
    q5 = (
        db.query(AdmissionScore)
        .filter(
            AdmissionScore.province == "湖南",
            AdmissionScore.subject_type == "物理类",
            AdmissionScore.year == 2024,
            AdmissionScore.min_score >= 500,
            AdmissionScore.min_score <= 560,
        )
        .count()
    )
    if q5 > 10:
        report.add_result(module, "Q5: 湖南530分冲稳保", "PASS", f"{q5}条记录匹配")
    elif q5 > 0:
        report.add_result(module, "Q5: 湖南530分冲稳保", "WARN", f"仅{q5}条记录")
    else:
        report.add_result(module, "Q5: 湖南530分冲稳保", "FAIL", "无匹配记录")


# ── 模块6: 安全与运维 ──


def check_security(db, report: AcceptanceReport):
    """模块6: 安全与运维验收"""
    module = "安全与运维"

    # 6.1 敏感信息扫描
    sensitive_patterns = [
        (r'(?:api[_-]?key|apikey|secret|password|token)\s*[=:]\s*["\'][^"\']{8,}', "API Key/Secret/Token"),
    ]
    found_secrets = []
    for root, dirs, files in os.walk(PROJECT_ROOT):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "node_modules", "venv", ".venv", ".worktree")]
        for fname in files:
            if not fname.endswith((".py", ".js", ".ts", ".env", ".yaml", ".yml", ".json", ".toml", ".cfg", ".ini")):
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "r", errors="ignore") as f:
                    content = f.read()
                    for pattern, label in sensitive_patterns:
                        matches = re.findall(pattern, content, re.IGNORECASE)
                        if matches:
                            rel = os.path.relpath(fpath, PROJECT_ROOT)
                            if "example" not in rel.lower() and "template" not in rel.lower():
                                found_secrets.append(f"{rel}: {label}")
            except Exception:
                pass

    if not found_secrets:
        report.add_result(module, "敏感信息扫描", "PASS", "0处硬编码敏感信息")
    else:
        report.add_result(module, "敏感信息扫描", "FAIL", f"发现 {len(found_secrets)} 处: {'; '.join(found_secrets[:5])}")

    # 6.2 数据库文件权限
    db_path = os.path.join(PROJECT_ROOT, "data", "gaokao.db")
    if os.path.exists(db_path):
        mode = oct(os.stat(db_path).st_mode)[-3:]
        if mode in ("600", "640", "644"):
            report.add_result(module, "数据库文件权限", "PASS", f"权限: {mode}")
        else:
            report.add_result(module, "数据库文件权限", "WARN", f"权限: {mode}")
    else:
        report.add_result(module, "数据库文件权限", "FAIL", "数据库文件不存在")

    # 6.3 备份文件存在性
    backup_dir = os.path.join(PROJECT_ROOT, "backups")
    if os.path.exists(backup_dir):
        backups = [f for f in os.listdir(backup_dir) if f.endswith(".sql.gz")]
        if backups:
            report.add_result(module, "数据库备份", "PASS", f"{len(backups)} 个备份文件")
        else:
            report.add_result(module, "数据库备份", "WARN", "备份目录存在但无备份文件")
    else:
        report.add_result(module, "数据库备份", "WARN", "无备份目录")


# ── 主入口 ──


def main():
    parser = argparse.ArgumentParser(description="数据验收")
    parser.add_argument(
        "--module", choices=["integrity", "accuracy", "relation", "timeliness", "business", "security"], help="只运行指定模块"
    )
    parser.add_argument("--report", action="store_true", help="保存报告到文件")
    args = parser.parse_args()

    init_db()
    db = get_session()
    report = AcceptanceReport()

    try:
        if not args.module or args.module == "integrity":
            check_integrity(db, report)
        if not args.module or args.module == "accuracy":
            check_accuracy(db, report)
        if not args.module or args.module == "relation":
            check_relation(db, report)
        if not args.module or args.module == "timeliness":
            check_timeliness(db, report)
        if not args.module or args.module == "business":
            check_business(db, report)
        if not args.module or args.module == "security":
            check_security(db, report)

        report.print_report()
        if args.report:
            report.save_report()

    finally:
        db.close()


if __name__ == "__main__":
    main()