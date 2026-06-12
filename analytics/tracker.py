"""轻量埋点模块：SQLite 存储 + 运营统计。"""

import json
import os
import sqlite3
from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple

# 事件类型常量
EVENT_SESSION_START = "session_start"
EVENT_QUERY_SUBMITTED = "query_submitted"
EVENT_EMOTION_SCORED = "emotion_scored"
EVENT_EMOTION_DETECTED = "emotion_detected"
EVENT_MAJORS_VIEWED = "majors_viewed"
EVENT_SCHOOLS_VIEWED = "schools_viewed"
EVENT_SLOT_FILLED = "slot_filled"
EVENT_MAJOR_QUERY = "major_query"
EVENT_SCHOOL_QUERY = "school_query"
EVENT_EXPORT_CLICKED = "export_clicked"
EVENT_ONBOARDING_COMPLETE = "onboarding_complete"

# 情绪映射
EMOTION_MAP = {"positive": "🟢", "neutral": "🟡", "negative": "🔴"}

# 隐私保护：event_data 字符串最大长度
_MAX_EVENT_DATA_LEN = 200


class EventTracker:
    """用户行为追踪器，基于 SQLite 存储。"""

    def __init__(self, db_path: str | None = None) -> None:
        if db_path is None:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            data_dir = os.path.join(base, "data")
            os.makedirs(data_dir, exist_ok=True)
            db_path = os.path.join(data_dir, "analytics.db")

        self._db_path = db_path
        self._conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    # ------------------------------------------------------------------
    # 初始化
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        cur = self._conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                event_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id);
            CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
            CREATE INDEX IF NOT EXISTS idx_events_time ON events(created_at);
            """
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def log_event(
        self,
        session_id: str,
        event_type: str,
        event_data: Dict[str, Any] | None = None,
    ) -> None:
        """记录一条用户行为事件。

        event_data 会在写入前序列化为 JSON，超过长度限制的值会被截断。
        """
        data_json: str | None = None
        if event_data is not None:
            data_json = json.dumps(event_data, ensure_ascii=False)
            if len(data_json) > _MAX_EVENT_DATA_LEN:
                data_json = data_json[:_MAX_EVENT_DATA_LEN]

        self._conn.execute(
            "INSERT INTO events (session_id, event_type, event_data) VALUES (?, ?, ?)",
            (session_id, event_type, data_json),
        )
        self._conn.commit()

    def get_stats(self, days: int = 7) -> Dict[str, Any]:
        """返回最近 N 天的运营统计。"""
        since = datetime.utcnow() - timedelta(days=days)
        since_str = since.strftime("%Y-%m-%d %H:%M:%S")

        cur = self._conn.cursor()

        # 独立会话数
        cur.execute(
            "SELECT COUNT(DISTINCT session_id) FROM events WHERE created_at >= ?",
            (since_str,),
        )
        session_count = cur.fetchone()[0]

        # 事件类型分布
        cur.execute(
            "SELECT event_type, COUNT(*) FROM events WHERE created_at >= ? GROUP BY event_type",
            (since_str,),
        )
        event_counts: Dict[str, int] = {row[0]: row[1] for row in cur.fetchall()}

        # 情绪分布
        emotion_dist = {"🟢": 0, "🟡": 0, "🔴": 0}
        cur.execute(
            "SELECT event_data FROM events WHERE event_type = ? AND created_at >= ?",
            (EVENT_EMOTION_SCORED, since_str),
        )
        for (data_json,) in cur.fetchall():
            if not data_json:
                continue
            try:
                data = json.loads(data_json)
                label = data.get("label", "")
                emoji = EMOTION_MAP.get(label)
                if emoji:
                    emotion_dist[emoji] += 1
            except (json.JSONDecodeError, TypeError):
                continue

        # 热门专业
        top_majors = self._top_from_event(EVENT_MAJORS_VIEWED, "majors", since_str)

        # 热门院校
        top_schools = self._top_from_event(EVENT_SCHOOLS_VIEWED, "schools", since_str)

        return {
            "session_count": session_count,
            "event_counts": event_counts,
            "emotion_distribution": emotion_dist,
            "top_majors": top_majors,
            "top_schools": top_schools,
        }

    def close(self) -> None:
        """关闭数据库连接。"""
        self._conn.close()

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _top_from_event(
        self, event_type: str, key: str, since_str: str, limit: int = 10
    ) -> List[Tuple[str, int]]:
        """从 event_data JSON 中提取列表字段，统计频次，返回 top-N。"""
        cur = self._conn.cursor()
        cur.execute(
            "SELECT event_data FROM events WHERE event_type = ? AND created_at >= ?",
            (event_type, since_str),
        )
        counter: Counter = Counter()
        for (data_json,) in cur.fetchall():
            if not data_json:
                continue
            try:
                data = json.loads(data_json)
                items = data.get(key, [])
                if isinstance(items, list):
                    counter.update(items)
            except (json.JSONDecodeError, TypeError):
                continue
        return counter.most_common(limit)
