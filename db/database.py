"""
SQLite 数据库连接 — 零依赖外部服务，开箱即用
"""
import os
import stat

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)

DB_PATH = os.path.join(PROJECT_ROOT, "data", "gaokao.db")

# #15: DATABASE_URL 白名单校验（防止注入指向外部数据库）
_RAW_DB_URL = os.getenv("DATABASE_URL", "")
_ALLOWED_SCHEMES = ("sqlite",)
_allowed = False

if _RAW_DB_URL:
    for scheme in _ALLOWED_SCHEMES:
        if _RAW_DB_URL.startswith(f"{scheme}://"):
            _allowed = True
            break
    if not _allowed:
        _RAW_DB_URL = ""  # 拒绝不安全的 scheme

DATABASE_URL = _RAW_DB_URL if _RAW_DB_URL else f"sqlite:///{DB_PATH}"

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


def _lock_db_permissions(db_path: str):
    """收紧数据库及其 WAL/SHM 附属文件的权限为 0600（仅 owner 可读写）。"""
    for suffix in ("", "-wal", "-shm"):
        path = db_path + suffix
        if os.path.exists(path):
            try:
                os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)  # 0600
            except OSError:
                pass


def is_db_connected() -> bool:
    """Check database engine connectivity.

    Returns:
        True if the engine can execute a simple query, False otherwise.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def init_db():
    """创建所有表"""
    from db.models import School, Major, AdmissionScore, EnrollmentPlan, SubjectRanking, YiFenYiDuan, Highlight  # noqa
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    Base.metadata.create_all(bind=engine)
    _lock_db_permissions(DB_PATH)
