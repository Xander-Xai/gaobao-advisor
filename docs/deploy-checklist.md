# gaobao Production Deploy Checklist

> **Date**: 2026-06-13
> **Branch**: `feat/next-phase`
> **Sprint**: 1-4 Complete

---

## Pre-deploy

- [x] All tests passing (`pytest --tb=short -q` → 333/333 ✅)
- [x] CI/CD configured (`.github/workflows/ci.yml` + `pyproject.toml`)
- [x] `.env.production` configured with real API key
- [x] Database backed up (check `data/backups/`)

## Deploy

### Option A: Docker Compose
```bash
# 1. Copy and configure environment
cp .env.production .env.production.local
# Edit .env.production.local with real LLM_API_KEY

# 2. Build and start
docker compose -f docker-compose.prod.yml up -d --build

# 3. Verify health
curl -f http://localhost:8501/_stcore/health && echo "OK"
```

### Option B: Streamlit Cloud
```bash
# Push feat/next-phase to GitHub
git push origin feat/next-phase
# Connect repo in Streamlit Cloud
# Set secrets: LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
# Deploy
```

## Post-deploy Verification

- [ ] Streamlit UI loads correctly
- [ ] Chat responds to test query
- [ ] Onboarding 3-step flow works
- [ ] Markdown export downloads correctly
- [ ] Conversation history click-to-restore works
- [ ] No errors in logs: `docker logs gaobao-advisor --tail 30`

## Security Checklist

- [ ] No hardcoded secrets in code
- [ ] RAG enabled by default (`ENABLE_RAG_KB=true`)
- [ ] Rate limiting active (20 req/hr per IP)
- [ ] Session TTL 30 min
- [ ] SQLite WAL files restricted (0600)
- [ ] Maintenance page shows when no API key

## Rollback

```bash
# Docker Compose
docker compose -f docker-compose.prod.yml down
# Restore from backup
gunzip -c data/backups/gaobao_YYYYMMDD_HHMMSS.db.gz | sqlite3 data/gaokao.db
docker compose -f docker-compose.prod.yml up -d

# Streamlit Cloud
# Go to Streamlit Cloud dashboard → select previous deployment → revert
```

## Data Pipeline

- [ ] Full import running in background (PID check: `ps aux | grep import_baidu_gaokao`)
- [ ] Data targets: 3,000+ schools, 100,000+ scores, 30 provinces
- [ ] Daily backup cron: `0 2 * * * /path/to/scripts/backup_db.sh >> logs/backup.log 2>&1`

## Key Commits (feat/next-phase)

| Commit | Description |
|--------|-------------|
| `58c7a32` | fix: test_import_schools_fills_missing_city |
| `e58d8a9` | feat: CI/CD pipeline, pyproject.toml, Makefile |
| `9846e1d` | feat: rebrand from xuefeng to gaobao |
| `6035a6e` | feat: enable RAG by default with keyword fallback |
| `51b9aa7` | feat: show maintenance page when LLM API key not configured |
| `9311f6c` | feat: production hardening — rate limiting, session TTL |
| `2e21ba8` | feat: production Docker config and database backup script |
| `c05282c` | feat: OPC commercial hooks — WeChat QR, event tracking |