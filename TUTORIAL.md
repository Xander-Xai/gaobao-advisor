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

### 端到端 Agent 演示（合成画像）

```bash
curl -N -X POST http://localhost:8000/api/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{
    "session_id": "demo-session-001",
    "scene": "gaokao",
    "message": "我是示例省·甲的物理类考生，600分，想报计算机"
  }'
```

可复核的事件序列（无 LLM Key 时的实测行为）：

1. `slots` — 抽取到 `province=示例省·甲`、`score_rank=600分`、`score=600`、
   `subject=物理`、`interest=计算机`；
2. `structured` — 结构化卡片包含分数、匹配院校（名称带「（合成）」）与位次分析；
3. `sources` — 检索证据及 `chunk_id` / `source`（来自 `knowledge/synthetic_demo/`）；
4. `degraded` — 明确提示「未配置 LLM Key，已使用基于结构化数据的确定性模板答复」；
5. `token` / `done` — SSE 流式文本与 HMAC `session_token`。

> 首次请求会**忽略调用方传入的 `session_id`**，返回服务端生成的会话 ID；续聊需携带
> `Authorization: Bearer <session_token>`。以上输出只演示软件行为，不是真实志愿建议。

## 方式二：本地开发（Python 3.10/3.11 + Node.js）

```bash
git clone https://github.com/Xander-Xai/gaobao-advisor.git
cd gaobao-advisor
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m scripts.seed_demo_data --db data/demo.db --reset
export DATABASE_URL=sqlite:///data/demo.db   # 连接刚生成的合成库（Docker 已自动设置）
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

## 面试演示脚本（可复现，面向 RAG / Agent 岗位）

下面的脚本只依赖标准库，对着无 Key 的本地/Docker 后端运行即可复现「问题 → 槽位抽取 →
LangGraph 路由 → 结构化查询 / BM25 RAG → 证据组装 → 生成或确定性降级 → SSE → Vue 展示」
全链路。每一段都能指向源码或测试，不含任何编造指标。

```python
import json, urllib.request, urllib.error

BASE = "http://localhost:8000/api/v1"

def sse(message, session_id, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        f"{BASE}/chat",
        data=json.dumps({"session_id": session_id, "scene": "gaokao", "message": message}).encode(),
        headers=headers,
    )
    events = []
    with urllib.request.urlopen(req) as resp:
        for raw in resp:
            line = raw.decode().strip()
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
    return events

# ① 完整画像 → data_query + rag_retrieve（结构化查询与知识检索分工）
full = sse("我是示例省·甲的物理类考生，600分，想报计算机，平行志愿投档规则是什么", "client-id-ignored")
full_done = next(e for e in full if e["type"] == "done")
print("events:", [e["type"] for e in full])
print("has structured card:", any(e["type"] == "structured" for e in full))
print("has sources:", any(e["type"] == "sources" for e in full))

# ② 不完整画像 → 追问分支（不生成无依据结论）
incomplete = sse("你好", "client-id-ignored")
print("incomplete events:", [e["type"] for e in incomplete])

# ③ 会话所有权：首次匿名由服务端签发 session + 令牌
tok = full_done["session_token"]
print("server session:", full_done["session_id"])

# ④ 续聊需令牌（合法）；跨会话访问被拒绝（401）
sse("那计算机专业现在还推荐吗", full_done["session_id"], tok)
try:
    urllib.request.urlopen(urllib.request.Request(
        f"{BASE}/profile/not-this-session", headers={"Authorization": f"Bearer {tok}"}))
except urllib.error.HTTPError as e:
    print("cross-session profile status:", e.code)  # 401
```

```bash
# ⑤ 有证据 vs 无证据（no match ≠ 检索故障）
curl -s -X POST http://localhost:8000/api/v1/knowledge/search \
  -H 'Content-Type: application/json' -d '{"query":"平行志愿的投档规则是什么"}' | python -m json.tool
curl -s -X POST http://localhost:8000/api/v1/knowledge/search \
  -H 'Content-Type: application/json' -d '{"query":"量子缠结与超导磁悬浮技术前沿"}' | python -m json.tool
# 第一条 has_evidence=true 且带 citations；第二条 has_evidence=false（语料健康但无匹配）

# ⑥ 存活 / 就绪 / 能力降级分离
curl -s http://localhost:8000/api/v1/health/live
curl -s http://localhost:8000/api/v1/health/ready
curl -s http://localhost:8000/api/v1/health
```

可在源码/测试中复核的对应点：

| 演示点 | 证据位置 |
|---|---|
| 完整/不完整画像分支 | `server/graph/nodes/route.py`、`server/graph/graph.py`；`tests/test_rag_demo_e2e.py::TestRouting` |
| SQL 与 RAG 职责划分 | `server/graph/nodes/data_nodes.py`、`server/graph/nodes/rag_node.py` |
| 有证据 / 无证据差异 | `server/services/kb_retriever.py::_select_evidence`；`tests/test_rag_demo_e2e.py::TestNoEvidenceMeansCannotVerify` |
| 会话所有权 / 跨会话拒绝 | `server/auth.py::require_session_auth`；`tests/test_report_auth.py`、`tests/test_auth_endpoints.py` |
| 无 Key 运行 / 模型失败降级 | `server/routes/chat.py`、`server/graph/nodes/llm_node.py`；`tests/test_chat_llm_path.py` |
| 合成数据与真实录取边界 | `scripts/seed_demo_data.py`、`knowledge/synthetic_demo/manifest.json`；`tests/test_public_demo_acceptance.py` |

## 代码归属与治理边界（如实说明）

本仓库基于上游开源工程（见 `LICENSE` 与 `THIRD_PARTY_NOTICES.md`）演化而来，**不是**从零个人作品。
可独立指出的后续治理工作集中在：会话/报告/元数据接口的鉴权与存储边界、SSE 流式解析的
无损化与失败态处理、RAG 语料完整性与离线 Provider 默认值、启动期配置 fail-fast，以及
相应的回归测试。演示时应区分「继承的既有架构」与「本轮独立改动」，两者都可在 git 历史与
测试中核对。

## 使用边界

- 不需要 LLM Key 即可检查健康状态、合成数据 API 与知识库检索；配置模型是可选操作。
- `ENABLE_RAG_KB=true`（默认，使用随仓合成语料）、`ENABLE_OUTBOUND_FETCH=false`、
  `ENABLE_SEARCH=false` 为默认值；知识检索在语料缺失/损坏时 fail-closed（返回
  `RAG_ERROR`，不编造答案）。
- 未经授权不得分发真实招生数据库、第三方知识语料或历史私人会话。
- 本工程没有生产级并发、可用性或真实 RAG 质量验证；`knowledge/synthetic_demo/`
  只是原创合成演示语料。

返回 [README](README.md) 查看整体架构、安全设计与技术限制。
