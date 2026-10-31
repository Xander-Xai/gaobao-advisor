# Test Resource Isolation

> Scope: Redis and MySQL integration tests. These rules exist because a
> mis-pointed test URL must never delete shared data.

## 1. Redis

### Prohibited

- `FLUSHDB` and `FLUSHALL` are forbidden in tests, regardless of database
  number, URL substring, or environment name.
- Tests must not delete keys outside their own random namespace.

### Implemented

- `tests/test_admin_limits_redis.py` creates one random session root:
  `gaobao:test:limits:<random-hex>`.
- Every limiter namespace and process subprocess uses a child of that root.
- Cleanup scans only `<root>:*` and deletes only those keys.
- The revocation persistence test deletes only a test-owned probe key to model
  Redis key loss; revocation itself is database-backed.
- `test_namespace_cleanup_preserves_foreign_keys` creates a foreign-prefix key,
  runs the cleanup helper, and asserts the foreign key still exists.
- The real Redis service is disposable in `make test-integration`/CI service
  containers, but tests still do not rely on that fact for destructive safety.

### Failure injection

Redis key loss is simulated by deleting the test namespace, not by flushing the
server. This preserves the security property under test (database-persisted
revocation) while keeping shared Redis safe.

## 2. MySQL

### Prohibited

- A database is never considered disposable merely because its name contains
  `test`.
- `MYSQL_TEST_URL` must not equal `DATABASE_URL`.
- Destructive fixtures must not run against a non-empty unmarked database.

### Implemented guard

`tests/mysql_guard.py` enforces:

1. URL scheme is `mysql://` or `mysql+pymysql://`.
2. Database name matches a dedicated test naming convention
   (`*test*`, `*_test`, `test_*`).
3. `MYSQL_TEST_URL` is not exactly `DATABASE_URL`.
4. If the database is empty, create `_gaobao_test_ownership` with an owner row.
5. If the database is non-empty and lacks that marker, refuse before any
   `DROP`/`CREATE`.

All three MySQL destructive fixtures (`test_admin_mysql.py`,
`test_mysql_migrations.py`, `test_worker_integration.py`) call
`ensure_test_database()` before dropping tables.

### Cleanup

- Fixtures drop only SQLAlchemy metadata tables and `alembic_version`.
- The ownership marker is retained for the disposable test database.
- `make test-integration` starts dedicated MySQL/Redis containers and removes
  only those named test containers via a shell `trap` on success/failure.
- No database is dropped, and no production connection is used.

### Negative tests

`tests/test_mysql_guard.py` asserts that a non-test database name, a URL equal
to `DATABASE_URL`, and a non-MySQL URL are all rejected before destructive work.

## 3. Verification

```bash
make test-integration
# 27 passed: MySQL 8 + Redis limiter 11 + Redis worker 3 + dual-worker 5

pytest tests/test_mysql_guard.py -q
pytest tests/test_admin_limits_redis.py -q
```

The only destructive actions are against resources created by the test run and
guarded by the marker/namespace rules above.
