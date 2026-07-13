from server.services.data_query import annotate_provenance


def test_missing_source_or_year_is_marked_unverified():
    result = annotate_provenance({"school_name": "示例大学", "min_score": 580})

    assert result["provenance_status"] == "unverified"
    assert "无法验证" in result["data_source"]
    assert result["confidence_score"] <= 20


def test_synthetic_numeric_record_is_zero_confidence():
    result = annotate_provenance(
        {
            "school_name": "星海理工学院",
            "min_score": 580,
            "year": 2099,
            "data_source": "SYNTHETIC DEMO DATA - NOT FOR REAL ADMISSION DECISIONS",
        }
    )

    assert result["synthetic"] is True
    assert result["provenance_status"] == "synthetic"
    assert result["confidence_score"] == 0
    assert "不可用于真实志愿决策" in result["data_source"]


def test_declared_source_and_year_are_preserved_for_display():
    result = annotate_provenance(
        {
            "school_name": "示例大学",
            "min_score": 580,
            "year": 2025,
            "data_source": "某省教育考试院 2025 年投档公告",
        }
    )

    assert result["provenance_status"] == "declared"
    assert result["year"] == 2025
    assert "考试院" in result["data_source"]
