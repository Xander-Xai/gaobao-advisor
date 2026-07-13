import logging


def test_log_reference_does_not_expose_session_identifier():
    from server.privacy import safe_log_reference

    session_id = "applicant-name-score-612-secret-session"
    reference = safe_log_reference(session_id)

    assert session_id not in reference
    assert reference.startswith("ref-")


def test_rag_cache_debug_logs_do_not_expose_user_message(caplog):
    from server.services.rag_cache import RagCache

    private_message = "我是河北考生，身份证号和分数都属于隐私"
    cache = RagCache(redis_url=None)

    with caplog.at_level(logging.DEBUG):
        cache.set(private_message, {"score": 612}, {"result": "synthetic"})
        assert cache.get(private_message, {"score": 612}) == {"result": "synthetic"}

    assert private_message not in caplog.text
    assert "身份证号" not in caplog.text
