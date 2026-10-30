# 海博特｜全栈开发工程师能力补齐矩阵（gaobao-advisor）

> 审计日期：2026-10-30
> 审计对象：`https://github.com/Xander-Xai/gaobao-advisor` @ `master`
> 基线提交：`65bdb406db3b2cb26dae0398c3dec83349ef5eaa`
> 审计方式：只读源码 + 本机实际运行命令；不把 README/CI 声明当作生产验证。

## 0. 基线事实

| 项目 | 实际结果 | 证据 |
|---|---|---|
| 当前分支 / HEAD | `master` / `65bdb40`，工作区 clean | `git status`、`git log -1` |
| Python 测试 | **1010 passed, 1 skipped**（39.13s） | `.venv/bin/python -m pytest tests -q --no-header --no-cov` |
| 前端测试 | **12 files / 70 tests passed** | `cd frontend && npx vitest run` |
| 前端生产构建 | 通过（Vite 8，dist 正常产出） | `npm run build` |
| Lint / 格式 | `ruff check .`、`ruff format --check .` 通过 | 本机命令 |
| Docker | 本机 Docker/Compose 可用；本次审计未重新 build 镜像 | `docker info`、`docker compose version` |
| 现有 PR | #31 open（docs/portfolio），#30/#29/#28/#27/#26 已合并 | `gh pr list --state all` |

> 注意：README 写「vitest 11 files / 64 tests」，实际为 **12 files / 70 tests**；README 写「1010 passed / 1 skipped」与本次一致。文档数字与实测的轻微漂移本身属于交付风险，Phase 1 一并修正。

## 1. JD 能力逐条矩阵（原仓审计结论）

状态定义：
- `ALREADY_VERIFIED`：源码与本机测试/运行已验证。
- `PARTIAL`：有相关实现，但覆盖不完整或缺少验收链路。
- `GAP`：原仓没有，需要新增。
- `NOT_APPLICABLE`：不适合在本项目重复实现（有独立项目/业务不匹配）。
- `NOT_VERIFIED`：无法从仓库或本机运行确认。

| # | JD 能力 | 原仓能力 | 状态 | 源码/证据 | 缺口与风险 |
|---|---|---|---|---|---|
| 1a | Vue 3 / 组件化 | Chat/Profile/Report/Admin 四个视图、Pinia、Vue Router、Tailwind | ALREADY_VERIFIED | `frontend/src/views/*.vue`、`frontend/src/stores/*`、`frontend/src/router/index.js`、vitest 70 tests | 无 |
| 1b | TypeScript | 全部前端为 `.js`/`<script setup>`（无 `lang="ts"`），无 `tsconfig.json`、无 `vue-tsc` | **GAP** | `frontend/package.json`（无 typescript/vue-tsc）；`frontend/src/views/AdminView.vue:64` | 无法证明 TS 工程能力；需渐进式引入，不能重写聊天模块 |
| 1c | 管理后台 / 运营后台 | `/admin` 仅展示 `/api/v1/health` 三个指标 + 模块列表，无数据表格、筛选、任务、审核 | **GAP** | `frontend/src/views/AdminView.vue:1-86` | 不构成运营后台；需真实数据与写操作 |
| 1d | 数据可视化 | 无图表库；Admin 只有状态卡片 | **GAP** | `AdminView.vue`；`package.json` 无 chart 依赖 | 用轻量 CSS 柱状/占比图即可，避免引入重型依赖 |
| 2a | Python/FastAPI | FastAPI 应用、8 个 router、SSE、Pydantic | ALREADY_VERIFIED | `server/main.py:58-104`、`server/routes/*`、`tests/test_routes.py` | 无 |
| 2b | MySQL | 仅 `_ALLOWED_SCHEMES=("sqlite",)`；`.env.example` 的 MySQL 示例会被 `db/database.py` 静默拒绝 | **GAP** | `db/database.py:17-35`、`.env.example:20-23` | 需可选 MySQL、方言适配、迁移、集成测试 |
| 2c | Redis | 仅 `server/services/rag_cache.py` 作为 RAG 缓存；`redis` 在 requirements 中但未用于任务队列 | PARTIAL | `server/services/rag_cache.py:45-102`、`tests/test_rag_cache.py` | 无后台任务、无 worker、无队列故障语义 |
| 2d | 消息队列 / 异步任务 | 无 Celery/RQ/Arq/自研队列；无 worker 进程 | **GAP** | 全局 grep 无队列实现；`docker-compose.yml` 仅 api/frontend/nginx | 需一个具体异步任务 + 幂等 + 重试 + 故障状态 |
| 2e | 微服务边界 | 单体 FastAPI + LangGraph；无独立 worker | PARTIAL | `Dockerfile`、`docker-compose.yml` | 不强行拆 LangGraph；证明 API/Worker 独立运行与故障隔离即可 |
| 3a | AI 应用 / RAG / Agent | LangGraph 17 节点、BM25+可选 Dense、引用、fail-closed | ALREADY_VERIFIED | `server/graph/graph.py`、`server/services/rag.py`、`tests/test_rag_demo_e2e.py` | 无（本轮不重做） |
| 3b | OCR / 文本抽取 / 隐私脱敏 | 无 OCR；无通用脱敏模块；仅导入脚本/Excel 类数据处理 | **GAP** | 全局无 OCR/脱敏实现；`scripts/import_*.py` 不是脱敏 | 高考项目不伪造 OCR/医疗；补一个可验证的脱敏工具与测试，OCR 标记 NOT_APPLICABLE 于本项目 |
| 4a | REST API | 现有 REST + SSE；但 data 路由返回裸 `__dict__`、无统一错误码、无详情接口、无排序/offset 分页 | PARTIAL | `server/routes/data.py:13-56`、`server/routes/data.py:59-208` | 新增 admin 路由需 Pydantic schema、错误码、状态码、限流 |
| 4b | 数据库设计 | 14 表、索引、唯一约束、SQLAlchemy 2.0；但有 `init_db()->create_all`，无迁移版本 | PARTIAL | `db/models.py`、`db/database.py:84-105` | 需新业务表 + Alembic/迁移版本；不得用 drop_all |
| 4c | Prompt / 模型集成 | LLM router、OpenAI 兼容、无 Key 降级 | ALREADY_VERIFIED | `server/services/llm_router.py`、`server/routes/chat.py`、`tests/test_chat_llm_path.py` | 无 |
| 4d | 私有化部署 | Docker/Compose/Nginx、无 Key 启动、合成数据 | PARTIAL | `Dockerfile`、`docker-entrypoint.sh`、`docker-compose.yml`、CI container job | 无可选 MySQL/Redis/Worker 编排；启动顺序未用 readiness |
| 5a | AI Coding 辅助开发 | 仓库有开发计划/审计文档，但没有「需求→AI 改码→失败测试→修复→Review→CI」的可验证记录 | PARTIAL | `docs/superpowers/plans/*`、`docs/audit/*` | 需真实开发证据，不得编造提效数字 |
| 5b | 单元测试 | 1010 pytest + 70 vitest；覆盖 80%+ | ALREADY_VERIFIED | `tests/`、`frontend/src/**/__tests__`、CI test/frontend job | 新增模块需同等覆盖 |
| 5c | Bug 排查 / Code Review | 历史 PR 有修复记录；无本轮新增证据 | PARTIAL | `git log`、PR #26/#27/#28 | Phase 1-3 需留下实际失败/修复记录 |
| 6a | 技术文档 | README/SPEC/TUTORIAL/ADR 齐全 | ALREADY_VERIFIED | `README.md`、`SPEC.md`、`docs/superpowers/adr/*` | 需补运营后台/双数据库/队列/面试讲解 |
| 6b | 性能优化 | 有 cursor pagination、WAL、joinedload；但无本轮实测基准 | PARTIAL | `db/pagination.py`、`docs/superpowers/adr/ADR-003-sqlite-wal-joinedload.md` | Phase 3 需可复现测量，不能只写结论 |
| 6c | 兼容性 / 规范化交付 | CI 有 lint/test/secret/security/frontend/container/redistribution | ALREADY_VERIFIED | `.github/workflows/ci.yml:16-181` | 需加入 typecheck、MySQL/Redis 集成、admin smoke |
| 7 | 医疗文本 / GCP / 临床方案 | 无医疗业务、无 GCP、无临床方案 | NOT_APPLICABLE | 全局无医疗模块 | 不在高考项目伪造医疗经历；用独立项目展示 |

## 2. 强制审计问题 A-H 的结论

### A. `AdminView.vue` 是否只是健康检查面板？
**是。** 组件只调用 `healthAPI.check()`，渲染 `health.status/database/version` 和静态模块列表；没有列表查询、筛选、任务、审核、审计或任何写操作。证据：`frontend/src/views/AdminView.vue:64-86`。

### B. 前端是否尚未配置 TypeScript / vue-tsc？
**是。** `frontend/package.json` 无 `typescript`、`vue-tsc`、`tsconfig.json`；所有源文件为 JS/无 lang ts。新增模块必须使用 `<script setup lang="ts">`，聊天模块保持现状。

### C. MySQL 是否只存在配置示例，实际仅支持 SQLite？
**是，且配置示例是误导性的。** `db/database.py:18` 只允许 `sqlite`，`.env.example` 的 `mysql+pymysql://...` 会被清空并回退到默认 SQLite；`create_engine` 无条件传 `check_same_thread=False`，WAL PRAGMA 也无条件执行，直接切 MySQL 会报错。

### D. 后端是否已有可复用查询/分页/ORM/事务代码？
**部分有。**
- 可复用：`db/pagination.py` 的 `paginate_cursor/paginate_offset`；`db/crud.py` 的 `get_admission_scores` 多条件查询；`db/models.py` 的索引与关系；`server/deps.py::get_db`。
- 不足：现有 `data.py` 在路由里直接 `SessionLocal()` 和拼查询，没有服务层；`paginate_cursor` 的过滤只支持等值；`PageResult.to_dict()` 直接暴露 `__dict__`；无统一事务边界与回滚测试。

### E. Redis / MQ / 后台任务是否已有实现？
- Redis：只有 `RagCache`，且 `redis` 包不在当前 `.venv` 中（运行输出 `redis package not installed — RAG cache disabled`），默认路径不依赖 Redis。
- MQ/后台任务：**无**。没有 worker 进程、没有任务表、没有重试/幂等。不能复用 RAG 缓存当作任务队列。

### F. 管理接口是否有真正的身份鉴权和角色授权？
**没有。** 原仓只有匿名会话能力令牌：`server/auth.py:88-129` 的 HMAC token 只证明「请求者拥有某个 session_id」，不含账号、角色、过期时间；`/admin` 前端路由无守卫，后端也没有任何 admin 路由。因此本轮必须新增**独立的管理员令牌与角色校验**，不能把 session token 当管理员令牌。

### G. 前后端是否存在数据结构不一致 / 错误处理缺口？
**存在，已确认：**
1. `dataAPI.searchSchools()` 同一函数可能返回 `{count,results}` 或 `{items,next_cursor,has_more}`，前端无类型约束（`frontend/src/api/client.js:185-194`）。
2. `data.py` 返回 `school.__dict__`，字段集合随 ORM 实现变化，无 schema 契约（`server/routes/data.py:51`）。
3. `_request` 对非 JSON 错误体只保留 `raw`，前端错误提示可能为空（`client.js:34-53`）。
4. `AdminView.vue` 只有 error，没有 loading skeleton/empty/retry 的完整状态机。
5. 现有测试覆盖了 SSE/鉴权，但没有 admin 的 401/403/404/409/422/幂等/回滚测试。

### H. 现有 CI 是否覆盖 Python/前端/构建/密钥/安全/Docker？
**已覆盖，缺三块：**
- 已有：ruff、pytest（3.10/3.11）、gitleaks、pip-audit、npm audit、vitest、vite build、Docker no-key smoke、redistribution gate（`.github/workflows/ci.yml`）。
- 缺：前端 `vue-tsc` 类型门禁；MySQL/Redis 集成 job；admin 登录/写接口的容器 smoke；worker 独立运行 smoke。

## 3. 真实缺口与优先级

| 优先级 | 缺口 | 验收标准 |
|---|---|---|
| P0 | 运营后台无真实业务 | 登录→院校列表（真实 API）→筛选/排序/分页→详情→创建质检任务→状态→审核→审计→统计，全链路可演示 |
| P0 | 无管理员身份/角色 | 未登录 401；角色不足 403；普通 session token 不能访问 admin；生产缺凭据 fail-closed；审计可追溯 |
| P0 | 前端无 TS 门禁 | `npm run typecheck` 通过；新增后台模块为 `lang="ts"`；聊天模块行为不变 |
| P0 | 无事务/审计写入链路 | 创建任务 + outbox + 审计同事务；异常回滚有测试 |
| P1 | MySQL 不可用 | SQLite 默认回归不变；MySQL 可选连接 + Alembic + CRUD 集成测试；WAL 仅 SQLite |
| P1 | 无异步质检 | PENDING→RUNNING→SUCCEEDED/FAILED；幂等、重试、失败可见；Redis 不可用不返回假成功 |
| P1 | 部署无 full profile | 默认 SQLite 一键启动；full profile 起 MySQL/Redis/Worker；healthcheck/readiness |
| P2 | 性能/恢复/监控/脱敏/面试材料 | 有实测基准、故障恢复记录、审计检查、脱敏示例、3/5 分钟讲解稿 |

## 4. 本轮实施边界（防止过度承诺）

- 不重做 RAG/Agent，不改 SSE 语义。
- 不引入 React、不新增 Java/Go 服务。
- MySQL 只保证**新增运营业务表 + 现有演示查询路径**可用；14 张历史表的完整生产迁移不在本轮范围，文档明确标注。
- Redis 只解决「数据质检任务」一个场景，不同时引入 Celery/Kafka/RabbitMQ。
- 医疗/GCP/临床方案标记 `NOT_APPLICABLE`，不在高考项目伪造。
- 所有性能结论必须来自本机命令输出；CI 通过不等于生产验证。

## 5. 后续证据落点

- Phase 1：`docs/interview-readiness/haibote-fullstack-demo.md`、admin 路由/服务/表、Vue TS 后台。
- Phase 2：`docs/superpowers/adr/ADR-008-mysql-redis-worker.md`、`docker-compose.full.yml`。
- Phase 3：`docs/interview-readiness/performance.md`、`docs/interview-readiness/ai-coding-evidence.md`。
