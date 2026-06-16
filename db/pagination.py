"""
Cursor-based Pagination for Database Queries.

Solves the "deep pagination" problem in SQLite by using cursor-based
pagination instead of OFFSET/LIMIT, which becomes slow for large offsets.

Example:
    # Traditional OFFSET pagination (slow for large offsets)
    SELECT * FROM scores ORDER BY id LIMIT 50 OFFSET 10000;  # Slow!

    # Cursor-based pagination (fast)
    SELECT * FROM scores WHERE id > :last_id ORDER BY id LIMIT 50;  # Fast!

Usage:
    from db.pagination import paginate_cursor

    # First page
    results, next_cursor = paginate_cursor(
        session, Scores, order_by=Scores.id, limit=50
    )

    # Next page
    results, next_cursor = paginate_cursor(
        session, Scores, order_by=Scores.id, limit=50, cursor=next_cursor
    )
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from sqlalchemy import ColumnElement
from sqlalchemy.orm import Query, Session

T = TypeVar("T")


class PageResult(Generic[T]):
    """Paginated result with cursor."""

    def __init__(
        self,
        items: list[T],
        next_cursor: str | None = None,
        has_more: bool = False,
        total_count: int | None = None,
    ):
        self.items = items
        self.next_cursor = next_cursor
        self.has_more = has_more
        self.total_count = total_count

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "items": [item.__dict__ if hasattr(item, "__dict__") else item for item in self.items],
            "next_cursor": self.next_cursor,
            "has_more": self.has_more,
            "total_count": self.total_count,
        }


def paginate_cursor(
    session: Session,
    model: type[T],
    order_by: ColumnElement,
    limit: int = 50,
    cursor: str | None = None,
    filters: dict[str, Any] | None = None,
    include_total: bool = False,
) -> PageResult[T]:
    """Perform cursor-based pagination.

    Args:
        session: SQLAlchemy session
        model: ORM model class
        order_by: Column to order by (must be unique or combined with unique column)
        limit: Number of items per page
        cursor: Cursor value (last ID from previous page)
        filters: Additional filter conditions
        include_total: Whether to count total items (slower)

    Returns:
        PageResult with items and next cursor

    Example:
        >>> from db.models import School
        >>> results = paginate_cursor(
        ...     session, School, School.id, limit=50
        ... )
        >>> print(results.items)  # First 50 schools
        >>> print(results.next_cursor)  # Cursor for next page
    """
    query = session.query(model)

    # Apply filters
    if filters:
        for key, value in filters.items():
            if value is not None:
                column = getattr(model, key)
                query = query.filter(column == value)

    # Apply cursor
    if cursor:
        query = query.filter(order_by > cursor)

    # Order and limit
    query = query.order_by(order_by).limit(limit + 1)  # Fetch one extra to check has_more

    items = query.all()

    # Check if there are more items
    has_more = len(items) > limit
    if has_more:
        items = items[:limit]  # Remove the extra item

    # Determine next cursor
    next_cursor = None
    if items and has_more:
        last_item = items[-1]
        next_cursor = str(getattr(last_item, order_by.name))

    # Optional: count total (expensive for large tables)
    total_count = None
    if include_total:
        count_query = session.query(model)
        if filters:
            for key, value in filters.items():
                if value is not None:
                    column = getattr(model, key)
                    count_query = count_query.filter(column == value)
        total_count = count_query.count()

    return PageResult(
        items=items,
        next_cursor=next_cursor,
        has_more=has_more,
        total_count=total_count,
    )


def paginate_offset(
    session: Session,
    model: type[T],
    order_by: ColumnElement,
    limit: int = 50,
    offset: int = 0,
    filters: dict[str, Any] | None = None,
    include_total: bool = False,
) -> PageResult[T]:
    """Traditional OFFSET-based pagination (for comparison).

    WARNING: This becomes slow for large offsets (> 10000).
    Use paginate_cursor() instead for better performance.

    Args:
        session: SQLAlchemy session
        model: ORM model class
        order_by: Column to order by
        limit: Number of items per page
        offset: Number of items to skip
        filters: Additional filter conditions
        include_total: Whether to count total items

    Returns:
        PageResult with items (no cursor)
    """
    query = session.query(model)

    # Apply filters
    if filters:
        for key, value in filters.items():
            if value is not None:
                column = getattr(model, key)
                query = query.filter(column == value)

    # Count total if requested
    total_count = None
    if include_total:
        total_count = query.count()

    # Order, offset, and limit
    query = query.order_by(order_by).offset(offset).limit(limit)
    items = query.all()

    # Calculate next offset
    has_more = len(items) == limit
    next_cursor = str(offset + limit) if has_more else None

    return PageResult(
        items=items,
        next_cursor=next_cursor,
        has_more=has_more,
        total_count=total_count,
    )


# ── Helper Functions ────────────────────────────────────────


def encode_cursor(value: Any) -> str:
    """Encode a value as a cursor string.

    For simple IDs, just convert to string.
    For composite cursors, use base64 encoding.
    """
    return str(value)


def decode_cursor(cursor: str) -> Any:
    """Decode a cursor string back to its original value.

    For simple IDs, try to convert back to int.
    """
    try:
        return int(cursor)
    except ValueError:
        return cursor
