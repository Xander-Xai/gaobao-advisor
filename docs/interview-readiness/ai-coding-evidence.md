# AI 辅助开发证据（实际发生记录）

> 本文只记录本轮实际执行过的命令、改动和失败/修复，不编造提效百分比。
> 工具：opencode（CLI 编码代理）。人工决策：任务边界、验收标准、最终取舍。

## 0. 起点

- 仓库：`Xander-Xai/gaobao-advisor`，`master@65bdb406db3b2cb26dae0398c3dec83349ef5eaa`
- 基线实测：`pytest` 1010 passed / 1 skipped；`vitest` 12 files / 70 tests；`ruff`、`vite build` 通过。
- 审计结论：`AdminView.vue` 只是健康检查；前端无 TS；`DATABASE_URL` 仅允许 SQLite；
  Redis 只做 RAG 缓存；无 admin RBAC；无任务/审计表。

## 1. 需求 → 验收标准

原始需求摘要：

1. `/admin` 必须是真实运营后台，数据来自 FastAPI；
2. 渐进式 TypeScript + `vue-tsc`；
3. 管理员独立鉴权 + RBAC，不能用聊天 session token；
4. 一条创建→查询→状态→审核→审计→回滚的链路；
5. MySQL/Redis/Worker 可选，不破坏 SQLite 默认；
6. 测试、CI、文档、面试讲解。

可执行验收：

```bash
.venv/bin/python -m pytest tests -q --no-header
cd frontend && npm test -- --run && npm run build
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

## 2. AI 代理实际执行的任务

| 阶段 | AI 执行 | 人工/AI 共同决策 |
|---|---|---|
| 审计 | 读取关键文件、运行基线、生成 gap matrix | 明确「不重做 RAG/Agent」「不伪造医疗经验」 |
| Phase 1 | 生成 `server/admin/*`、DB 模型、Vue TS 后台、pytest/vitest | 选择独立 admin token + PBKDF2 + 乐观锁 + Outbox |
| Phase 2 | MySQL URL/引擎适配、Alembic、Redis Worker、full compose | 只迁移新增 4 表，明确历史表范围 |
| Phase 3 | 基准脚本、N+1 优化、性能/面试/AI 证据文档 | 性能结论只采用实测数字 |

实际新增/修改文件（节选，完整见 PR diff）：

- 后端：`server/admin/{auth,schemas,repository,service,quality,queue,worker,errors,privacy}.py`、
  `db/models.py`、`db/database.py`、`db/migrate.py`、`migrations/versions/20261030_0001_admin_ops.py`
- 前端：`frontend/src/{types/admin.ts,api/admin.ts,stores/admin.ts}`、
  `frontend/src/components/admin/*.vue`、`frontend/src/views/AdminView.vue`、`tsconfig.json`
- 测试：`tests/test_admin_*.py`、`tests/test_database_modes.py`、`tests/test_migrations.py`、
  `tests/test_redis_worker.py`、`frontend/src/**/__tests__/admin*`
- 交付：`docs/interview-readiness/*`、`docs/superpowers/adr/ADR-00{7,8}*`

## 3. 实际发现的 Bug 与修复

### Bug 1：测试 fixture 导入错误

- 现象：`ImportError: cannot import name '_job_limiter' from 'server.admin.limits'`
- 原因：限流器实例定义在 `routes.py`，fixture 从 `limits.py` 导入。
- 修复：`tests/conftest.py` 改为从 `server.admin.routes` 导入。
- 证据：修复后 admin 测试 44 passed（当时）。

### Bug 2：前端“创建任务”点击不触发请求

- 现象：Vitest 中点击 `create-job` 后 `fetch` 调用数为 0。
- 定位：按钮是 `type="submit"`，jsdom 点击未触发表单 submit 默认行为。
- 修复：按钮改为 `type="button"` + `@click="submitJob"`，显式调用业务函数。
- 证据：`AdminView.spec.ts` 从 2 failed 变为 10 passed。

### Bug 3：`.env.full` 中 PBKDF2 哈希被 Docker Compose 当变量

- 现象：`docker compose config` 警告 `The "c1b4e717..." variable is not set`。
- 原因：`ADMIN_USERS_JSON` 值包含 `$600000$...`，Compose 对未加引号的 env 值做插值。
- 修复：生成脚本用单引号包裹 JSON；重新生成后 config 通过。
- 证据：`docker compose --env-file .env.full ... config` exit 0。

### Bug 4：full overlay 仍强制要求 `.env`

- 现象：`env file .../.env not found`。
- 原因：base compose 的 `env_file: .env` 仍生效。
- 修复：使用 Compose 长语法 `required: false`；full overlay 用 `.env.full`。
- 证据：不创建 `.env` 也能 `compose config` 成功。

### Bug 5：质检扫描 N+1

- 现象：基准 500 校扫描 median **416.791 ms**。
- 原因：每校 2 条查询。
- 修复：按 100 个 school_id 分块批量预取，保留上限与去重。
- 结果：median **58.352 ms**，约 7.1×；新增 `tests/test_admin_quality_batching.py` 防回归。
- 证据：`docs/interview-readiness/performance.md`。

### 未解决/环境阻塞

- MySQL 真实运行测试：Docker Hub 拉取 `mysql:8.4` 超时 → `tests/test_admin_mysql.py` 4 skipped。
  未标记 PASS；提供了 DDL 编译测试和可复现命令。
- GitHub workflow 修改：当前 `gh` token 缺 `workflow` scope，推送 `.github/workflows/*`
  被拒绝。通过把 `vue-tsc` 加入 `npm test` 脚本绕过，现有 CI 仍执行类型检查。

## 4. Code Review 检查项

| 检查 | 结论 |
|---|---|
| 聊天 token 是否可当管理员 token | 否；独立 secret + `aud=gaobao-admin`，有测试 |
| 前端隐藏按钮是否被当权限 | 否；后端 `require_role` 真实返回 401/403 |
| 生产缺凭据是否放行 | 否；显式启用但缺 secret 时启动失败 |
| 创建任务与入队是否可能丢消息 | 否；DB + Outbox + 审计同事务，投递失败保留 PENDING |
| 重复提交 | 唯一幂等键 + 冲突 409 + 回放 200 |
| 并发审核 | `expected_version` + 条件 UPDATE；冲突 409 |
| 审计是否包含密钥 | 递归脱敏；有 `test_admin_privacy.py` |
| 队列不可用是否假成功 | 否；PENDING + warning / 503，有测试 |
| MySQL WAL 是否误执行 | 否；engine 分支隔离，有测试 |
| 前端 token 风险 | `sessionStorage` 仍受 XSS 影响；已在 ADR-007 明确取舍 |

## 5. 最终验证记录（本机）

| 命令 | 结果 |
|---|---|
| `pytest tests -q --no-header` | **1072 passed, 8 skipped**，覆盖率 **80.78%** |
| `REDIS_TEST_URL=... pytest tests/test_redis_worker.py` | **3 passed**（真实 Redis） |
| `pytest tests/test_migrations.py` | **2 passed** |
| `pytest tests/test_database_modes.py` | **7 passed** |
| `cd frontend && npm test -- --run` | `vue-tsc` + **14 files / 85 tests passed** |
| `cd frontend && npm run build` | 通过 |
| `ruff check .` / `ruff format --check .` | 通过 |
| `docker compose ... config` | 通过（`--env-file .env.full`） |
| `docker build` | 本机拉取依赖超时，未完成；CI container job 会执行 |
| MySQL 运行测试 | **BLOCKED**（镜像拉取超时） |

## 6. 可现场讲解的案例

**需求**：后台点击“创建质检任务”必须真实落库、异步执行、可审核、可审计，且 Redis
不可用时不能假装成功。

**过程**：

1. 先写测试：无 Redis 时期望 202 + PENDING + warning；
2. 实现 Outbox + 队列 + Worker；
3. 测试发现点击没有发请求（Bug 2），修复按钮语义；
4. 基准发现 N+1（Bug 5），批量预取后 7.1×；
5. Code Review 补乐观锁冲突、审计脱敏、生产 fail-closed；
6. 最终 `pytest`/`vitest`/`typecheck`/`ruff` 全绿，Redis 真实集成通过。

这条链路可以在面试中按「需求 → 失败测试 → 定位 → 修复 → Review → CI」逐层展开。
