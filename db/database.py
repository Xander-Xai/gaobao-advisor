"""
SQLite 数据库连接 — 零依赖外部服务，开箱即用
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)

DB_PATH = os.path.join(PROJECT_ROOT, "data", "gaokao.db")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_session():
    """获取数据库会话（用完记得关闭）"""
    return SessionLocal()


def init_db():
    """创建所有表"""
    from db.models import School, Major, AdmissionScore, EnrollmentPlan, SubjectRanking  # noqa
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    Base.metadata.create_all(bind=engine)
