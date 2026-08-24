"""Regression tests for profile/query-state persistence."""

import os
import sys
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.crud import load_conversation_slots, save_slots
from db.database import get_session, init_db
from db.models import Conversation
from server.routes.profile import _save_query_state
from server.soul_query import QueryState


def test_save_query_state_preserves_existing_profile_slots():
    """Saving soul-query state must not replace previously collected profile data."""
    init_db()
    session_id = f"test-query-state-{uuid4().hex}"
    original_slots = {
        "province": "广东",
        "score": 612,
        "subject": "物理",
        "interest": "计算机",
    }

    db = get_session()
    try:
        save_slots(db, session_id, original_slots)
    finally:
        db.close()

    query_state = QueryState(
        round_count=2,
        asked_fields=["province", "score_rank"],
        skipped_fields=["family"],
    )
    _save_query_state(session_id, query_state)

    db = get_session()
    try:
        persisted = load_conversation_slots(db, session_id)
        assert persisted is not None
        assert persisted["province"] == "广东"
        assert persisted["score"] == 612
        assert persisted["subject"] == "物理"
        assert persisted["interest"] == "计算机"
        assert persisted["_query_state"] == {
            "round_count": 2,
            "asked_fields": ["province", "score_rank"],
            "skipped_fields": ["family"],
        }
    finally:
        (
            db.query(Conversation)
            .filter(Conversation.session_id == session_id)
            .delete(synchronize_session=False)
        )
        db.commit()
        db.close()
