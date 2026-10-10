"""
cross_validator — 录取数据交叉校验

对比多个数据源的分数线/排名，输出置信度与差异提示。
"""

from config.loader import load_tuning


def _get_cv_config():
    return load_tuning().get("thresholds", {}).get("cross_validation", {})


def cross_validate_admission(sources: list[dict]) -> dict | None:
    """对多个数据源的录取信息做交叉校验。

    Args:
        sources: 每个元素包含 source(str), min_score(int|None), min_rank(int|None)

    Returns:
        校验结果 dict 或 None（无法校验时）
    """
    if not sources:
        return None

    valid = [s for s in sources if s.get("min_score") is not None]
    if not valid:
        return None

    best = valid[0]
    sources_used = [s["source"] for s in valid]

    if len(valid) == 1:
        return {
            "best": best,
            "confidence": "低",
            "note": "仅单源数据，请核实官方信息",
            "sources_used": sources_used,
        }

    # 多源：计算分数差和排名差
    scores = [s["min_score"] for s in valid]
    max_diff_score = max(scores) - min(scores)

    ranks = [s["min_rank"] for s in valid if s.get("min_rank") is not None]
    if ranks:
        max_rank = max(ranks)
        max_diff_rank = max(ranks) - min(ranks)
        rank_diff_ratio = max_diff_rank / max_rank if max_rank else 0
    else:
        rank_diff_ratio = 0

    cv_cfg = _get_cv_config()
    score_tolerance = cv_cfg.get("score_tolerance", 5)
    rank_tolerance_ratio = cv_cfg.get("rank_tolerance_ratio", 0.10)

    if max_diff_score <= score_tolerance and rank_diff_ratio <= rank_tolerance_ratio:
        return {
            "best": best,
            "confidence": "高",
            "note": "",
            "sources_used": sources_used,
        }

    score_labels = " vs ".join(str(s) for s in scores)
    return {
        "best": best,
        "confidence": "中",
        "note": f"数据源存在差异（{score_labels}），建议核实官方数据",
        "sources_used": sources_used,
    }
