# Deployment guide

This guide covers the no-key community demo, a production deployment with real
data, and the hard limits you must know before serving anything to real users.

> Before deploying for real users, read
> `SECURITY_AND_LICENSE_BLOCKERS.md`. The project is `PUBLIC_RELEASE_BLOCKED`
> until the data-rights review is recorded. Do not serve imported data to the
> public on the basis of this guide alone.

## 1. Requirements

| Component | Version |
|---|---|
| Python | 3.10 or 3.11 |
| Node.js | 20 (frontend build only) |
| Docker | 24+ with BuildKit |
| Disk | ~1.5 GB for the image; ~110 MB + WAL for the database |

The application stores everything in SQLite. There is no external database,
message queue or cache dependency. Redis is optional and only used for the RAG
cache; without it the cache falls back to memory.

## 2. Community demo (no keys)

```bash
cp .env.example .env
docker compose up --detach --build api frontend
```

This starts:

- `api` on `:8000` — FastAPI, seeded with synthetic data by
  `scripts/seed_demo_data.py` at start-up;
- `frontend` on `:3080` — the built Vue SPA served by nginx;
- `nginx` on `:80` (optional, in `docker-compose.yml`).

The `api` service sets `LLM_PROVIDER=demo`, `ENABLE_RAG_KB=false` and
`VOICE_ENABLED=false`, and routes `GAOBAO__DB_PATH` to a named volume
`gaobao-demo-data`. No API key is read. Verify:

```bash
curl -s http://localhost:8000/api/v1/health
# {"status":"ok","mode":"demo","llm_provider":"demo",
#  "optional_services":{"rag":"disabled","voice":"disabled"}, ...}
```

Every chat reply is prefixed with the community-demo disclosure. See
`DEMO_MODE_CONTRACT.md`.

### Building without direct PyPI access

If the build host cannot reach `files.pythonhosted.org` reliably, pre-download
the wheels and let the Dockerfile pick them up:

```bash
pip download -r requirements.lock -d wheels/ --only-binary=:all:
docker compose build api
```

The Dockerfile installs from `wheels/` with `--no-index` when at least one
`.whl` is present, and otherwise installs from the official PyPI index. The
index is never replaced with a third-party mirror.

## 3. Production with real data

1. Set `APP_ENV=production` and a real provider in `.env` (see `.env.example`).
   Set `SESSION_SECRET` explicitly — the application warns and generates an
   ephemeral secret otherwise, which breaks sessions across processes.
2. Populate the database. Importers live in `scripts/import_*.py`. Confirm you
   have the right to use the data first (`SECURITY_AND_LICENSE_BLOCKERS.md §B2`).
3. Verify the data before serving it:

   ```bash
   python scripts/data_quality_report.py --database data/gaokao.db
   ```

   A `blocked` verdict means the report could not establish coverage or
   freshness. Do not deploy on a blocked verdict.
4. Deploy with the production compose file:

   ```bash
   docker compose -f docker-compose.prod.yml --profile nginx up -d
   ```

   This binds the API to `127.0.0.1:8000` only and mounts `./data` for
   persistence. Put TLS termination in front of it.

## 4. Configuration reference

| Variable | Purpose | Demo default |
|---|---|---|
| `APP_ENV` | Reported as `mode` when the provider is not `demo` | `development` |
| `LLM_PROVIDER` | `demo` or a configured provider name | `demo` |
| `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY` | Provider connection | `demo://local` |
| `ENABLE_RAG_KB` | Enables the knowledge-base retrieval stage | `false` |
| `RAG_EMBEDDING_PROVIDER` | `keyword` needs no key | `keyword` |
| `VOICE_ENABLED` | Enables the WebSocket speech endpoints | `false` |
| `SESSION_SECRET` | HMAC key for session tokens | empty (ephemeral) |
| `CORS_ORIGINS` | Comma-separated allowed origins | localhost defaults |
| `GAOBAO__DB_PATH` | SQLite path | `data/gaokao.db` |
| `GAOBAO__DATA_DIR` | Base directory for data and reports | `data/` |

## 5. Backups

`scripts/backup_db.sh` is **not** safe to rely on: it copies the database file
and gzips it (producing a `gzip → sqlite` payload) while naming the result
`.sql.gz`, and a copy taken while the database is in WAL mode is not
transactionally consistent.

Use the online backup API instead:

```bash
python -c "from scripts.db_archive import make_sqlite_backup; \
  make_sqlite_backup('data/gaokao.db', 'backups/gaokao_db_<stamp>.db')"
```

`make_sqlite_backup` returns the destination and an integrity report. Record the
SHA-256 (`sha256sum`) alongside the file. To restore, see
`DATA_RECOVERY_AND_QUALITY.md §3`; `scripts/restore_db.py` is dry-run by default.

## 6. Health, metrics and monitoring

| Endpoint | Purpose |
|---|---|
| `/api/v1/health` | Liveness and mode |
| `/metrics` | Prometheus exposition |
| `/docs` | OpenAPI UI |

`docker-compose.monitoring.yml` brings up Prometheus and Grafana with the
dashboard in `deploy/grafana/dashboards/ai-quality-dashboard.json`.

## 7. Verification after deploy

```bash
curl -fsS http://<host>/api/v1/health
curl -fsS http://<host>/ > /dev/null
curl -fsSN -H 'Content-Type: application/json' \
  -d '{"session_id":"smoke","message":"你好"}' http://<host>/api/v1/chat | head
```

For a non-demo deployment, `mode` must not be `demo`, and the reply must not
contain the community-demo disclosure, because that disclosure states the data
is synthetic.

## 8. Known operational limits

- Single-node only. SQLite plus a single uvicorn process is the supported shape.
- No built-in multi-tenancy. Session tokens scope access within one deployment.
- The vector index is optional; with `RAG_EMBEDDING_PROVIDER=keyword` retrieval
  is lexical.
- `streamlit` remains in `requirements.txt` for the legacy UI. It is not started
  by any compose service.
