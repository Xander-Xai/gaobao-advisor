# gaobao Production Deploy Checklist

> **Date**: 2026-06-28 (Updated)
> **Current Status**: Code verified for production pre-deploy; run post-deploy checks against the target domain

---

## ✅ Pre-deploy

- [x] All tests passing (`pytest tests/ -q --timeout=60 --timeout-method=thread` → 816 passed / 1 skipped, coverage 77.78% ✅)
- [x] Database populated: 3,016+ schools, 215+ majors, 35万+ scores, 30 provinces
- [x] .gitignore configured (db files, .coverage, egg-info, logs excluded)
- [x] Rate limiting active (20 req/s per IP, burst 40)
- [x] Security middleware active (injection detection, SSRF defense, XSS sanitization)
- [x] CSP headers configured with nonce-based script/style policies
- [x] CORS restricted to configured origins
- [x] Sentry error monitoring configured
- [x] Prometheus metrics endpoint at `/metrics`

## ⏳ Deploy Steps

### Docker Compose 部署（推荐）

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 LLM_API_KEY、SESSION_SECRET、CORS_ORIGINS

# 2. 构建并启动
docker compose -f docker-compose.prod.yml --profile nginx up -d --build

# 3. 验证健康
curl -f http://localhost:8000/api/v1/health
# 预期输出: {"status":"ok","version":"3.1.0","database":"connected"}

# 4. 配置 HTTPS（推荐使用 Caddy / Certbot + Let's Encrypt）
```

### 关键环境变量

| 变量 | 生产环境必须设置 | 说明 |
|------|-----------------|------|
| `LLM_API_KEY` | ✅ | LLM 提供商 API Key |
| `SESSION_SECRET` | ✅ | 用于 HMAC 会话签名，所有 worker 共享 |
| `CORS_ORIGINS` | ✅ | 前端域名白名单 |
| `SILICONFLOW_API_KEY` | ✅ | RAG 知识检索 |
| `APP_ENV=production` | ✅ | 启用生产模式校验 |
| `SENTRY_DSN` | 推荐 | 错误监控 |
| `GAOBAO__VOICE__API_KEY` / `DASHSCOPE_CHAT_API_KEY` | 可选 | 电话模式口语化渲染；缺失时回退原文本 |
| `QUALITY_JUDGE_ALLOW_PLACEHOLDER_KEY` | 否 | 默认关闭；仅本地 Ollama 调试时可设为 `true` |

## ⏳ Post-deploy Verification

- [ ] API health check 返回 `{"status":"ok","database":"connected"}`
- [ ] 前端页面正常加载（http://your-domain.com）
- [ ] 发送一条聊天消息后 SSE stream 正常返回
- [ ] `/api/v1/profile` 使用 Bearer token 鉴权正常
- [ ] `/api/v1/knowledge/search` RAG 搜索正常
- [ ] `/api/v1/report/generate` 报告生成正常（请求体需 `session_id + token`）
- [ ] `/api/v1/report/{report_id}` / `html` / `cover.svg` 读取正常（Query 需 `session_id + token`）
- [ ] `/metrics` Prometheus 端点可访问
- [ ] 错误日志中无异常

## 🔒 Security Verification

- [x] No hardcoded secrets in codebase
- [x] API Keys only in `.env` or environment (excluded by `.gitignore`)
- [x] Prompt injection detection active on chat/feedback/onboarding endpoints
- [x] Rate limiting per IP (token bucket)
- [x] CORS whitelist enforced
- [x] CSP header with nonce for inline scripts
- [x] SSRF protection for outbound HTTP calls
- [x] XSS sanitization via HTML tag stripping + DOMPurify
- [x] Report read/export verifies both token and report session ownership
- [x] LLM Judge and Voice rendering fail closed when external provider config is missing
- [x] Auth helpers centralized in server/auth.py (require_bearer_auth and require_token_auth)
- [x] SSE error and degraded events handled by frontend
- [x] Report title dynamic based on scene (no longer hardcoded)
- [x] Message and session token persistence via localStorage

## 🔄 Frontend-Backend Alignment

- [x] All backend endpoints have corresponding frontend API client methods
- [x] SSE event types (error, degraded, slots, emotion, structured, token, quality, done) handled by frontend
- [x] Report generation UI trigger available in ChatView
- [x] Voice WebSocket error messages handled by useVoice composable
- [ ] Voice end-to-end functionality requires ASR service integration
- [ ] Onboarding frontend UI not yet implemented

## 📊 Data Pipeline

- [x] Full import: 30 provinces, 3,016+ schools, 35万+ scores
- [x] Yi-fen-yi-duan table: 11,524+ records
- [x] Majors taxonomy: 215+ majors
- [x] RAG Knowledge base: 9 groups (G1-G9) + 555+ expert quotes
- [ ] Enrollment plans (optional, not blocking)

## 🐳 Docker Checklist

- [ ] `.env` configured (not committed to git)
- [ ] `APP_ENV=production` set
- [ ] `SESSION_SECRET` explicitly set
- [ ] HTTPS configured (Caddy / nginx + Let's Encrypt)
- [ ] Database volume mounted correctly: `./data:/app/data`
- [ ] Non-root user configured in Dockerfile (Phase 4.1)
- [ ] Container resource limits set (CPU/Memory)
- [ ] Health check configured
