#!/usr/bin/env python3
"""
从 xuefeng-agent 的 admission_clean.db 导入 31 省全量录取数据到 gaokao.db。

⚠️ 注意：xuefeng-agent 项目已于 2026-06-13 删除，此脚本为归档参考。
如需使用，请先恢复 xuefeng-agent 目录或将 admission_clean.db.gz 放到正确位置。

用法:
  python scripts/import_xuefeng_data.py [--dry-run] [--verbose]

说明:
  - 自动解压 admission_clean.db.gz（如需要）
  - 通过学校名匹配现有 schools 表，未匹配的自动创建
  - 使用 UniqueConstraint 去重，不会产生重复记录
"""

from __future__ import annotations

import argparse
import gzip
import os
import shutil
import sys

# ── 路径设置 ──
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XUEFENG_DIR = os.path.join(PROJECT_ROOT, "..", "xuefeng-agent")
XUEFENG_DB_GZ = os.path.join(XUEFENG_DIR, "admission_clean.db.gz")
XUEFENG_DB = os.path.join(XUEFENG_DIR, "admission_clean.db")

sys.path.insert(0, PROJECT_ROOT)

from db.database import SessionLocal, init_db  # noqa: E402
from db.models import AdmissionScore, School  # noqa: E402


def decompress_db_if_needed() -> str:
    """解压 .gz 数据库文件，返回可用的 db 路径。"""
    if os.path.exists(XUEFENG_DB):
        print(f"[INFO] 使用已存在的数据库: {XUEFENG_DB}")
        return XUEFENG_DB

    if not os.path.exists(XUEFENG_DB_GZ):
        print(f"[ERROR] 找不到数据库文件: {XUEFENG_DB_GZ}")
        sys.exit(1)

    print(f"[INFO] 解压 {XUEFENG_DB_GZ} ...")
    with gzip.open(XUEFENG_DB_GZ, "rb") as f_in:
        with open(XUEFENG_DB, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
    size_mb = os.path.getsize(XUEFENG_DB) / (1024 * 1024)
    print(f"[INFO] 解压完成: {size_mb:.1f} MB")
    return XUEFENG_DB


def load_school_name_map(db_session) -> dict[str, int]:
    """加载 gaokao.db 中所有学校名 → school_id 的映射。"""
    schools = db_session.query(School).all()
    name_map = {}
    for s in schools:
        name_map[s.name] = s.id
        # 也添加简称映射（去掉"大学"/"学院"后缀的匹配）
    return name_map


def match_school(
    school_name: str,
    name_map: dict[str, int],
    db_session,
) -> int | None:
    """通过学校名匹配 school_id，支持模糊匹配。"""
    # 1. 精确匹配
    if school_name in name_map:
        return name_map[school_name]

    # 2. 去除空格和括号后匹配
    cleaned = school_name.strip().replace("（", "(").replace("）", ")")
    for name, sid in name_map.items():
        name_cleaned = name.strip().replace("（", "(").replace("）", ")")
        if name_cleaned == cleaned:
            return sid

    # 3. 包含匹配（源名包含目标名，或目标名包含源名）
    for name, sid in name_map.items():
        if len(name) >= 4 and (name in school_name or school_name in name):
            return sid

    return None


def create_school(school_name: str, province: str, db_session) -> int:
    """创建新学校记录并返回 school_id。"""
    new_school = School(
        name=school_name,
        province=province,
        level="",  # 未知等级
        type="",
        website="",
    )
    db_session.add(new_school)
    db_session.flush()
    return new_school.id


def import_data(dry_run: bool = False, verbose: bool = False) -> None:
    """主导入逻辑。"""
    # 1. 解压数据库
    xuefeng_db_path = decompress_db_if_needed()

    # 2. 连接 xuefeng 数据库（只读）
    import sqlite3

    xuefeng_conn = sqlite3.connect(f"file:{xuefeng_db_path}?mode=ro", uri=True)
    xuefeng_conn.row_factory = sqlite3.Row
    cursor = xuefeng_conn.cursor()

    # 查看源表结构
    cursor.execute("PRAGMA table_info(admission)")
    columns = [row["name"] for row in cursor.fetchall()]
    print(f"[INFO] 源表列: {columns}")

    # 统计源数据
    cursor.execute("SELECT COUNT(*) FROM admission")
    total_rows = cursor.fetchone()[0]
    print(f"[INFO] 源数据总行数: {total_rows:,}")

    cursor.execute("SELECT COUNT(DISTINCT province) FROM admission")
    provinces = cursor.fetchone()[0]
    print(f"[INFO] 覆盖省份: {provinces}")

    cursor.execute("SELECT province, COUNT(*) FROM admission GROUP BY province ORDER BY COUNT(*) DESC")
    if verbose:
        for row in cursor.fetchall():
            print(f"  {row[0]}: {row[1]:,} 条")

    # 3. 初始化 gaokao.db
    if not dry_run:
        init_db()

    # 4. 加载现有学校映射
    db_session = SessionLocal()
    try:
        name_map = load_school_name_map(db_session)
        print(f"[INFO] 现有学校数: {len(name_map)}")

        # 5. 批量读取并导入
        matched_schools = 0
        new_schools = 0
        new_scores = 0
        skipped_scores = 0
        errors = 0

        batch_size = 5000
        offset = 0

        while offset < total_rows:
            cursor.execute(
                "SELECT province, school, major, score, rank, year FROM admission LIMIT ? OFFSET ?",
                (batch_size, offset),
            )
            rows = cursor.fetchall()

            if not rows:
                break

            for row in rows:
                try:
                    province = row["province"] or ""
                    school_name = (row["school"] or "").strip()
                    (row["major"] or "").strip()
                    score = row["score"]
                    rank = row["rank"]
                    year = row["year"]

                    # 跳过无效数据
                    if not school_name or len(school_name) < 2:
                        errors += 1
                        continue

                    # 匹配学校
                    school_id = match_school(school_name, name_map, db_session)
                    if school_id is None:
                        if dry_run:
                            new_schools += 1
                            continue
                        school_id = create_school(school_name, province, db_session)
                        name_map[school_name] = school_id
                        new_schools += 1
                        if verbose and new_schools <= 10:
                            print(f"  [NEW SCHOOL] {school_name} ({province}) -> id={school_id}")
                    else:
                        matched_schools += 1

                    # 插入录取分数记录
                    if not dry_run:
                        # 检查是否已存在
                        _year = year if year else 2024
                        existing = (
                            db_session.query(AdmissionScore)
                            .filter(
                                AdmissionScore.school_id == school_id,
                                AdmissionScore.province == province,
                                AdmissionScore.year == _year,
                                AdmissionScore.min_score == score,
                                AdmissionScore.min_rank == rank,
                            )
                            .first()
                        )
                        if existing:
                            skipped_scores += 1
                            continue

                        record = AdmissionScore(
                            school_id=school_id,
                            major_id=None,  # xuefeng 数据没有 major_id
                            province=province,
                            year=_year,
                            batch="本科一批" if score and score > 500 else "本科",
                            subject_type="综合",
                            min_score=score,
                            avg_score=None,
                            max_score=None,
                            min_rank=rank,
                            plan_count=None,
                        )
                        db_session.add(record)
                        new_scores += 1
                    else:
                        new_scores += 1

                except Exception as e:
                    errors += 1
                    if verbose:
                        print(f"  [ERROR] {e}")

            # 定期提交
            if not dry_run and new_scores > 0 and new_scores % batch_size == 0:
                db_session.commit()
                print(f"  [PROGRESS] 已导入 {new_scores:,} 条，匹配 {matched_schools:,}，新增学校 {new_schools}")

            offset += batch_size

        # 最终提交
        if not dry_run:
            db_session.commit()

        # 6. 输出统计
        print("\n" + "=" * 60)
        print("导入完成！")
        print("=" * 60)
        print(f"  总源数据:      {total_rows:,} 条")
        print(f"  匹配现有学校:  {matched_schools:,} 条")
        print(f"  新增学校:      {new_schools} 所")
        print(f"  新增录取分数:  {new_scores:,} 条")
        print(f"  跳过(重复):    {skipped_scores:,} 条")
        print(f"  错误:          {errors:,} 条")

        if dry_run:
            print("\n[DRY RUN] 未实际写入任何数据")

    finally:
        db_session.close()
        xuefeng_conn.close()

    # 7. 清理临时解压文件（保留 .gz）
    if os.path.exists(XUEFENG_DB) and not dry_run:
        print(f"[INFO] 保留源数据库: {XUEFENG_DB}")


def main():
    parser = argparse.ArgumentParser(description="从 xuefeng-agent 导入录取数据")
    parser.add_argument("--dry-run", action="store_true", help="试运行，不写入数据库")
    parser.add_argument("--verbose", action="store_true", help="显示详细信息")
    args = parser.parse_args()

    import_data(dry_run=args.dry_run, verbose=args.verbose)


if __name__ == "__main__":
    main()
