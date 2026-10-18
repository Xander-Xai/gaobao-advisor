# 快速体验 gaobao-advisor（合成数据 / 无需 API Key）

> 适用于第一次使用本仓库的开发者。本项目是演示工程，不含真实高校录取数据；不可用于实际志愿填报决策。

## 方式一：Docker（推荐）

准备 Docker，然后在终端执行：

```bash
git clone https://github.com/Xander-Xai/gaobao-advisor.git
cd gaobao-advisor
docker build -t gb-advisor .
docker run --rm -p 8000:8000 gb-advisor
```

打开另一个终端检查：

```bash
curl http://localhost:8000/api/v1/health
curl "http://localhost:8000/api/v1/data/schools?limit=3"
# 知识库检索（默认启用，无需 Key）
curl -X POST http://localhost:8000/api/v1/knowledge/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"平行志愿的投档规则是什么"}'
```

预期健康检查中的 `data_profile` 为 `SYNTHETIC_DEMO`，知识检索状态为
`RAG_ENABLED`（`documents`/`chunks` 为随仓合成语料数量，`integrity_ok=true`）。
院校列表来自程序合成的数据，检索证据来自仓库自带的**原创合成语料**，
均不对应真实招生结果。

Docker 默认运行 FastAPI 后端；它**不会同时启动 Vue 开发服务器**。

## 方式二：本地开发（Python 3.10/3.11 + Node.js）

```bash
git clone https://github.com/Xander-Xai/gaobao-advisor.git
cd gaobao-advisor
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m scripts.seed_demo_data --db data/demo.db --reset
uvicorn server.main:app --reload
```

另开终端运行前端：

```bash
cd frontend
npm ci
npm run dev
```

前端 Vite 默认使用其终端显示的地址（通常为 http://localhost:5173/），如 API 请求不通，需检查开发代理与后端端口配置。Windows PowerShell 虚拟环境激活命令不同，见 Python 官方 venv 文档。

## 测试

```bash
pytest tests/ -q --no-header
ruff check . && ruff format --check .
cd frontend && npm ci && npx vitest run && npm run build
```

可在 [GitHub Actions](https://github.com/Xander-Xai/gaobao-advisor/actions/workflows/ci.yml) 查看最新版 CI 结果。

## 使用边界

- 不需要 LLM Key 即可检查健康状态、合成数据 API 与知识库检索；配置模型是可选操作。
- `ENABLE_RAG_KB=true`（默认，使用随仓合成语料）、`ENABLE_OUTBOUND_FETCH=false`、
  `ENABLE_SEARCH=false` 为默认值；知识检索在语料缺失/损坏时 fail-closed（返回
  `RAG_ERROR`，不编造答案）。
- 未经授权不得分发真实招生数据库、第三方知识语料或历史私人会话。
- 本工程没有生产级并发、可用性或真实 RAG 质量验证；`knowledge/synthetic_demo/`
  只是原创合成演示语料。

返回 [README](README.md) 查看整体架构、安全设计与技术限制。
