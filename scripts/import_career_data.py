#!/usr/bin/env python3
"""
Import Career Path Data.

Imports career information including job roles, required skills, salary ranges,
and career progression paths for career planning guidance.

Data sources:
    - LinkedIn Jobs
    - Zhaopin.com
    - Boss Zhipin
    - Industry reports

Usage:
    python scripts/import_career_data.py [--test]

Output:
    - Populates careers table
    - Populates career_skills table
    - Populates salary_ranges table
"""

import argparse
import logging
import os
import sys
from datetime import datetime

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from db.database import SessionLocal, engine  # noqa: E402
from db.models import Base  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def create_tables():
    """Create Career-related tables."""
    logger.info("Creating Career tables...")

    from sqlalchemy import JSON, Column, DateTime, Integer, String, Text

    class Career(Base):
        __tablename__ = "careers"

        id = Column(Integer, primary_key=True, autoincrement=True)
        title = Column(String(200), nullable=False, index=True)  # Job title
        category = Column(String(100), index=True)  # IT, Finance, Education, etc.
        industry = Column(String(100))  # Internet, Banking, Manufacturing, etc.
        description = Column(Text)
        required_education = Column(String(50))  # 本科, 硕士, 博士
        experience_years = Column(Integer)  # Required experience (years)
        career_path = Column(JSON)  # Progression path
        created_at = Column(DateTime, default=datetime.utcnow)

    class CareerSkill(Base):
        __tablename__ = "career_skills"

        id = Column(Integer, primary_key=True, autoincrement=True)
        career_id = Column(Integer, index=True)
        skill_name = Column(String(200), nullable=False)
        importance = Column(String(20))  # Essential, Preferred, Nice-to-have
        proficiency_level = Column(String(20))  # Beginner, Intermediate, Advanced, Expert
        created_at = Column(DateTime, default=datetime.utcnow)

    class SalaryRange(Base):
        __tablename__ = "salary_ranges"

        id = Column(Integer, primary_key=True, autoincrement=True)
        career_id = Column(Integer, index=True)
        city = Column(String(50), index=True)
        experience_level = Column(String(50))  # Entry, Junior, Mid, Senior, Lead
        min_salary = Column(Integer)  # Monthly salary (CNY)
        max_salary = Column(Integer)
        avg_salary = Column(Integer)
        year = Column(Integer, default=2024)
        created_at = Column(DateTime, default=datetime.utcnow)

    # Create tables
    Base.metadata.create_all(
        engine,
        tables=[
            Career.__table__,
            CareerSkill.__table__,
            SalaryRange.__table__,
        ],
    )

    logger.info("✓ Career tables created")


def import_sample_data(test_mode: bool = False):
    """Import sample career data."""
    logger.info("Importing sample career data...")

    session = SessionLocal()
    try:
        # Sample careers
        careers = [
            {
                "title": "软件工程师",
                "category": "IT/互联网",
                "industry": "互联网",
                "description": "负责软件开发、维护和优化",
                "required_education": "本科",
                "experience_years": 0,
                "career_path": ["初级工程师", "中级工程师", "高级工程师", "技术专家", "架构师"],
            },
            {
                "title": "产品经理",
                "category": "IT/互联网",
                "industry": "互联网",
                "description": "负责产品规划、需求分析和项目管理",
                "required_education": "本科",
                "experience_years": 2,
                "career_path": ["产品助理", "产品经理", "高级产品经理", "产品总监", "VP产品"],
            },
            {
                "title": "数据分析师",
                "category": "数据分析",
                "industry": "互联网/金融",
                "description": "负责数据采集、清洗、分析和可视化",
                "required_education": "本科",
                "experience_years": 1,
                "career_path": ["数据分析师", "高级数据分析师", "数据科学家", "数据分析经理"],
            },
            {
                "title": "金融分析师",
                "category": "金融",
                "industry": "银行/证券/基金",
                "description": "负责金融市场分析、投资建议和风险管理",
                "required_education": "硕士",
                "experience_years": 3,
                "career_path": ["分析师", "高级分析师", "投资经理", "投资总监", "合伙人"],
            },
            {
                "title": "教师",
                "category": "教育",
                "industry": "教育/培训",
                "description": "负责教学、课程设计和学生管理",
                "required_education": "本科",
                "experience_years": 0,
                "career_path": ["助教", "讲师", "副教授", "教授", "学科带头人"],
            },
            {
                "title": "医生",
                "category": "医疗",
                "industry": "医疗卫生",
                "description": "负责疾病诊断、治疗和预防",
                "required_education": "博士",
                "experience_years": 5,
                "career_path": ["住院医师", "主治医师", "副主任医师", "主任医师", "科室主任"],
            },
            {
                "title": "律师",
                "category": "法律",
                "industry": "法律服务",
                "description": "提供法律咨询、代理诉讼和非诉业务",
                "required_education": "本科",
                "experience_years": 2,
                "career_path": ["律师助理", "律师", "资深律师", "合伙人", "律所主任"],
            },
            {
                "title": "市场营销经理",
                "category": "市场/营销",
                "industry": "各行业",
                "description": "负责市场推广、品牌建设和营销策划",
                "required_education": "本科",
                "experience_years": 3,
                "career_path": ["市场专员", "市场主管", "市场经理", "市场总监", "CMO"],
            },
        ]

        # Sample skills for careers
        career_skills = [
            {
                "career_title": "软件工程师",
                "skill_name": "Python",
                "importance": "Essential",
                "proficiency_level": "Intermediate",
            },
            {
                "career_title": "软件工程师",
                "skill_name": "Java",
                "importance": "Essential",
                "proficiency_level": "Intermediate",
            },
            {
                "career_title": "软件工程师",
                "skill_name": "JavaScript",
                "importance": "Preferred",
                "proficiency_level": "Beginner",
            },
            {
                "career_title": "软件工程师",
                "skill_name": "数据结构",
                "importance": "Essential",
                "proficiency_level": "Advanced",
            },
            {
                "career_title": "软件工程师",
                "skill_name": "算法",
                "importance": "Essential",
                "proficiency_level": "Advanced",
            },
            {
                "career_title": "产品经理",
                "skill_name": "需求分析",
                "importance": "Essential",
                "proficiency_level": "Advanced",
            },
            {
                "career_title": "产品经理",
                "skill_name": "原型设计",
                "importance": "Essential",
                "proficiency_level": "Intermediate",
            },
            {
                "career_title": "产品经理",
                "skill_name": "数据分析",
                "importance": "Preferred",
                "proficiency_level": "Intermediate",
            },
            {
                "career_title": "产品经理",
                "skill_name": "沟通协调",
                "importance": "Essential",
                "proficiency_level": "Advanced",
            },
            {
                "career_title": "数据分析师",
                "skill_name": "SQL",
                "importance": "Essential",
                "proficiency_level": "Advanced",
            },
            {
                "career_title": "数据分析师",
                "skill_name": "Python",
                "importance": "Essential",
                "proficiency_level": "Intermediate",
            },
            {
                "career_title": "数据分析师",
                "skill_name": "统计学",
                "importance": "Essential",
                "proficiency_level": "Advanced",
            },
            {
                "career_title": "数据分析师",
                "skill_name": "可视化",
                "importance": "Preferred",
                "proficiency_level": "Intermediate",
            },
        ]

        # Sample salary ranges
        salary_ranges = [
            {
                "career_title": "软件工程师",
                "city": "北京",
                "experience_level": "Entry",
                "min_salary": 15000,
                "max_salary": 25000,
                "avg_salary": 20000,
            },
            {
                "career_title": "软件工程师",
                "city": "北京",
                "experience_level": "Mid",
                "min_salary": 25000,
                "max_salary": 40000,
                "avg_salary": 32000,
            },
            {
                "career_title": "软件工程师",
                "city": "北京",
                "experience_level": "Senior",
                "min_salary": 40000,
                "max_salary": 70000,
                "avg_salary": 55000,
            },
            {
                "career_title": "软件工程师",
                "city": "上海",
                "experience_level": "Entry",
                "min_salary": 14000,
                "max_salary": 23000,
                "avg_salary": 18000,
            },
            {
                "career_title": "软件工程师",
                "city": "上海",
                "experience_level": "Mid",
                "min_salary": 23000,
                "max_salary": 38000,
                "avg_salary": 30000,
            },
            {
                "career_title": "产品经理",
                "city": "北京",
                "experience_level": "Entry",
                "min_salary": 12000,
                "max_salary": 20000,
                "avg_salary": 16000,
            },
            {
                "career_title": "产品经理",
                "city": "北京",
                "experience_level": "Mid",
                "min_salary": 20000,
                "max_salary": 35000,
                "avg_salary": 27000,
            },
            {
                "career_title": "数据分析师",
                "city": "北京",
                "experience_level": "Entry",
                "min_salary": 13000,
                "max_salary": 22000,
                "avg_salary": 17000,
            },
            {
                "career_title": "数据分析师",
                "city": "北京",
                "experience_level": "Mid",
                "min_salary": 22000,
                "max_salary": 35000,
                "avg_salary": 28000,
            },
        ]

        if test_mode:
            logger.info(f"[TEST MODE] Would insert {len(careers)} careers")
            logger.info(f"[TEST MODE] Would insert {len(career_skills)} skills")
            logger.info(f"[TEST MODE] Would insert {len(salary_ranges)} salary ranges")
            return

        # Insert careers
        from db.models import Career as C

        for career_data in careers:
            existing = session.query(C).filter(C.title == career_data["title"]).first()
            if not existing:
                career = C(**career_data)
                session.add(career)

        session.commit()
        logger.info(f"✓ Inserted {len(careers)} careers")

        # Insert skills
        from db.models import CareerSkill as CS

        for skill_data in career_skills:
            career = session.query(C).filter(C.title == skill_data["career_title"]).first()
            if career:
                skill_data["career_id"] = career.id
                del skill_data["career_title"]

                existing = (
                    session.query(CS)
                    .filter(CS.career_id == skill_data["career_id"], CS.skill_name == skill_data["skill_name"])
                    .first()
                )

                if not existing:
                    skill = CS(**skill_data)
                    session.add(skill)

        session.commit()
        logger.info(f"✓ Inserted {len(career_skills)} skills")

        # Insert salary ranges
        from db.models import SalaryRange as SR

        for salary_data in salary_ranges:
            career = session.query(C).filter(C.title == salary_data["career_title"]).first()
            if career:
                salary_data["career_id"] = career.id
                del salary_data["career_title"]

                existing = (
                    session.query(SR)
                    .filter(
                        SR.career_id == salary_data["career_id"],
                        SR.city == salary_data["city"],
                        SR.experience_level == salary_data["experience_level"],
                    )
                    .first()
                )

                if not existing:
                    salary = SR(**salary_data)
                    session.add(salary)

        session.commit()
        logger.info(f"✓ Inserted {len(salary_ranges)} salary ranges")

    except Exception as e:
        session.rollback()
        logger.error(f"Failed to import data: {e}")
        raise
    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(description="Import Career data")
    parser.add_argument("--test", action="store_true", help="Test mode (don't insert)")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Career Data Import Tool")
    logger.info("=" * 60)

    # Create tables
    create_tables()

    # Import data
    import_sample_data(test_mode=args.test)

    logger.info("=" * 60)
    logger.info("Import completed successfully!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
