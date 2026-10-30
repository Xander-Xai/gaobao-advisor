"""Quality scan must not degrade into two queries per school (N+1)."""

from __future__ import annotations

from sqlalchemy import event

from server.admin.quality import collect_issues


def test_quality_scan_query_count_is_bounded(admin_factory):
    session = admin_factory()
    statements: list[str] = []

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    try:
        event.listen(session.bind, "before_cursor_execute", before_cursor_execute)
        checked, issues = collect_issues(session, {})
        event.remove(session.bind, "before_cursor_execute", before_cursor_execute)
    finally:
        session.close()

    # 8 schools in the fixture: one school query + one score chunk + one plan
    # chunk. Allow a small margin for future eager-loading, but reject N+1.
    assert len(statements) <= 6, statements
    assert checked >= 8
    assert any(issue["rule_code"] == "score_out_of_range" for issue in issues)
