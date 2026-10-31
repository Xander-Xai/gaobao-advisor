# Administrator Authentication Hardening

> Scope: `server/admin/*`, Vue admin workbench, Redis/MySQL/Compose deployment.
> Date: 2026-10-31. This is an implementation record, not a production audit certificate.

## 1. Existing baseline

- Separate admin token domain: `aud=gaobao-admin`, HMAC-SHA256, claims
  `sub/role/iat/exp/jti`; anonymous chat tokens cannot cross over.
- PBKDF2-HMAC-SHA256 credentials injected from the environment; production
  plaintext `ADMIN_PASSWORD` is rejected.
- RBAC hierarchy `viewer < operator < admin`; role is resolved from current
  configuration on every request (demotion/deletion is effective immediately).
- Production startup fails closed when admin is enabled without
  `ADMIN_TOKEN_SECRET`.
- Existing audit log records actor/role/action/resource/request id with
  recursive redaction.
- Token is kept in `sessionStorage` (XSS-readable); no cookies/CSRF surface.

## 2. Threat model and controls

| Threat | Risk | Control | Evidence |
|---|---|---|---|
| Stolen admin token remains valid until expiry | High | DB-persisted `jti` revocation; logout revokes current token; all replicas check DB | `server/admin/revocation.py`, `test_admin_security.py` |
| Redis restart/data loss restores a revoked token | High | Revocation is in SQLite/MySQL, not Redis; Redis flush test | `test_revocation_survives_redis_flush` |
| Brute force / credential stuffing | High | Redis atomic sliding window per IP and per username; 429 + `Retry-After` | `test_admin_limits_redis.py`, `test_admin_security.py` |
| Multi-account rotation from one IP | High | IP-dimension counter; per-username counter; both checked before auth | `test_same_ip_multi_account_rotation_is_limited` |
| Multi-replica rate-limit bypass | High | Shared Redis key namespace + Lua script; two clients/processes tested | `test_two_instances_share_the_same_counter`, `test_two_processes_share_one_redis_counter` |
| Spoofed `X-Forwarded-For` | High | Default ignore; only explicit `ADMIN_TRUSTED_PROXIES`; right-to-left chain | `server/admin/client_ip.py`, trusted-proxy tests |
| Redis outage silently falls back to memory | High | `auto`/`redis` returns 503 `SECURITY_BACKEND_UNAVAILABLE`; production + memory fails startup | `test_redis_backend_unavailable_is_503_not_429`, `test_production_memory_backend_fails_startup` |
| Deleted/demoted admin keeps access | High | Current config lookup + current role; revocation check after signature | `test_deleted_admin_and_role_downgrade_take_effect` |
| Invalid/missing jti or audience | Medium | Strict jti regex, audience/expiry checks, signature first | `test_missing_or_invalid_jti_is_rejected`, audience test |
| Token in logs/Redis keys | High | Only HMAC-SHA256 `jti` hash and IP hash stored; raw token never logged/keyed | `revocation.py`, `client_ip.py`, audit test |
| Redis key growth | Medium | Sorted-set TTL = window; per-key cap is the limit; namespace versioned | Lua `PEXPIRE`, TTL test |
| Redis outage breaks public read API | Low | Only admin security endpoints fail closed; public read APIs unchanged | full regression |

## 3. Redis limiter design

- Backend: `RedisSlidingWindowLimiter` in `server/admin/limits.py`.
- One Lua `EVAL` per decision: remove scores older than the window, `ZCARD`,
  reject with retry, or `ZADD` + `PEXPIRE`. No client-side GET/SET race.
- Time comes from Redis `TIME`, so replicas do not depend on host clock skew.
- Key: `ADMIN_RATE_LIMIT_NAMESPACE:<scope>:<hashed client/identity>`.
  Raw IP/username/token never appear in Redis.
- Login: both `ip:<hash>` and `user:<hash>` keys are checked.
- Job creation: both operator `user:<hash>` and `ip:<hash>` keys are checked.
- Limits: login 8/min; job creation 20/min (per dimension).
- Backend selection:
  - `ADMIN_RATE_LIMIT_BACKEND=auto` (default): Redis when `REDIS_URL` exists;
    memory only outside production; otherwise unavailable.
  - `memory`: explicit local/test only; production startup fails.
  - `redis`: require Redis; runtime outage returns 503.
- Redis timeout: 1s connect/socket. Failure raises
  `SecurityBackendUnavailable`; routes return 503, never 429 or 200.

## 4. Token revocation design

- Table: `admin_token_revocations` (`jti_hash`, `username`, `expires_at`,
  `created_at`), migration `20261031_0003`.
- `jti_hash = HMAC-SHA256(ADMIN_TOKEN_SECRET, jti)`; raw token/jti is not stored.
- Signature, audience, expiry, current user and current role are validated
  before the revocation lookup.
- `POST /api/v1/admin/auth/logout` revokes the current token, writes an
  `admin.logout` audit event, returns 204; repeated logout is idempotent.
- Other tokens for the same admin remain valid.
- Expired revocation rows are cleaned on new revocations; a revoked token is
  rejected until its own `exp`, then naturally invalid.
- Database is the persistence boundary. Redis restart/flush cannot restore a
  revoked token. If the DB is unavailable, admin requests fail closed with 503.
- Logout with an already revoked but otherwise valid token returns 204; all
  other endpoints return 401 `ADMIN_TOKEN_REVOKED`.

## 5. Trusted proxy boundary

- Default: `ADMIN_TRUSTED_PROXIES` empty; `X-Forwarded-For` is ignored and the
  direct peer is used.
- Only when the direct peer is in a configured CIDR do we parse the forwarding
  chain. We walk right-to-left, skip trusted hops, and return the first
  untrusted address. The left-most value is never trusted directly.
- Invalid forwarding values fall back to the direct peer.
- IPv6 and IPv4-mapped IPv6 are normalized; IPv6 brackets/ports are handled.
- The same normalized identity feeds rate limiting and audit hashing.
- Production Compose does **not** hardcode a proxy subnet or IP. Default is
  empty (ignore XFF); operators must set the exact Nginx/proxy CIDR in
  `ADMIN_TRUSTED_PROXIES`. Direct API access remains untrusted.
- Operators using an external proxy must set the exact proxy CIDR; do not set
  `0.0.0.0/0`.

## 6. Fail-closed matrix

| Environment | Redis | Backend | Admin login/job behavior |
|---|---|---|---|
| Local/test | absent | memory | allowed (explicit development mode) |
| Full Compose | present | redis (auto) | Redis Lua limit; outage -> 503 |
| Production | present, `ADMIN_RATE_LIMIT_BACKEND=redis` | redis | Redis Lua limit; outage -> 503 |
| Production | absent | unavailable | startup fails when admin enabled |
| Production | explicit `memory` | unavailable | startup fails |
| Any | revocation DB down | n/a | admin requests 503 |

Public chat/RAG/data endpoints do not use the admin limiter and are unaffected.

## 7. Configuration

```env
ADMIN_RATE_LIMIT_BACKEND=auto          # auto|memory|redis
ADMIN_RATE_LIMIT_NAMESPACE=gaobao:admin:ratelimit:v1
ADMIN_TRUSTED_PROXIES=                 # e.g. 172.30.0.10/32; empty = ignore XFF
REDIS_URL=redis://redis:6379/0         # required in production when admin enabled
```

`scripts/setup_full_env.py` writes `ADMIN_RATE_LIMIT_BACKEND=redis`.
`docker-compose.prod.yml` provides a private Redis service. Trusted proxy
addresses are deployment-specific and must be set explicitly.

## 8. Verification

```bash
# SQLite/unit security tests
pytest tests/test_admin_security.py tests/test_admin_auth.py -q

# Real Redis 7: atomic concurrency, multi-client, multi-process, TTL, revocation
REDIS_TEST_URL=redis://127.0.0.1:6380/0 \
  pytest tests/test_admin_limits_redis.py -q

# MySQL migration incl. revocation table
MYSQL_TEST_URL=... pytest tests/test_mysql_migrations.py -q

# Full stack
make test-integration
# or CI Full Compose E2E
```

CI keeps the existing 10 jobs and adds these tests to the existing
`MySQL + Redis + Admin Smoke` job; no security scan or coverage gate is removed.

## 9. Residual risks

- `sessionStorage` token remains XSS-readable; CSP and no third-party scripts
  reduce but do not eliminate this.
- No MFA/OIDC, refresh-token rotation, or device/session management UI.
- Redis limiter is single-region; multi-region latency/partition policy is not
  tested.
- Revocation table grows with revocations until expiry; cleanup runs on new
  revocations, not a background scheduler.
- No production load/SLA claim; see Issue #38.
- Redis data loss does not restore revoked tokens because revocation is in the
  database; however database loss/restore must be treated as a security event.
