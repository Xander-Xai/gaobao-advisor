# gaobao Production Deploy Checklist

> **Date**: 2026-06-13 (Updated)
> **Current Status**: Code ready, awaiting deployment decision

---

## ✅ Pre-deploy (已完成)

- [x] All tests passing (`pytest --tb=short -q` → 333/333 ✅)
- [x] CI/CD configured (`.github/workflows/ci.yml` + `pyproject.toml`)
- [x] Database populated: 3,016 schools, 70,000+ scores, 30 provinces
- [x] .gitignore configured (db files, .coverage, egg-info, logs excluded)

## ⏳ Deploy (待执行)

### Option A: Streamlit Cloud (推荐，最快)
```bash
# 1. 推送代码
git push origin master

# 2. 在 https://share.streamlit.io 连接仓库
#    - Repository: yandexuanxuan/xuefeng-agent
#    - Main file: app.py
#    - Python: 3.10

# 3. 在 Advanced Settings → Secrets 中添加:
LLM_API_KEY = "你的API Key"
LLM_PROVIDER = "deepseek"
LLM_MODEL = "deepseek-chat"

# 4. 点击 Deploy
```

### Option B: Docker Compose
```bash
# 1. 配置环境变量
cp .env.production .env.production.local
# 编辑填入真实 LLM_API_KEY

# 2. 构建并启动
docker compose -f docker-compose.prod.yml up -d --build

# 3. 验证健康
curl -f http://localhost:8501/_stcore/health && echo "OK"
```

## ⏳ Post-deploy Verification

- [ ] Streamlit UI loads correctly
- [ ] Chat responds to test query
- [ ] Onboarding 3-step flow works
- [ ] Markdown export downloads correctly
- [ ] Conversation history click-to-restore works
- [ ] WeChat sharing shows correct OG title/description
- [ ] No errors in logs

## 🔒 Security Checklist

- [x] No hardcoded secrets in code
- [x] RAG enabled by default (`ENABLE_RAG_KB=true`)
- [x] Rate limiting active (20 req/hr per IP)
- [x] Session TTL 30 min
- [x] Maintenance page shows when no API key

## 📊 Data Pipeline

- [x] Full import complete: 30 provinces, 3,016 schools, 70,000+ scores
- [x] Yi-fen-yi-duan table: 11,524 records
- [x] Majors taxonomy: 215 majors
- [ ] Enrollment plans: 0 records (optional, not blocking)

## 📦 Git History (Recent)

```
3667c8d docs: first Zhihu tech article
ccbd635 feat: add 3 ready-to-record Douyin scripts
5519ed8 feat: Phase 7+8 deliverables
adca208 feat: Phase 6 content engine deliverables
227d789 fix: repair 2 failing import pipeline tests
```
