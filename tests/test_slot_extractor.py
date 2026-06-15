"""Tests for slot extraction from user messages — unified to use slots.extractor."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slots.extractor import SlotExtractor


@pytest.fixture
def extractor():
    return SlotExtractor()


def test_extracts_province(extractor):
    slots_dict, _ = extractor.extract("我是北京的考生")
    assert slots_dict["province"]["filled"] is True
    assert slots_dict["province"]["value"] == "北京"


def test_extracts_score(extractor):
    slots_dict, _ = extractor.extract("我考了620分")
    assert slots_dict["score_rank"]["filled"] is True
    assert "620" in slots_dict["score_rank"]["value"]


def test_extracts_score_chinese_num(extractor):
    slots_dict, _ = extractor.extract("我考了六百二十分")
    assert slots_dict["score_rank"]["filled"] is True
    assert "620" in slots_dict["score_rank"]["value"]


def test_extracts_subject_science(extractor):
    slots_dict, _ = extractor.extract("我是理科生")
    assert slots_dict["subject"]["filled"] is True
    assert slots_dict["subject"]["value"] == "理科"


def test_extracts_subject_3plus3(extractor):
    slots_dict, _ = extractor.extract("我选的物理化学生物")
    assert slots_dict["subject"]["filled"] is True
    # slots/extractor matches raw combo like "物化生"
    assert slots_dict["subject"]["value"] in ("物化生", "物理+化学+生物")


def test_extracts_interest(extractor):
    slots_dict, _ = extractor.extract("我想学计算机专业")
    assert slots_dict["interest"]["filled"] is True
    assert "计算机" in slots_dict["interest"]["value"]


def test_extracts_goal(extractor):
    slots_dict, _ = extractor.extract("我想考研")
    assert slots_dict["goal"]["filled"] is True
    assert slots_dict["goal"]["value"] == "考研"


def test_extracts_multiple_slots(extractor):
    text = "北京理科生，630分，想学计算机，以后想考研"
    slots_dict, _ = extractor.extract(text)
    assert slots_dict["province"]["value"] == "北京"
    assert "630" in slots_dict["score_rank"]["value"]
    assert "计算机" in slots_dict["interest"]["value"]
    assert slots_dict["goal"]["value"] == "考研"


def test_empty_input_returns_empty(extractor):
    slots_dict, updated = extractor.extract("")
    assert updated == []
    assert not any(v["filled"] for v in slots_dict.values())


def test_unrelated_input_returns_empty(extractor):
    slots_dict, updated = extractor.extract("今天天气不错")
    assert not any(v["filled"] for v in slots_dict.values())


def test_dialect_shandong(extractor):
    slots_dict, _ = extractor.extract("俺是山东的")
    assert slots_dict["province"]["filled"] is True
    assert slots_dict["province"]["value"] == "山东"


def test_score_oral(extractor):
    slots_dict, _ = extractor.extract("大概六百分")
    assert slots_dict["score_rank"]["filled"] is True
    assert "600" in slots_dict["score_rank"]["value"]
