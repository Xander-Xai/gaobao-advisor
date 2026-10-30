# AI 辅助开发证据（实际发生记录）

> 本文只记录本轮实际执行过的命令、改动和失败/修复，不编造提效百分比。
> 工具：opencode（CLI 编码代理）。人工决策：任务边界、验收标准、最终取舍。

## 0. 起点

- 仓库：`Xander-Xai/gaobao-advisor`，`master@65bdb406db3b2cb26dae0398c3dec83349ef5eaa`
- 基线实测：`pytest` 1010 passed / 1 skipped；`vitest` 12 files / 70 tests；`ruff`、`vite build` 通过。
- 2026-10-31 复核基线：`master@1622c3f`，`pytest` 1072 passed / 8 skipped；`vitest` 85 tests。
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

### Bug 6：内联降级失败后 Outbox 被错误标记为 DISPATCHED

- 现象：`QUALITY_TASK_MODE=inline` 下注入可重试异常，任务回到 PENDING，但 Outbox
  变成 DISPATCHED，任务永久卡住。
- 定位：`service.create_quality_job` 在内联执行后无条件调用
  `mark_outbox_dispatched`，没有区分“终态”和“等待重试”。
- 修复：新增 `mark_inline_execution`；仅终态标记 Outbox DISPATCHED；PENDING 保留
  Outbox 并返回 202 + warning。
- 证据：`test_inline_retry_does_not_mark_outbox_dispatched`（先失败后通过）。

### Bug 7：Compose bind mount 权限导致 API 启动失败

- 现象：full compose 中 API 重启，日志 `PermissionError: data/.session_secret`。
- 原因：宿主机 UID 1001 / 容器 appuser UID 1000，`./data:/app/data` 不可写。
- 修复：改为命名卷 `gaobao_data:/app/data`；full profile 注入 `SESSION_SECRET`。
- 证据：默认与 full compose 均实际启动，API/Frontend healthcheck 通过。

### Bug 8：演示环境 Nginx 强制 TLS 导致无限重启

- 现象：`nginx: [emerg] cannot load certificate /etc/nginx/ssl/fullchain.pem`。
- 原因：`nginx.conf` 是生产 TLS 配置，默认 compose 没有证书。
- 修复：新增 HTTP-only `nginx.demo.conf` 并仅供 Compose 演示使用；生产仍挂载
  `nginx.conf` + `./certs`。
- 证据：`GET /healthz` = 200，`GET /api/v1/health` 经 Nginx 返回 200。

### Bug 9：前端 `/admin` 深链接 404

- 现象：Vue Router 使用 history mode，但前端 Nginx 没有 SPA fallback。
- 修复：`try_files $uri $uri/ /index.html`，并为 hashed assets 增加缓存头。
- 证据：Docker 内 `GET /admin` 返回 200；Vitest 详情重试用例通过。

### Bug 10：DOMPurify critical advisory 触发前端安全门禁

- 现象：`npm audit --omit=dev` 报告 `dompurify <=3.4.16` 1 个 critical advisory。
- 修复：升级到 `dompurify@3.4.17`，同步 `package-lock.json`；不添加 ignore。
- 证据：`npm audit --omit=dev --audit-level=high` → **0 vulnerabilities**；
  `vue-tsc` + 86 tests + build 仍通过。

### Bug 11：可选 legacy admin 依赖集触发 Pillow 公告

- 现象：CI Security Audit 在 `requirements-legacy-admin.lock` 上报 Pillow 12.3.0
  的 31 个公告（旧 workflow 仅忽略 8 个）。
- 定位：Streamlit 1.66.0 固定 `pillow<13`；但 1.66.1 已放宽为 `pillow<14`。
- 修复：升级 `streamlit==1.66.1` + `pillow==13.0.0`，移除历史 ignore 列表；
  legacy 集要求 Python 3.11+，运行时集不变。
- 证据：`pip-audit -r requirements-legacy-admin.lock` → **No known vulnerabilities**；
  CI Security Audit 重新运行通过。

### Bug 12：生产 Compose 挂载 `.env.production` 但应用不读取

- 现象：`docker-compose.prod.yml` 只把 `.env.production` 挂到 `/app/.env`，代码没有
  dotenv 加载逻辑，`SESSION_SECRET` / `ADMIN_TOKEN_SECRET` 实际不可见。
- 修复：改为 required Compose `env_file`，真实注入进程；新增
  `scripts/verify_prod_compose_env.sh` 做真实启动正/负控制。
- 证据：缺 env 文件、缺 SESSION_SECRET、缺 ADMIN_TOKEN_SECRET 均 fail-closed；
  有效配置健康启动且 admin 登录成功。

### Bug 13：BRPOP 后、claim 前崩溃造成 PENDING+DISPATCHED 孤儿

- 现象：真实 Redis+MySQL 注入中，Worker 用 BRPOP 取走消息后被停止，任务停在
  PENDING、Outbox 为 DISPATCHED，RUNNING 租约恢复找不到它。
- 修复：新增 `requeue_orphaned_dispatched`，Worker 启动和每 30 秒扫描超过 60 秒的
  该状态并重新武装 Outbox；重复投递由原子 claim 吸收。
- 证据：SQLite `TestDeliveryCrashWindow` 2 条、MySQL 1 条；真实 full profile 注入后
  Worker 日志 `requeued 1 orphaned dispatched job(s)`，任务最终 SUCCEEDED。

### Bug 14：full Compose 把 MySQL/Redis 暴露到宿主机

- 现象：`3306:3306` / `6379:6379` 使数据库和队列可从宿主机直连。
- 修复：删除 host ports；API/Worker 通过 Compose 网络 `mysql:3306` / `redis:6379` 通信。
- 证据：`docker port` 对两者为空；full profile 异步任务、容器间 MySQL/Redis 连接均通过。

### 文档修正：回滚范围反向

- 原 PR 文案 `git revert de9f3d1..8ed4c2a` 是 newer..older，可能得到空范围。
- 修正为 `1622c3f..de9f3d1`，并补充 squash merge / 普通 merge / rebase merge 的验证流程；
  本轮不执行真实回滚。

### 过程阻塞：OAuth token 缺 workflow scope

- 现象：`git push` 被拒绝（OAuth App 不能更新 `.github/workflows/ci.yml`）。
- 处理：改用已授权的 SSH（`ssh.github.com:443`）推送同一提交；随后新增
  `MySQL + Redis + Admin Smoke` job，CI 全绿。没有通过删除/跳过检查来绕过。

## 4. Code Review 检查项

| 检查 | 结论 |
|---|---|
| 聊天 token 是否可当管理员 token | 否；独立 secret + `aud=gaobao-admin`，有测试 |
| 前端隐藏按钮是否被当权限 | 否；后端 `require_role` 真实返回 401/403 |
| 生产缺凭据是否放行 | 否；显式启用但缺 secret 时启动失败 |
| 创建任务与入队是否可能丢消息 | 同事务 + Outbox；BRPOP 丢消息由 `requeue_orphaned_dispatched` 补偿，原子 claim 吸收重复 |
| 重复提交 | 唯一幂等键 + 冲突 409 + 回放 200 |
| 并发审核 | `expected_version` + 条件 UPDATE；冲突 409 |
| 审计是否包含密钥 | 递归脱敏；有 `test_admin_privacy.py` |
| 队列不可用是否假成功 | 否；PENDING + warning / 503，有测试 |
| MySQL WAL 是否误执行 | 否；engine 分支隔离，有测试 |
| 前端 token 风险 | `sessionStorage` 仍受 XSS 影响；已在 ADR-007 明确取舍 |

## 5. 最终验证记录（本机）

| 命令 | 结果 |
|---|---|
| `pytest tests -q --no-header --cov-fail-under=70` | **1075 passed, 9 skipped**，覆盖率 **80.77%** |
| `REDIS_TEST_URL=... pytest tests/test_redis_worker.py` | **3 passed**（真实 Redis 7） |
| `MYSQL_TEST_URL=... pytest tests/test_admin_mysql.py` | **5 passed**（真实 MySQL 8.4） |
| `pytest tests/test_migrations.py` | **2 passed** |
| `pytest tests/test_database_modes.py` | **7 passed** |
| `cd frontend && npm test -- --run` | `vue-tsc` + **14 files / 86 tests passed** |
| `cd frontend && npm run build` | 通过 |
| `ruff check .` / `ruff format --check .` | 通过 |
| `docker compose ... --profile full up` | 全部服务 healthy；MySQL/Redis 无宿主机端口；异步任务/审核/审计/Redis 故障恢复通过 |
| 真实 BRPOP 丢消息注入（Redis+MySQL） | Worker 启动恢复孤儿；job **SUCCEEDED** |
| `PROD_API_IMAGE=gb-advisor:ci bash scripts/verify_prod_compose_env.sh` | 3 个负控制 fail-closed；有效配置启动 + admin 登录成功 |
| `make test-integration` | **8 passed**（MySQL 5 + Redis 3） |
| 默认 `docker compose up`（SQLite） | healthy；`/admin` 200；inline 质检落库并审核 |
| `npm audit --omit=dev --audit-level=high` | **0 vulnerabilities** |
| `pip-audit -r requirements.lock --no-deps --disable-pip` | **No known vulnerabilities found** |
| `pip-audit -r requirements-legacy-admin.lock` | **No known vulnerabilities found**（Pillow 13.0.0）|
| gitleaks v8.30.1（full history） | **476 commits scanned / no leaks found** |
| GitHub Actions（PR #35） | **全部通过**：Lint、Test 3.10/3.11、MySQL+Redis+Admin Smoke、Security、Secret、Frontend、Container、Redistribution |

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
