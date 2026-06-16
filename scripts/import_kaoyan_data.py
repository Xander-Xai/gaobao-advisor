#!/usr/bin/env python3
"""
Import Postgraduate Entrance Exam (Kaoyan) Data.

Imports university rankings, major information, and admission statistics
for postgraduate entrance exam planning.

Data sources:
    - China Graduate Admission Information Network
    - University official websites
    - Third-party education data providers

Usage:
    python scripts/import_kaoyan_data.py [--test]

Output:
    - Populates kaoyan_universities table
    - Populates kaoyan_majors table
    - Populates kaoyan_admission_stats table
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from sqlalchemy import text
from db.database import SessionLocal, engine
from db.models import Base

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def create_tables():
    """Create Kaoyan-related tables if they don't exist."""
    logger.info("Creating Kaoyan tables...")
    
    # Define Kaoyan models inline for simplicity
    from sqlalchemy import Column, Integer, String, Float, Text, DateTime, Boolean
    
    class KaoyanUniversity(Base):
        __tablename__ = "kaoyan_universities"
        
        id = Column(Integer, primary_key=True, autoincrement=True)
        name = Column(String(200), nullable=False, index=True)
        level = Column(String(50))  # 985, 211, 双一流
        province = Column(String(50), index=True)
        city = Column(String(100))
        type = Column(String(50))  # 综合, 理工, 师范, etc.
        ranking = Column(Integer)  # National ranking
        website = Column(String(200))
        created_at = Column(DateTime, default=datetime.utcnow)
    
    class KaoyanMajor(Base):
        __tablename__ = "kaoyan_majors"
        
        id = Column(Integer, primary_key=True, autoincrement=True)
        code = Column(String(20), unique=True, index=True)  # Major code (e.g., 081200)
        name = Column(String(200), nullable=False, index=True)
        category = Column(String(100))  # 工学, 理学, 文学, etc.
        degree_type = Column(String(20))  # 学硕, 专硕
        duration_years = Column(Integer, default=3)  # Program duration
        description = Column(Text)
        created_at = Column(DateTime, default=datetime.utcnow)
    
    class KaoyanAdmissionStats(Base):
        __tablename__ = "kaoyan_admission_stats"
        
        id = Column(Integer, primary_key=True, autoincrement=True)
        university_id = Column(Integer, index=True)
        major_code = Column(String(20), index=True)
        year = Column(Integer, index=True)
        enrolled_count = Column(Integer)  # Number of enrolled students
        applicant_count = Column(Integer)  # Number of applicants
        acceptance_rate = Column(Float)  # Acceptance rate (%)
        min_score = Column(Integer)  # Minimum score
        avg_score = Column(Integer)  # Average score
        max_score = Column(Integer)  # Maximum score
        created_at = Column(DateTime, default=datetime.utcnow)
    
    # Create tables
    Base.metadata.create_all(engine, tables=[
        KaoyanUniversity.__table__,
        KaoyanMajor.__table__,
        KaoyanAdmissionStats.__table__,
    ])
    
    logger.info("✓ Kaoyan tables created")


def import_sample_data(test_mode: bool = False):
    """Import sample Kaoyan data."""
    logger.info("Importing sample Kaoyan data...")
    
    session = SessionLocal()
    try:
        # Sample universities
        universities = [
            {"name": "清华大学", "level": "985", "province": "北京", "city": "北京", "type": "理工", "ranking": 1},
            {"name": "北京大学", "level": "985", "province": "北京", "city": "北京", "type": "综合", "ranking": 2},
            {"name": "复旦大学", "level": "985", "province": "上海", "city": "上海", "type": "综合", "ranking": 3},
            {"name": "浙江大学", "level": "985", "province": "浙江", "city": "杭州", "type": "综合", "ranking": 4},
            {"name": "上海交通大学", "level": "985", "province": "上海", "city": "上海", "type": "理工", "ranking": 5},
            {"name": "南京大学", "level": "985", "province": "江苏", "city": "南京", "type": "综合", "ranking": 6},
            {"name": "中国科学技术大学", "level": "985", "province": "安徽", "city": "合肥", "type": "理工", "ranking": 7},
            {"name": "华中科技大学", "level": "985", "province": "湖北", "city": "武汉", "type": "理工", "ranking": 8},
            {"name": "武汉大学", "level": "985", "province": "湖北", "city": "武汉", "type": "综合", "ranking": 9},
            {"name": "中山大学", "level": "985", "province": "广东", "city": "广州", "type": "综合", "ranking": 10},
        ]
        
        # Sample majors
        majors = [
            {"code": "081200", "name": "计算机科学与技术", "category": "工学", "degree_type": "学硕", "duration_years": 3},
            {"code": "085400", "name": "电子信息", "category": "工学", "degree_type": "专硕", "duration_years": 2},
            {"code": "020200", "name": "应用经济学", "category": "经济学", "degree_type": "学硕", "duration_years": 3},
            {"code": "025100", "name": "金融", "category": "经济学", "degree_type": "专硕", "duration_years": 2},
            {"code": "050100", "name": "中国语言文学", "category": "文学", "degree_type": "学硕", "duration_years": 3},
            {"code": "055100", "name": "翻译", "category": "文学", "degree_type": "专硕", "duration_years": 2},
            {"code": "070100", "name": "数学", "category": "理学", "degree_type": "学硕", "duration_years": 3},
            {"code": "080200", "name": "机械工程", "category": "工学", "degree_type": "学硕", "duration_years": 3},
            {"code": "120200", "name": "工商管理", "category": "管理学", "degree_type": "学硕", "duration_years": 3},
            {"code": "125100", "name": "工商管理硕士(MBA)", "category": "管理学", "degree_type": "专硕", "duration_years": 2},
        ]
        
        # Sample admission stats
        admission_stats = [
            {"university_name": "清华大学", "major_code": "081200", "year": 2024, 
             "enrolled_count": 50, "applicant_count": 500, "acceptance_rate": 10.0,
             "min_score": 380, "avg_score": 420, "max_score": 480},
            {"university_name": "北京大学", "major_code": "081200", "year": 2024,
             "enrolled_count": 45, "applicant_count": 450, "acceptance_rate": 10.0,
             "min_score": 375, "avg_score": 415, "max_score": 475},
            {"university_name": "复旦大学", "major_code": "025100", "year": 2024,
             "enrolled_count": 80, "applicant_count": 800, "acceptance_rate": 10.0,
             "min_score": 390, "avg_score": 430, "max_score": 490},
        ]
        
        if test_mode:
            logger.info(f"[TEST MODE] Would insert {len(universities)} universities")
            logger.info(f"[TEST MODE] Would insert {len(majors)} majors")
            logger.info(f"[TEST MODE] Would insert {len(admission_stats)} admission stats")
            return
        
        # Insert universities
        from db.models import KaoyanUniversity as KU
        for uni_data in universities:
            existing = session.query(KU).filter(KU.name == uni_data["name"]).first()
            if not existing:
                uni = KU(**uni_data)
                session.add(uni)
        
        session.commit()
        logger.info(f"✓ Inserted {len(universities)} universities")
        
        # Insert majors
        from db.models import KaoyanMajor as KM
        for major_data in majors:
            existing = session.query(KM).filter(KM.code == major_data["code"]).first()
            if not existing:
                major = KM(**major_data)
                session.add(major)
        
        session.commit()
        logger.info(f"✓ Inserted {len(majors)} majors")
        
        # Insert admission stats
        from db.models import KaoyanAdmissionStats as KAS
        for stat_data in admission_stats:
            # Find university ID
            uni = session.query(KU).filter(KU.name == stat_data["university_name"]).first()
            if uni:
                stat_data["university_id"] = uni.id
                del stat_data["university_name"]
                
                existing = session.query(KAS).filter(
                    KAS.university_id == stat_data["university_id"],
                    KAS.major_code == stat_data["major_code"],
                    KAS.year == stat_data["year"]
                ).first()
                
                if not existing:
                    stat = KAS(**stat_data)
                    session.add(stat)
        
        session.commit()
        logger.info(f"✓ Inserted {len(admission_stats)} admission stats")
        
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to import data: {e}")
        raise
    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(description="Import Kaoyan data")
    parser.add_argument("--test", action="store_true", help="Test mode (don't insert)")
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("Kaoyan Data Import Tool")
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
