# ADR-003: SQLite with WAL mode and joinedload for N+1 prevention

**Status:** Accepted (implemented)
**Date:** 2026-06

## Context
The admission_scores → schools → majors relationship creates N+1 queries when serializing results.
SQLite under default journal mode blocks reads during writes.

## Decision
1. Enable WAL mode + busy_timeout=5000 at engine connect time
2. Use SQLAlchemy `joinedload()` for school/major relationships in query functions

## Consequences
+ WAL enables concurrent reads during writes (critical for import pipeline)
+ busy_timeout prevents "Database Is Locked" errors under load
+ joinedload reduces N+1 from O(1+N) to O(1) for score queries
- WAL creates .db-wal and .db-shm files
- joinedload can cause cartesian products if misused (not an issue here due to 1:1 relationships)