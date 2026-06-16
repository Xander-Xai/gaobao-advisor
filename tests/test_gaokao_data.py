"""gaokao_data 模块测试。"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from legacy.gaokao_data import get_db_stats


def test_get_db_stats_no_name_error():
    """get_db_stats() 不应抛 NameError（_db_session 未定义）。"""
    result = get_db_stats()
    assert isinstance(result, dict)
    assert "status" in result or "schools" in result


def test_get_db_stats_returns_valid_dict():
    """返回结构应包含预期字段。"""
    result = get_db_stats()
    if "status" not in result:
        assert "schools" in result
        assert "majors" in result
        assert "admission_scores" in result
        assert "subject_rankings" in result
        assert "policies" in result
        assert isinstance(result["schools"], int)
