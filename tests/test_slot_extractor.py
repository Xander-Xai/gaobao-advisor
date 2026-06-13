"""Tests for slot extraction from user messages."""
import pytest

from server.services.slot_extractor import SlotExtractor


@pytest.fixture
def extractor():
    return SlotExtractor()


def test_extracts_province(extractor):
    slots = extractor.extract("我是北京的考生")
    assert slots["province"] == "北京"


def test_extracts_score(extractor):
    slots = extractor.extract("我考了620分")
    assert slots["score"] == 620


def test_extracts_score_chinese_num(extractor):
    slots = extractor.extract("我考了六百二十分")
    assert slots["score"] == 620


def test_extracts_subject_science(extractor):
    slots = extractor.extract("我是理科生")
    assert slots["subject"] == "理科"


def test_extracts_subject_3plus3(extractor):
    slots = extractor.extract("我选的物理化学生物")
    assert slots["subject"] == "物理+化学+生物"


def test_extracts_interest(extractor):
    slots = extractor.extract("我想学计算机专业")
    assert "计算机" in slots["interest"]


def test_extracts_goal(extractor):
    slots = extractor.extract("我想考研")
    assert slots["goal"] == "考研"


def test_extracts_multiple_slots(extractor):
    text = "北京理科生，630分，想学计算机，以后想考研"
    slots = extractor.extract(text)
    assert slots["province"] == "北京"
    assert slots["score"] == 630
    assert "计算机" in slots["interest"]
    assert slots["goal"] == "考研"


def test_empty_input_returns_empty(extractor):
    slots = extractor.extract("")
    assert all(v is None for v in slots.values())


def test_unrelated_input_returns_empty(extractor):
    slots = extractor.extract("今天天气不错")
    assert all(v is None for v in slots.values())


def test_dialect_shandong(extractor):
    slots = extractor.extract("俺是山东的")
    assert slots["province"] == "山东"


def test_score_oral(extractor):
    slots = extractor.extract("大概六百分")
    assert slots["score"] == 600
