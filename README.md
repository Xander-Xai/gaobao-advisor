# gaobao-advisor — LangGraph AI 高考志愿咨询工程

[![CI](https://github.com/Xander-Xai/gaobao-advisor/actions/workflows/ci.yml/badge.svg)](https://github.com/Xander-Xai/gaobao-advisor/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11-blue)
![Demo](https://img.shields.io/badge/data-SYNTHETIC__DEMO-orange)

**一个可复现的 AI Agent 工程样本**：LangGraph 有状态工作流、FastAPI / SSE、结构化数据查询、Vue 3，以及会话安全与失败关闭设计。

**3 分钟先跑 API 演示，无需模型 Key 或真实招生数据：**

```bash
git clone https://github.com/Xander-Xai/gaobao-advisor.git
cd gaobao-advisor
docker build -t gb-advisor .
docker run --rm -p 8000:8000 gb-advisor
# 在另一个终端执行：
curl http://localhost:8000/api/v1/health
curl "http://localhost:8000/api/v1/data/schools?limit=3"
```

> Docker 默认启动 **FastAPI 后端**，不会自动打开 Vue 前端。前端开发启动见[快速开始](#快速开始)。
> 演示数据为程序生成的虚构数据，**不能用于真实高考志愿决策**；知识库检索默认启用，使用随仓库分发的原创合成语料。

**导航：** [核心能力](#这个仓库是什么不是什么) · [工程设计](#关键工程设计) · [架构](#架构) · [快速开始](#快速开始) · [演示步骤](TUTORIAL.md) · [数据与 RAG 边界](#数据分发模式) · [安全与贡献](#许可与合规)

一个基于 **LangGraph + 结构化高考数据查询 + FastAPI/SSE + Vue 3** 的 AI 志愿填报
顾问开源工程。它不是把问题直接丢给大模型的 ChatBot，而是把志愿咨询拆成
**画像采集 → 数据查询 → 知识检索（合成语料）→ 决策推理 → 来源标注 → 质量检查 →
多轮记忆** 的可观测工作流。

> **数据边界先行：** 本仓库默认只附带由程序生成的**合成演示数据**
> （`SYNTHETIC_DEMO`），不对应任何真实院校、专业或录取结果，不可用于真实
> 志愿决策。真实录取数据的导入能力保留在源码中，但需要使用者自行提供合法数据。

---

## 这个仓库是什么，不是什么

**是：** 一个把多轮对话、槽位抽取、结构化数据查询、LangGraph 编排、SSE 流式
输出和服务端会话鉴权组装在一起的工程样本。

**不是：** 一个附带真实知识库或真实招生数据的产品；也没有任何未经验证的
「企业级性能」或「RAG 质量」承诺。

| 能力 | 状态 | 说明 |
|---|---|---|
| 多轮对话与槽位抽取 | 可用 | LangGraph 状态机 + `slots/` 槽位契约 |
| 结构化数据查询（院校/专业/分数/位次/计划） | 可用 | 运行于数据源（默认合成库） |
| 冲/稳/保候选与一分一段 | 可用 | `legacy/` 适配层 + `db/` 模型 |
| 数据导入脚本 | 可用（自行提供数据） | `scripts/import_*.py`；第三方抓取默认关闭 |
| FastAPI + SSE + WebSocket 语音 | 可用 | 语音默认关闭，需自备 DashScope 凭据 |
| Vue 3 前端 | 可用 | `frontend/` |
| **运营后台（数据 / 质检 / 审计）** | **可用** | 独立管理员 RBAC、真实 API 数据、质检任务、乐观锁审核与审计；`/admin` |
| **知识库检索（RAG）** | **默认可用** | 随仓原创 SYNTHETIC_DEMO 合成语料；BM25 关键词检索为基础，无 Key 也能用；带来源引用与 fail-closed |
| 联网搜索 | 关闭 | 无第三方检索授权 |

---

## 关键工程设计

| 工程问题 | 采用的设计 | 查看实现 |
|---|---|---|
| 多轮咨询的信息不完整 | LangGraph 条件路由、槽位采集和追问分支 | [图定义](server/graph/graph.py) · [状态](server/graph/state.py) |
| LLM 与结构化业务数据如何协作 | 查询节点接入 SQLite/SQLAlchemy，后续生成与来源标注分离 | [数据 API](server/routes/data.py) · [图定义](server/graph/graph.py) |
| 可选 RAG 语料缺失/损坏时怎么办 | 默认启用随仓合成语料；语料缺失或完整性校验失败时显式 `RAG_ERROR` 并 fail-closed，检索报错而不是静默给无证据答案 | [RAG 服务](server/services/rag.py) |
| 检索结果如何可引用 | 每个检索片段带稳定 `chunk_id` 与 `source`（组名 § 小节），随 SSE `sources` 事件与知识检索接口返回 | [检索器](server/services/kb_retriever.py) · [SSE 聊天](server/routes/chat.py) |
| 匿名多轮会话如何隔离 | 服务端签发 session ID；后续请求使用 HMAC 绑定的 Bearer token | [鉴权](server/auth.py) · [SSE 聊天](server/routes/chat.py) |
| 如何验证仓库能实际运行 | 合成数据种子、无 Key Docker、Python/前端/安全 CI 门禁 | [CI](.github/workflows/ci.yml) · [验收测试](tests/test_public_demo_acceptance.py) |

**读代码顺序（面向 AI 应用工程实践）：** `server/graph/graph.py` → `server/graph/state.py` → `server/routes/chat.py` → `server/auth.py` → `server/services/rag.py`。这条路线比只看 API 列表更容易理解状态流转、异步流式输出与错误边界。

**真实性说明：** 工作流编排与 SSE 生成分开实现；当前图定义不包含独立的 `llm_reason` 节点，LLM token streaming 由 `server/routes/chat.py` 处理。配置 LLM Key 时，完整画像路径通过 SSE 流式生成；无 Key 时返回基于结构化查询结果的**确定性模板**并标记降级，而不是假装调用了模型。项目没有已验证的吞吐量、SLA 或真实录取准确率；RAG 仅有一份小规模**合成**标注集的组级命中率（`12/12`），**不构成生产级 RAG 质量评测**。

---

## 数据分发模式

默认模式开箱即用、可复现、无第三方授权风险：

1. **SYNTHETIC_DEMO（默认）** — `scripts/seed_demo_data.py` 由固定随机种子
   （`20240617`）生成，两次运行结果完全一致。院校名统一带「（合成）」，
   省份为虚构的「示例省·甲」等，`schools.special_type` 写入
   `SYNTHETIC_DEMO_DATA`。
   ```bash
   python -m scripts.seed_demo_data --db data/demo.db --reset
   ```
2. **USER_SUPPLIED_DATA** — 使用者自行准备并导入自己有权使用的数据。导入脚本见
   `scripts/import_*.py`。开启第三方抓取需显式设置 `ENABLE_OUTBOUND_FETCH=true`。
3. **VERIFIED_PUBLIC_DATA** — 有来源记录、公开使用边界已审查的数据
   （当前为 **PENDING**，未随仓库分发）。录取分数等客观事实是可公开候选，
   但需要逐项留存来源与使用条款，不能反推数据库备份、会话记录或语料可公开。

> **知识语料**同样遵循这一原则：随仓库分发的只有**原创、机器编写、带
> `SYNTHETIC_DEMO` 标记**的合成语料（见下一节）。真实招生资料/第三方语料必须走
> 单独的授权导入链路，不能直接混入默认演示。

---

## RAG 能力（默认演示可用）

本仓库自带一份**原创合成知识语料** `knowledge/synthetic_demo/`（虚构院校规则、
录取政策示例、志愿填报 FAQ 与说明性文档，CC0-1.0），因此默认演示环境中 RAG
是**启用**的，启动即自动完成语料完整性校验并初始化，**无需任何 API Key**。

检索实现复用现有 `KbRetriever`（未新建平行框架）：

* **BM25 关键词检索**是始终可用的基础路径（离线、无 Key）；
* 配置了 embedding provider（siliconflow / openai / dashscope / ollama）时叠加
  **Dense Retrieval**；无 Key 时自动使用 `keyword`，不发任何付费请求；
* 命中片段带稳定 `chunk_id` 与 `source`（`组名 § 小节标题`）；
* 无匹配证据时返回 `has_evidence:false` 且**不编造**——`build_llm_context`
  会指示模型明确说明「当前知识库无法验证」；
* 与结构化 SQL 查询职责分离：知识问题路由到检索链路，含画像的混合问题
  同时执行 `data_query` 与 `rag_retrieve`。

健康检查如实反映状态（Docker 默认启动实测输出）：

```json
{
  "status": "ok",
  "data_profile": "SYNTHETIC_DEMO",
  "optional_services": {
    "rag": {
      "state": "RAG_ENABLED",
      "reason": "",
      "corpus_configured": true,
      "documents": 8,
      "chunks": 31,
      "integrity_ok": true
    }
  },
  "degraded_services": []
}
```

**fail-closed：** 语料缺失、损坏或未带 `SYNTHETIC_DEMO` 标记时，
`rag.status()` 返回 `RAG_ERROR`、检索请求抛出 `RagCorpusError`、
`/api/v1/knowledge/search` 返回 `503`——不会静默退化成无证据的模型答案。设置
`ENABLE_RAG_KB=false` 则返回 `RAG_DISABLED`。

> **真实数据环境**：启用 RAG 前必须完成**已授权语料**的配置与完整性检查，
> 未获授权的第三方语料不得随仓库分发或用于演示。

---

## 运营后台（数据运营 / 质检 / 审计）

`/admin` 不是健康检查面板，而是一条贯穿前后端的真实运营闭环：

1. 管理员登录（独立于匿名聊天 session token）；
2. 查看合成招生数据，按关键词/省份/层次筛选、排序、分页；
3. 查看院校详情（录取分数 + 招生计划）；
4. 发起数据质检任务，按 `PENDING → RUNNING → SUCCEEDED / FAILED` 查看状态；
5. 审核质检结果（`APPROVED / REJECTED`，带乐观锁 `expected_version`）；
6. 查看统计指标与操作审计（主体、角色、资源、请求关联 ID）。

**本地启动：**

```bash
python scripts/setup_admin_env.py          # 生成 .env.admin.local（0600，已 gitignore）
set -a; . ./.env.admin.local; set +a
uvicorn server.main:app --reload
cd frontend && npm run dev                 # http://localhost:3080/admin
```

脚本会打印一次性用户名/密码；不要把 `.env.admin.local` 提交到仓库。

**鉴权边界：**

* 管理员 token 使用独立的 `ADMIN_TOKEN_SECRET` 签名，载荷包含 `sub/role/exp/aud=gaobao-admin`；
* 匿名聊天 token 无法访问 `/api/v1/admin/*`；管理员 token 也无法读取聊天 session 数据；
* 角色层级 `viewer < operator < admin`：只读 / 创建任务 / 审核 + 审计；
* 生产环境配置了管理员但缺少 `ADMIN_TOKEN_SECRET` 时**启动失败**；未配置管理员则后台拒绝所有请求（fail-closed）；禁止在 production 使用明文 `ADMIN_PASSWORD`；
* 审计详情落库前会脱敏手机号、身份证、邮箱、姓名与 token。

**质检任务模式：** `QUALITY_TASK_MODE=auto|async|inline|disabled`。`auto` 优先 Redis + Worker；开发环境 Redis 不可用时显式内联执行并标记 `execution_mode=inline_degraded`。`async` 模式下 Redis 不可用会返回 `202 + PENDING + warning`，不会伪造成功。

---

### 可选 MySQL / Redis / Worker（full profile）

默认 `docker compose up` 仍只使用 SQLite，不需要 MySQL/Redis。需要展示异步质检和双数据库时：

```bash
python scripts/setup_full_env.py          # 生成 .env.full（0600，gitignore）
docker compose --env-file .env.full \
  -f docker-compose.yml -f docker-compose.full.yml --profile full up --build
```

Compose 演示使用命名卷 `gaobao_data` 和 HTTP-only `nginx.demo.conf`；生产 TLS 仍使用
`nginx.conf` + `./certs`。直接访问 `http://localhost/admin` 可进入运营工作台。

启动内容：FastAPI（MySQL + Alembic）、MySQL 8.4、Redis 7、数据质检 Worker、Vue 前端、Nginx。
API/MySQL/Redis/Frontend 都有 healthcheck；API 使用 `/api/v1/health/ready`（DB 断开返回 503）。
MySQL 和 Redis **不发布宿主机端口**，API/Worker 通过 Compose 网络内的 `mysql:3306` /
`redis:6379` 通信；本地检查用 `docker compose exec mysql ...` / `exec redis redis-cli`。
本机已实测该 profile 全部服务 healthy，并通过“登录 → 异步质检 → SUCCEEDED → 审核 → 审计”链路；
Redis 停机时创建任务返回 `202 + PENDING + UNAVAILABLE`，恢复后 Worker 从 Outbox 补投并完成；
真实 BRPOP 丢消息故障注入后，Worker 启动补偿扫描恢复并完成任务。

```bash
# 迁移（SQLite 也可以跑，用于验证版本表）
DATABASE_URL=sqlite:///data/demo.db python -m db.migrate

# 可选集成测试（一次性启动 MySQL 8.4 + Redis 7，自动清理）
# 先安装可选 extras：pip install -e ".[dev,mysql,worker]"
make test-integration

# 也可以分别指定已有服务
REDIS_TEST_URL=redis://127.0.0.1:6379/0 pytest tests/test_redis_worker.py -q
MYSQL_TEST_URL='mysql+pymysql://root:testroot@127.0.0.1:3307/gaobao_test?charset=utf8mb4' \
  pytest tests/test_admin_mysql.py -q
```

### 生产 Compose 凭据（fail-closed）

`docker-compose.prod.yml` 不再把 `.env.production` 挂到 `/app/.env`（应用不会自动读取该文件），
而是使用 Compose `env_file` 把 `SESSION_SECRET`、`ADMIN_TOKEN_SECRET` 等真正注入进程。
`env_file` 标记为 required；文件缺失、生产环境缺 `SESSION_SECRET`、启用管理员却缺
`ADMIN_TOKEN_SECRET` 时容器启动失败，不会生成临时密钥或静默放行。

```bash
# 只使用临时测试凭据，不读取/提交真实 .env.production
PROD_API_IMAGE=gb-advisor:ci bash scripts/verify_prod_compose_env.sh
```

**迁移范围（重要）：** Alembic 初始 revision 只覆盖本轮新增的 4 张运营表
（`data_quality_jobs` / `data_quality_issues` / `operation_audit_logs` /
`quality_task_outbox`）。14 张历史表的 MySQL 生产迁移不在本轮承诺内；full profile
的演示数据由 `scripts/seed_demo_data.py --database-url ...` 引导创建。详见
[ADR-008](docs/superpowers/adr/ADR-008-mysql-redis-worker.md)。

**队列语义：** 创建任务时 DB + Outbox + 审计同事务；Redis 不可用时 `async` 模式返回
`202 + PENDING + warning`，不会伪造成功；开发环境 `auto` 才显式内联降级并标记
`execution_mode=inline_degraded`。

---

## 安全规则资产（fail-closed）

`safety_rules.md` 是原创编写的通用咨询安全约束（不编造数据、标注来源、
不提供专业意见、防提示注入、合成数据声明等）。

`SkillService` 在 `skills/gaokao/safety_rules.md` 缺失或为空时抛出
`SkillAssetUnavailableError`，**拒绝生成答案**，而不是在没有安全约束的情况下
静默作答。负控制测试见 `tests/test_skill_service.py::TestFailClosed`。

提示注入防护独立于此：`server/middleware/security.py::detect_injection` 始终生效。

---

## 会话安全

* 首次匿名会话的 `session_id` 由服务端 `secrets.token_urlsafe` 生成，
  **忽略调用方传入的 `session_id`**；
* 继续会话必须携带与该 `session_id` 匹配的 `Authorization: Bearer <token>`；
* 令牌为 `HMAC-SHA256(SESSION_SECRET, session_id)`，不匹配即
  `401 Invalid session token`；不同会话不能复用令牌。
* 报告（`/api/v1/report/*`）与反馈/金句（`/api/v1/chat/feedback`、
  `/api/v1/chat/highlight`）同样要求与该会话匹配的 Bearer 令牌；报告导出走带
  `Authorization` 头的 blob 下载流程，令牌不进入 URL。报告/会话标识还会做路径
  穿越校验，非法标识被拒绝。

> 这是**会话能力令牌**，不是账号体系：没有密码、没有用户注册、没有跨设备
> 账号恢复。生产环境必须设置强随机 `SESSION_SECRET`；`APP_ENV=production`
> 时缺失该变量会在**启动阶段**直接失败，而不是等到用户请求。

---

## 架构

```mermaid
flowchart LR
    A["security_scan"] --> B["intent_detect"] --> C["scene_route"] --> D["slot_extract"] --> E{"profile_check"}
    E -->|"信息不足"| F["question_generate"]
    E -->|"已有回复"| L["render_reply"]
    E -->|"资料完整"| G["quality_orchestrate"] --> H["data_query"] --> I["rag_retrieve（合成语料，默认启用）"] --> J["reason"] --> K["structure_output"] --> L
    F --> L
    L --> M["source_attribution"] --> N["quality_post_check"] --> O["quality_judge"] --> P["feedback"] --> Q["memory_update"] --> R(["END"])
```

> 图示对应 [`server/graph/graph.py`](server/graph/graph.py) 注册的 17 个节点；LLM Token 流由 SSE 路由独立处理，不应误解为所有节点都在一次流式调用中执行。

核心技术栈：

| 层 | 技术 |
|---|---|
| 前端 | Vue 3 + **TypeScript（新后台模块）** + Pinia + Vue Router + Tailwind CSS + Vite |
| API | FastAPI + Pydantic + SSE + WebSocket |
| Agent 编排 | LangGraph StateGraph |
| 数据库 | SQLite（默认）+ MySQL 8（可选，Alembic 迁移）+ SQLAlchemy |
| 知识检索 | BM25 关键词 + 可选 Dense Embedding 混合检索（随仓合成语料默认启用） |
| LLM | OpenAI Compatible API（DeepSeek / Qwen / GLM / Moonshot / GPT / Ollama） |
| 异步任务 | Redis List + 事务 Outbox + 独立 Worker（可选）|
| 可观测性 | Prometheus + Sentry + Analytics |
| 部署 | Docker / Docker Compose + Nginx |

---

## 快速开始

### Docker（推荐，无需任何 Key）

```bash
docker build -t gb-advisor .
docker run --rm -p 8000:8000 gb-advisor
curl http://localhost:8000/api/v1/health
# 知识库检索（默认启用，无需 Key）
curl -X POST http://localhost:8000/api/v1/knowledge/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"平行志愿的投档规则是什么"}'
```

容器首次启动会在本地生成合成数据库，**镜像内不含任何数据库文件**；知识库语料
随镜像分发（原创合成语料），健康检查返回 `optional_services.rag.state = RAG_ENABLED`。

### 本地

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 生成合成数据
python -m scripts.seed_demo_data --db data/demo.db --reset

# 让应用连接到刚生成的合成库（Docker 入口脚本已自动完成这一步）
export DATABASE_URL=sqlite:///data/demo.db

# 启动
uvicorn server.main:app --reload

# 前端
cd frontend && npm ci && npm run dev   # http://localhost:5173
```

### 测试

```bash
pytest tests -q --no-header        # Python 3.10 / 3.11
cd frontend && npx vitest run      # 前端单元测试
ruff check . && ruff format --check .
```

最近一次本地验证（本机 uv 托管环境；CI 在 Python 3.10 / 3.11 上运行同一套门禁）：

| 检查 | 结果 |
|---|---|
| `pytest tests` | **1075 passed / 9 skipped**，覆盖率 **80.77%**（门禁 70%；MySQL/Redis 集成测试默认跳过）|
| `ruff check` / `ruff format --check` | 通过 |
| Docker 无 Key 启动 `/api/v1/health` | `SYNTHETIC_DEMO` / `RAG_ENABLED`（documents=8, chunks=31, integrity_ok=true）|
| Docker 无 Key `POST /api/v1/knowledge/search`（「平行志愿的投档规则是什么」）| `has_evidence=true`，返回带 `source` 的片段 |
| 合成标注集检索命中率（`knowledge/synthetic_demo/eval_queries.json`，组级 top-k）| **12/12 = 1.000**（小规模合成集，非生产 RAG 质量指标）|
| `npm run typecheck` | 通过（`vue-tsc --noEmit`，新后台模块） |
| `vitest run`（frontend）| **14 files / 86 tests passed**；`npm run build` 通过 |
| `REDIS_TEST_URL=redis://127.0.0.1:6380/0 pytest tests/test_redis_worker.py` | 3 passed（真实 Redis 7）|
| `MYSQL_TEST_URL=... pytest tests/test_admin_mysql.py` | 5 passed（真实 MySQL 8.4）|
| `docker compose ... --profile full up` | MySQL/Redis/API/Worker/Frontend/Nginx 全部 healthy；MySQL/Redis 无宿主机端口；异步任务、审核、审计、Redis 故障恢复通过 |
| 真实 BRPOP 丢消息注入（Redis+MySQL） | job PENDING/DISPATCHED → Worker 启动日志 `requeued 1 orphaned dispatched job(s)` → **SUCCEEDED** |
| `PROD_API_IMAGE=gb-advisor:ci bash scripts/verify_prod_compose_env.sh` | 缺失 env 文件 / 缺 SESSION_SECRET / 缺 ADMIN_TOKEN_SECRET 均 fail-closed；有效配置启动并 admin 登录成功 |
| `npm audit --omit=dev --audit-level=high` | **0 vulnerabilities**（dompurify 3.4.17）|
| `pip-audit -r requirements.lock --no-deps --disable-pip` | **No known vulnerabilities found** |
| `pip-audit -r requirements-legacy-admin.lock` | **No known vulnerabilities found**（streamlit 1.66.1 / pillow 13.0.0）|
| gitleaks v8.30.1（full history） | **477 commits scanned / no leaks found** |

> 上述数字来自本机实际运行输出。Docker/Compose 项为本机真实启动、健康检查与故障注入结果；
> 生产 Compose 测试只使用临时生成且已删除的测试凭据。

CI（`.github/workflows/ci.yml`）在 push / PR 上运行同一组门禁：Lint、Test（3.10 & 3.11）、
MySQL 8.4 + Redis 7 集成测试、Admin Smoke、Secret Scan（gitleaks 全历史）、
Security Audit（pip-audit 审计运行时锁 + legacy 锁、npm audit）、Frontend Quality Gate、
No-Key Container Smoke Test、Redistribution Gate。
门禁失败即红，不通过跳过或降低阈值来「修绿」。

---

## 项目结构

```text
server/
  main.py              FastAPI 入口（挂载 8 个路由）
  auth.py              会话令牌签发与校验（HMAC-SHA256）
  routes/              health / onboarding / chat / profile / data / knowledge / voice
  report/              报告生成路由
  graph/               LangGraph 编排与 17 个节点
  services/            rag / kb_retriever / quality / llm_router ...
  middleware/          CSP、限流、注入检测、请求关联 ID
  admin/               管理员鉴权/RBAC、运营查询、质检任务、审计、Worker
db/                    SQLAlchemy 模型、会话与迁移入口（db/migrate.py）
migrations/            Alembic 版本目录
skills/gaokao/         SkillService（fail-closed）+ 原创安全规则与启发式
quality/               质量与幻觉检查
legacy/                数据查询适配层
scrapers/              数据采集器（默认不发起外部请求）
scripts/               数据导入脚本 + seed_demo_data.py + 管理员凭据生成
knowledge/synthetic_demo/  随仓原创合成知识语料（SYNTHETIC_DEMO，CC0）
frontend/              Vue 3 + Vite（Chat / Report / Profile / Admin；后台模块使用 TypeScript）
tests/                 单元与验收测试（1059 passed / 1 skipped）
```

---

## 已知限制与不适用场景

本工程是**可运行的开源工程样本**，不是可直接上线的生产系统，也不是志愿决策依据。
请明确以下边界：

* **数据**：默认只有程序生成的合成数据，**不用于真实志愿填报决策**。真实录取数据需
  由使用者自行准备、导入并确保拥有合法授权；`VERIFIED_PUBLIC_DATA` 当前仍为
  **PENDING**，未随仓库分发。
* **知识检索**：默认启用随仓**原创合成语料**（`knowledge/synthetic_demo/`），
  可在无 Key 环境下完成 BM25 检索与引用；它是演示语料，**不是真实招生知识**。
  真实语料需自行提供并完成授权与完整性检查后再启用；语料缺失/损坏时返回
  `RAG_ERROR` 并 fail-closed。检索默认走离线 `keyword`（BM25）路径；需要网络的
  Embedding Provider 必须通过 `RAG_EMBEDDING_PROVIDER` 显式开启，配置 LLM Key
  不会自动切换到付费向量服务。
* **联网能力**：第三方抓取（`ENABLE_OUTBOUND_FETCH`）与联网搜索（`ENABLE_SEARCH`）
  默认关闭。
* **身份体系**：只有「会话能力令牌」（HMAC 签名），没有账号、密码、注册、跨设备
  恢复；多 worker 部署必须显式设置 `SESSION_SECRET`。
* **语音**：WebSocket 语音链路默认关闭，需自备 DashScope 凭据。
* **生产级验证**：未做容量、并发、SLA 或真实 RAG 质量评测；可观测性组件
  （Prometheus / Sentry）需自行配置后才生效。
* **第三方数据再分发**：第三方招生数据存在授权不确定性，本仓库**不**再分发这类数据。

> 说明：以上是不适用边界，不是待办列表。历史版本中曾尝试过的人物化/营销类内容
> 已从当前源码树移除。

---

## 演示和参与

- **初次使用：** [无 Key 演示教程](TUTORIAL.md)；[合成模式演示检查项](examples/demo_conversation.md)。不提供真实院校报考推荐样例。
- **面试演示：** [TUTORIAL.md 的「面试演示脚本」](TUTORIAL.md#面试演示脚本可复现面向-rag--agent-岗位) 给出从槽位抽取到 SSE 输出、会话鉴权与证据/无证据差异的可复现命令，并注明每一点对应的源码/测试。
- **反馈问题：** [提交 Issue](https://github.com/Xander-Xai/gaobao-advisor/issues/new/choose)。请不要附加真实考生个人信息或 API Key。
- **贡献代码：** 参见 [CONTRIBUTING.md](CONTRIBUTING.md)。涉及安全问题请按 [SECURITY.md](SECURITY.md) 私下报告。
- **面试/验收材料：** [3 分钟演示与 10 个追问](docs/interview-readiness/haibote-fullstack-demo.md) · [JD 能力矩阵](docs/interview-readiness/haibote-gap-matrix.md) · [性能与恢复](docs/interview-readiness/performance.md) · [AI 开发证据](docs/interview-readiness/ai-coding-evidence.md)。
- **工程决策：** [ADR-002 LangGraph](docs/superpowers/adr/ADR-002-langgraph-flow.md)、[ADR-003 数据库](docs/superpowers/adr/ADR-003-sqlite-wal-joinedload.md)、[ADR-004 混合检索](docs/superpowers/adr/ADR-004-hybrid-rag.md)。
- **RAG 演示与健康检查：** [docs/rag-demo.md](docs/rag-demo.md)。

不提供承诺运行中的在线 Demo 服务；以仓库代码和最新 CI 为准。

---

## 许可与合规

* 代码：[`LICENSE`](LICENSE)（MIT）。
* 来源：本项目基于早期的 **MIT 许可代码**继续开发，并在此基础上独立完成了 LangGraph / FastAPI / Vue 3 / 容器化 / 会话安全 / 自动化测试等工程重构。完整来源、固定版本与后续许可证变更说明见 [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)；原始 MIT 版权声明与许可正文见 [`LICENSE`](LICENSE)。
* 数据：[`DATA_LICENSE.md`](DATA_LICENSE.md) — 合成数据集以 CC0-1.0 提供。
* 隐私：[`PRIVACY.md`](PRIVACY.md)。安全：[`SECURITY.md`](SECURITY.md)。
* 依赖：运行时依赖集必须**零已知漏洞**，由 CI 的 `pip-audit` 强制；例外登记与
  开放决策见 [`docs/dependency-exceptions.md`](docs/dependency-exceptions.md)。
* 第三方：[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)；贡献指南：[`CONTRIBUTING.md`](CONTRIBUTING.md)。

**商标与人物：** 本项目不包含、也不声称包含任何真实人物的观点、方法论、
表达风格或语录；相关私有资产已在上游工程中移除。
