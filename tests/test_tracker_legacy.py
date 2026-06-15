"""analytics.tracker 单元测试。"""

import json
import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analytics.tracker import (
    EVENT_EMOTION_SCORED,
    EVENT_MAJORS_VIEWED,
    EVENT_QUERY_SUBMITTED,
    EVENT_SESSION_START,
    EventTracker,
)


class TestEventTracker(unittest.TestCase):
    """EventTracker 核心功能测试。"""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test_analytics.db")
        self.tracker = EventTracker(db_path=self.db_path)

    def tearDown(self) -> None:
        self.tracker.close()
        # 清理临时文件
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
        os.rmdir(self.tmpdir)

    # ------------------------------------------------------------------
    # 测试 1: log_event
    # ------------------------------------------------------------------

    def test_log_event(self) -> None:
        """记录 3 条事件并验证写入成功。"""
        sid = "test-session-001"
        self.tracker.log_event(sid, EVENT_SESSION_START, {"platform": "wechat"})
        self.tracker.log_event(sid, EVENT_QUERY_SUBMITTED, {"q_len": 42})
        self.tracker.log_event(sid, EVENT_EMOTION_SCORED, {"label": "positive", "score": 0.92})

        # 直接查 SQLite 确认
        conn = sqlite3.connect(self.db_path)
        cur = conn.execute("SELECT COUNT(*) FROM events")
        count = cur.fetchone()[0]
        conn.close()

        self.assertEqual(count, 3, "应有 3 条事件写入数据库")

        # 验证 session_id 和 event_type 正确
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT session_id, event_type FROM events ORDER BY id").fetchall()
        conn.close()

        expected_types = [EVENT_SESSION_START, EVENT_QUERY_SUBMITTED, EVENT_EMOTION_SCORED]
        for row, expected_type in zip(rows, expected_types, strict=False):
            self.assertEqual(row["session_id"], sid)
            self.assertEqual(row["event_type"], expected_type)

    # ------------------------------------------------------------------
    # 测试 2: get_stats
    # ------------------------------------------------------------------

    def test_get_stats(self) -> None:
        """跨 2 个会话写入多种事件，验证统计结果。"""
        # Session A
        self.tracker.log_event("s1", EVENT_SESSION_START)
        self.tracker.log_event("s1", EVENT_QUERY_SUBMITTED, {"q_len": 30})
        self.tracker.log_event("s1", EVENT_EMOTION_SCORED, {"label": "positive", "score": 0.8})
        self.tracker.log_event("s1", EVENT_EMOTION_SCORED, {"label": "neutral", "score": 0.5})
        self.tracker.log_event("s1", EVENT_MAJORS_VIEWED, {"majors": ["计算机科学", "人工智能", "数据科学"]})

        # Session B
        self.tracker.log_event("s2", EVENT_SESSION_START)
        self.tracker.log_event("s2", EVENT_QUERY_SUBMITTED, {"q_len": 50})
        self.tracker.log_event("s2", EVENT_EMOTION_SCORED, {"label": "negative", "score": 0.2})
        self.tracker.log_event("s2", EVENT_MAJORS_VIEWED, {"majors": ["人工智能", "软件工程"]})

        stats = self.tracker.get_stats(days=1)

        # 独立会话数
        self.assertEqual(stats["session_count"], 2)

        # 事件计数
        self.assertEqual(stats["event_counts"][EVENT_SESSION_START], 2)
        self.assertEqual(stats["event_counts"][EVENT_QUERY_SUBMITTED], 2)
        self.assertEqual(stats["event_counts"][EVENT_EMOTION_SCORED], 3)

        # 情绪分布
        self.assertEqual(stats["emotion_distribution"]["🟢"], 1)
        self.assertEqual(stats["emotion_distribution"]["🟡"], 1)
        self.assertEqual(stats["emotion_distribution"]["🔴"], 1)

        # 热门专业：人工智能 应排第一（出现 2 次）
        top_names = [name for name, _ in stats["top_majors"]]
        self.assertEqual(top_names[0], "人工智能")
        top_counts = {name: cnt for name, cnt in stats["top_majors"]}
        self.assertEqual(top_counts["人工智能"], 2)

    # ------------------------------------------------------------------
    # 测试 3: 隐私保护
    # ------------------------------------------------------------------

    def test_privacy_no_raw_text(self) -> None:
        """确认超长文本被截断，不会原样存入数据库。"""
        long_text = "这是一段很长的用户原始输入，" * 100  # 远超 200 字符
        self.tracker.log_event("s-privacy", EVENT_QUERY_SUBMITTED, {"raw_text": long_text})

        conn = sqlite3.connect(self.db_path)
        cur = conn.execute("SELECT event_data FROM events LIMIT 1")
        stored = cur.fetchone()[0]
        conn.close()

        self.assertLessEqual(len(stored), 200, "event_data 应被截断到 200 字符以内")
        self.assertNotEqual(stored, json.dumps({"raw_text": long_text}, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
