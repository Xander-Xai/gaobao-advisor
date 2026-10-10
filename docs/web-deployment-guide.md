# 部署指南 — gaobao-advisor v3.0

> 支持 Docker Compose 部署和裸机部署。

---

## 方式一：Docker Compose（推荐）

### 前置条件
- Docker 和 Docker Compose v2+
- LLM API Key（Agnes Flash / DeepSeek / Qwen / GLM / OpenAI 任选）

### 步骤

#### 1. 克隆仓库
```bash
git clone https://github.com/your-org/gaobao-advisor.git
cd gaobao-advisor
```

#### 2. 配置环境变量
```bash
cp .env.example .env
# 编辑 .env，填入你的 API Key
```

#### 3. 启动服务
```bash
docker compose up -d
```

前端将在 `http://localhost:3080` 访问，API 在 `http://localhost:8000`。

#### 4. 验证健康状态
```bash
curl -f http://localhost:8000/api/v1/health
# {"status":"ok","version":"3.1.0","database":"connected"}
```

---

## 方式二：裸机部署

### 前置条件
- Python 3.10+
- Node.js 20+
- LLM API Key

### 步骤

#### 1. 克隆 & 安装
```bash
git clone https://github.com/your-org/gaobao-advisor.git
cd gaobao-advisor
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock
```

#### 2. 前端构建
```bash
cd frontend
npm ci
npm run build
cd ..
```

#### 3. 配置
```bash
cp .env.example .env
# 编辑 .env，填入 API Key
```

#### 4. 启动
```bash
# 启动后端 API（生产建议使用 gunicorn + uvicorn workers）
uvicorn server.main:app --host 0.0.0.0 --port 8000 &

# 启动前端开发服务器（或配置 nginx 代理 dist/）
cd frontend && npm run dev -- --port 3080
```

---

## 生产部署 Checklist

参考 [deploy-checklist.md](deploy-checklist.md) 了解完整上线检查项。

### 关键安全配置

```bash
# 1. 设置 SESSION_SECRET（所有 worker 共享）
export SESSION_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")

# 2. 设置 CORS 白名单
export CORS_ORIGINS=https://your-domain.com

# 3. 设置 LLM API Key
export LLM_API_KEY=sk-your-key

# 4. 设置 APP_ENV=production（启用生产模式校验）
export APP_ENV=production
```

### 生产 Docker Compose
```bash
docker compose -f docker-compose.prod.yml --profile nginx up -d --build
```

---

## 架构概览

```
nginx (:80 / :443)
  |-- /api/*      --> FastAPI (port 8000)
  |                   |-- /api/v1/chat       (SSE streaming)
  |                   |-- /api/v1/data/*     (院校/分数/计划)
  |                   |-- /api/v1/knowledge/* (RAG 知识检索)
  |                   |-- /api/v1/profile/*  (用户画像)
  |                   |-- /api/v1/report/*   (报告生成/导出)
  |-- /ws/*       --> FastAPI (port 8000, WebSocket)
  |                   |-- /api/v1/ws/call   (语音通话)
  |-- /           --> Vue 3 SPA (nginx serving dist/)
```

---

## 环境变量参考

| 变量 | 必需 | 默认值 | 说明 |
|------|------|--------|------|
| `LLM_API_KEY` | ✅ | - | LLM 提供商 API Key |
| `LLM_PROVIDER` | | `ollama` | Provider 名称 (agnes-flash-1/agnes-flash-2/glm-4/deepseek/qwen/moonshot/openai/ollama) |
| `LLM_BASE_URL` | | `http://localhost:11434/v1` | API 地址 |
| `LLM_MODEL` | | `qwen2.5:7b` | 模型名 |
| `SESSION_SECRET` | ✅* | 自动生成 | 生产环境必须设置 |
| `CORS_ORIGINS` | | `localhost:*` | 逗号分隔的允许域名 |
| `SILICONFLOW_API_KEY` | | - | RAG 向量嵌入 API Key |
| `SENTRY_DSN` | | - | 错误监控 |
| `APP_ENV` | | `development` | 设为 `production` 启用生产校验 |
| `GAOBAO__DB_PATH` | | `data/gaokao.db` | SQLite 数据库路径 |
| `GAOBAO__VOICE__API_KEY` / `DASHSCOPE_CHAT_API_KEY` | | - | 电话模式口语化渲染；缺失时回退原文本 |
| `QUALITY_JUDGE_ALLOW_PLACEHOLDER_KEY` | | `false` | 仅本地 Ollama 调试时允许无 Key 占位调用；生产保持关闭 |

> * `SESSION_SECRET` 在生产环境为强必需，缺失会阻止服务启动。

---

## 常见问题

### Docker 启动失败
- 检查 Docker 是否运行：`docker ps`
- 检查端口冲突：`lsof -i :8000` / `lsof -i :3080`
- 查看容器日志：`docker compose logs api`

### API Key 费用过高
- 使用本地 Ollama 模型（最经济）
- 设置 `LLM_MAX_TOKENS` 限制回复长度
- 参考 [faq-troubleshooting.md](faq-troubleshooting.md)

### 前端无法连接后端
- 检查 `VITE_API_BASE_URL` 是否指向正确的后端地址
- 检查 nginx 反向代理路径配置
- 跨域检查：`CORS_ORIGINS` 是否正确设置

### 多 Worker 部署
所有 Worker 必须使用相同的 `SESSION_SECRET`，否则会话令牌验证失败。
```yaml
# docker-compose.yml
environment:
  - SESSION_SECRET=${SESSION_SECRET}  # 所有 Worker 必须相同
```
