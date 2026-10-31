# 海博特全栈演示与源码讲解手册

> 目标：3 分钟能演示，5 分钟能讲源码，10 个追问能各用 60 秒回答。
> 数据全部为 `SYNTHETIC_DEMO`，不用于真实志愿决策。

## 0. 环境与分支

| 项 | 值 |
|---|---|
| 仓库 | `https://github.com/Xander-Xai/gaobao-advisor` |
| 基线 | `master@65bdb40` |
| Phase 1 | 分支 `feat/haibote-phase1-admin-workbench-20261030`，PR #32 |
| Phase 2 | 分支 `feat/haibote-phase2-mysql-redis-worker-20261030`，PR #33 |
| Phase 3 | 分支 `feat/haibote-phase3-acceptance-20261030`（本手册、性能与 AI 证据） |
| 本地实测 | Python 3.11；SQLite 默认 + 真实 MySQL 8.4 + Redis 7；`pytest` 1088 passed / 17 skipped；`vitest` 86 tests |

## 1. 三分钟演示路径

### 1.1 启动（无 Key、无外部服务）

```bash
python scripts/setup_admin_env.py          # 打印一次密码，写 .env.admin.local（0600）
set -a; . ./.env.admin.local; set +a
python -m scripts.seed_demo_data --db data/demo.db --reset
uvicorn server.main:app --reload
# 另一个终端
cd frontend && npm run dev                 # http://localhost:3080/admin
```

### 1.2 演示动作（按顺序）

1. 打开 `/admin`，用脚本打印的 `operator` 登录 → 顶部显示角色、统计卡片。
2. “招生数据”页：关键词/省份/层次筛选，切换排序与分页 → 数据来自
   `GET /api/v1/admin/schools`，不是 Mock。
3. 点“详情” → 看录取分数与招生计划（`/schools/{id}`）。
4. 切“质检任务” → 选择省份 → “创建质检任务” → 当前无 Redis 时显式内联执行，
   页面显示 `SUCCEEDED` 与问题清单；若 Redis 异步模式则显示 `PENDING/RUNNING` 并轮询。
5. 用 `admin` 账号登录（或把 `.env.admin.local` 的角色改为 admin）→ 打开任务详情 →
   填写审核备注 → “审核通过” → 审计页出现 `quality_job.reviewed`。
6. 数据库验证：

```bash
sqlite3 data/demo.db "select id,status,review_status,issue_count from data_quality_jobs;"
sqlite3 data/demo.db "select actor,action,resource_id from operation_audit_logs order by id desc limit 5;"
```

7. 讲一句边界：这是会话能力令牌之外的独立管理员 RBAC；生产缺
   `ADMIN_TOKEN_SECRET` 会启动失败；Redis 不可用不会返回假成功。

## 2. 五分钟源码讲解路径

| 顺序 | 文件 | 讲什么 |
|---|---|---|
| 1 | `server/main.py` | 8+1 路由挂载、lifespan 中 `ensure_secret_ready` / `ensure_admin_ready` / MySQL 迁移、错误信封、RequestID 中间件 |
| 2 | `server/admin/auth.py` | 独立 token 域（`aud=gaobao-admin`）、PBKDF2、角色层级、生产 fail-closed、聊天 token 不可互换 |
| 3 | `server/admin/routes.py` | 依赖注入执行 RBAC、Pydantic 入参、登录/任务限流、HTTP 状态码（201/202/200/409/503） |
| 4 | `server/admin/service.py` | 业务编排：模式选择、Outbox 投递、内联降级、真实状态，不把逻辑塞进路由 |
| 5 | `server/admin/repository.py` | 查询/分页/事务/审计；`create_job_with_outbox` 同事务；`claim_job` 原子抢占；`review_job` 乐观锁 |
| 6 | `db/models.py` | 4 张新表、索引、唯一约束、状态字段、外键 |
| 7 | `server/admin/queue.py` + `worker.py` | Redis List、Outbox 重试、幂等 claim、失败/重试/租约恢复 |
| 8 | `db/database.py` + `db/migrate.py` + `migrations/` | SQLite/MySQL 方言隔离、URL 白名单、Alembic 版本化 |
| 9 | `frontend/src/stores/admin.ts` + `api/admin.ts` + `types/admin.ts` | 类型化 DTO、`{data,error}` 错误映射、状态机、轮询 |
| 10 | `frontend/src/views/AdminView.vue` + `components/admin/*` | 登录/数据/质检/审计四块、Loading/Empty/Error/Retry、可访问性 |
| 11 | `tests/test_admin_*.py` / `frontend/**/__tests__/admin*` | 401/403/404/409/422、幂等、回滚、Worker、漂移测试 |

## 3. 十个可能追问（每个 60 秒口述）

### Q1. 为什么不直接复用聊天 session token 做管理员鉴权？

聊天 token 是 `HMAC(SESSION_SECRET, session_id)`，只证明“你拥有这个匿名会话”，
没有账号、角色、过期时间。复用会造成权限提升。我们新增 `ADMIN_TOKEN_SECRET`，
token 载荷带 `aud=gaobao-admin/sub/role/iat/exp/jti`，签名输入不同，二者不可互换；
`ADMIN_USERS_JSON` 从环境注入，密码 PBKDF2。测试见
`tests/test_admin_auth.py::test_chat_session_token_is_not_an_admin_token`。
代码：`server/admin/auth.py`。

### Q2. RBAC 和 fail-closed 具体怎么落地？

角色层级 `viewer < operator < admin`：读接口 viewer+，创建任务 operator+，审核/审计
admin。FastAPI 依赖 `require_role(minimum)` 在后端执行，前端隐藏按钮只是 UX。
未配置管理员时后台返回 503；生产显式启用但缺 `ADMIN_TOKEN_SECRET` 或使用明文
`ADMIN_PASSWORD` 时启动失败。测试：`test_production_requires_separate_token_secret`、
`test_operator_cannot_review`、`test_viewer_cannot_create_quality_job`。

### Q3. 创建任务和入队如何保证一致性？

先把 `data_quality_jobs`、`quality_task_outbox`、`operation_audit_logs` 放在同一事务
提交，提交后再投递 Redis；投递失败不会丢任务，Outbox 保持 PENDING 并退避重试。
Worker 也会周期性 dispatch Outbox。这样避免“队列成功、数据库失败”的孤儿任务。
代码：`server/admin/repository.py::create_job_with_outbox`、
`server/admin/service.py::_publish_with_session`、`server/admin/queue.py::dispatch_outbox`。
测试：`TestOutboxDispatch`、`test_unexpected_error_rolls_back_and_returns_envelope`。

### Q4. 重复提交和并发审核怎么处理？

创建任务要求 `Idempotency-Key`，数据库唯一约束；同 key 同过滤条件回放 200，不同过滤
条件返回 409 `IDEMPOTENCY_CONFLICT`。审核用 `expected_version` 做乐观锁，条件
`UPDATE ... WHERE version=? AND status='SUCCEEDED' AND review_status='PENDING_REVIEW'`，
rowcount=0 返回 409，避免后写覆盖先写。测试：
`test_same_idempotency_key_replays_same_job`、`test_stale_version_conflicts`。
代码：`repository.py::review_job`。

### Q5. Redis 不可用时会不会假成功？

不会。`QUALITY_TASK_MODE=async` 且无 Redis 时返回 `202 + PENDING + warning`，
任务真实状态是 PENDING，不返回 SUCCEEDED；`auto` 模式在开发环境显式内联执行并标记
`execution_mode=inline_degraded`；`disabled` 返回 503。测试：
`test_async_mode_without_redis_does_not_fake_success`、
`test_queue_failure_keeps_job_pending`。代码：`server/admin/service.py`。

### Q6. Worker 的重试、幂等和崩溃恢复怎么做？

Worker 用 `UPDATE ... WHERE status='PENDING' AND attempts < max_attempts` 原子 claim，
重复消息因状态守卫被跳过；可重试错误回到 PENDING 并重新武装 Outbox，最多 3 次；
永久错误立即 FAILED。Worker 启动和运行期每 30 秒有界扫描 RUNNING 与孤儿
PENDING/DISPATCHED；未耗尽→PENDING，耗尽→FAILED + `WORKER_LEASE_EXPIRED`。
`claim_job` 返回 attempts 作为 fencing token，`complete_job`/`fail_job` 用
`WHERE status=RUNNING AND attempts=?` CAS，旧 Worker 只能得到 `EXECUTION_FENCED`。
BRPOP 在 claim 前取走消息的窗口由
`requeue_orphaned_dispatched` 补偿：把超过 60 秒的 PENDING+DISPATCHED 视为投递租约过期，
重新武装 Outbox；Worker 启动和运行期每 30 秒扫描。重复投递由原子 claim 吸收。
测试：`TestWorker`、`TestDeliveryCrashWindow`、MySQL 崩溃窗口用例；真实 Redis+MySQL
注入见 `performance.md`。代码：`server/admin/worker.py`、`repository.claim_job`。

### Q7. MySQL 支持和 SQLite 怎么隔离？迁移范围是什么？

`DATABASE_URL` 白名单只允许 sqlite/mysql/mysql+pymysql，非法 scheme 直接失败；
`mysql://` 规范化为 PyMySQL。WAL PRAGMA、`check_same_thread`、文件权限只对 SQLite
执行；MySQL 用 `pool_pre_ping/pool_recycle/utf8mb4/connect_timeout`。迁移用 Alembic，
`python -m db.migrate`：`20261030_0001` 创建 4 张运营表，`20261031_0002`
创建 14 张历史业务表；已有 `create_all` 数据库先 `adopt-existing`（校验 schema 后
stamp）再 upgrade。`0002` downgrade 明确拒绝，回滚依赖备份/恢复。Schema Matrix 见
`docs/database-schema-matrix.md`。代码：`db/database.py`、`db/migrate.py`、
`db/schema_contract.py`、`migrations/`；测试：`test_database_modes.py`、
`test_migrations.py`、`test_mysql_migrations.py`。真实 MySQL 8.4 上全量迁移/seed/
adopt 数据保留均通过，full profile 的 MySQL+Redis+Worker 已实际启动并完成异步任务。full profile 的 MySQL/Redis 不发布
宿主机端口，容器间通过 `mysql:3306` / `redis:6379` 通信。生产 `docker-compose.prod.yml`
使用 required `env_file` 注入 `.env.production`；应用不会自动读 `/app/.env`，缺
`SESSION_SECRET` / `ADMIN_TOKEN_SECRET` 会 fail-closed。验证脚本：
`scripts/verify_prod_compose_env.sh`。

### Q8. TypeScript 是渐进式还是重写？

渐进式。没有重写聊天/SSE/报告模块；新增 `tsconfig.json`、`env.d.ts` 和
`vue-tsc --noEmit`，只把后台模块改成 `<script setup lang="ts">`，DTO 放在
`types/admin.ts`，API 错误映射在 `api/admin.ts`。`npm test` 先跑 typecheck，现有 CI
无需改 workflow 即可获得类型门禁。测试：`npm test -- --run`，14 files / 86 tests。

### Q9. 审计和隐私怎么保证不泄漏凭据？

审计只写主体、角色、动作、资源、request_id、结果和脱敏后的 detail；写入前递归处理
姓名、手机号、身份证、邮箱、token、`sk-` key；请求头 `X-Request-ID` 与审计关联。
密码/密钥不进入审计；错误消息也做 URL 密码脱敏。测试：`test_admin_privacy.py`、
`test_unexpected_error_rolls_back_and_returns_envelope`。代码：
`server/admin/privacy.py`、`repository.record_audit`。

### Q10. 测试和 CI 覆盖到什么程度？哪些没做到？

Python 1088 passed / 17 skipped（覆盖率 80.82%），覆盖 401/403/404/409/422、幂等、
回滚、乐观锁、Worker 重试/租约、BRPOP 丢消息补偿、Alembic、MySQL DDL/URL、真实
MySQL 8.4 与 Redis 7；前端 86 tests 覆盖登录、筛选、空/错/重试、权限、创建、审核、审计。
full compose 已实际启动并验证异步任务、Redis 故障恢复与真实 BRPOP 丢消息恢复；生产
Compose 凭据正/负控制通过。CI 已新增 MySQL 8.4 + Redis 7 service job 和 admin smoke；
真实集成测试也可用 `make test-integration` 一键复现（MySQL 8 + Redis 3 + 双 Worker/恢复 5 = 16 passed）。
未做到：14 张历史表的 MySQL 生产迁移、生产容量/SLA、CI 中启动完整 Compose（本机已实测）。
CI 现有 lint/test/secret/security/frontend/container 门禁仍保留。

## 4. 设计取舍（ADR）

- `ADR-007`：独立管理员 token 而非复用 session；Bearer 而非 Cookie；进程内限流的
  代价；审计脱敏。
- `ADR-008`：SQLite 默认 + MySQL opt-in；Alembic 只覆盖新表；Redis List + Outbox；
  Worker 失败语义；full compose 边界。

## 5. 未实现边界（必须能说出口）

1. MySQL 全量 18 表已由 Alembic 覆盖；`0002` 不支持破坏性 downgrade，回滚必须使用
   经验证的备份/恢复。
2. MySQL/Redis 真实集成测试已同时在本机和 GitHub Actions service containers 运行通过；
   完整 Compose 只在本地实测，未放进 CI（构建成本高）。
3. full compose 已实际启动并验证；默认 compose 也已验证 SQLite + inline 质检 + `/admin`。
4. 新增了演示用 HTTP Nginx 配置；生产 TLS 仍使用 `nginx.conf` + 证书挂载。
5. full profile 的 MySQL/Redis 不发布宿主机端口；生产 Compose 的 `.env.production`
   必须存在且包含 `SESSION_SECRET`，启用管理员时还需 `ADMIN_TOKEN_SECRET`。
6. BRPOP 丢消息用补偿扫描恢复，不是 Redis 消费组/ACK；语义为 at-least-once，
   恢复延迟受 60 秒投递租约和 30 秒扫描周期影响，重复投递由原子 claim + fencing 吸收。
7. 登录/任务限流是进程内滑窗，多 worker 生产需 Redis。
8. 前端 token 存在 `sessionStorage`，仍受 XSS 影响；未引入 CSP 之外的更强隔离。
9. 没有 OCR、GCP、临床方案、医疗文本经验；这些标记 `NOT_APPLICABLE`，不在高考项目伪造。
10. 没有生产容量、并发、SLA、真实 RAG 质量结论。

### 5.1 回滚流程（只读验证，不在本任务执行）

PR #35 的基线是 `1622c3f`。Git 范围必须写成 **older..newer**；反向范围
（如 `de9f3d1..8ed4c2a`）会得到空集合或错误提交。使用 `HEAD` 可避免分支后续
文档提交导致范围过期。

```bash
# 1) 先验证范围，不修改工作区
git log --oneline 1622c3f..HEAD
git diff --stat 1622c3f..HEAD

# 2) 普通线性分支：按 older..newer 生成反向提交（不要执行未评审的回滚）
git revert --no-commit 1622c3f..HEAD
# 评审、运行 pytest / frontend / compose 检查后再提交

# 3) squash merge 后：对 squash commit 做单提交回滚
git revert <squash_commit_sha>

# 4) 普通 merge 后：保留主线父提交
git revert -m 1 <merge_commit_sha>

# 5) rebase merge 后：对实际落地提交逐个回滚
git log --oneline <base>..<head>
git revert --no-commit <base>..<head>
```

验证回滚范围是否包含预期提交：

```bash
git show --stat <revert_commit>
git log --oneline --graph -10
```

边界：以上命令仅作为文档与演练步骤；本轮不执行真实回滚，不重写历史，不强制推送。

## 6. 最终 JD 验收表

| JD 能力 | 原仓能力 | 新增实现 | 代码证据 | 测试证据 | 验收状态 |
|---|---|---|---|---|---|
| Vue 3 / 组件化 | 四视图 + Pinia + Router | 运营后台四块组件 | `frontend/src/components/admin/*` | `AdminView.spec.ts` | **PASS** |
| TypeScript | 无 | `tsconfig` + `vue-tsc` + 类型化后台 | `frontend/tsconfig.json`、`types/admin.ts`、`api/admin.ts` | `npm test`（含 typecheck） | **PASS** |
| 管理/运营后台 | 仅健康检查 | 数据筛选/分页/详情/任务/审核/审计/统计 | `AdminView.vue`、`server/admin/routes.py` | pytest + vitest | **PASS** |
| 数据可视化 | 无 | 任务状态/问题严重度 CSS 柱状图 | `AdminStatsCards.vue` | AdminView.spec | **PASS** |
| Python/FastAPI | 已有 | 分层 admin API + 错误码 + RequestID | `server/admin/*`、`server/main.py` | `test_admin_*.py` | **PASS** |
| MySQL | 仅 SQLite | 可选 MySQL + Alembic + 方言隔离 | `db/database.py`、`db/migrate.py`、`migrations/` | `test_database_modes.py`、`test_migrations.py`、真实 MySQL 5 passed | **PASS**（仅新增运营表范围） |
| Redis / 消息队列 | 仅 RAG 缓存 | Redis List + Outbox + Worker | `server/admin/queue.py`、`worker.py` | 真实 Redis 3 passed + 单元测试 | **PASS** |
| 异步任务 | 无 | PENDING→RUNNING→SUCCEEDED/FAILED、重试、周期租约、Fencing、BRPOP 补偿 | `worker.py`、`repository.py` | `TestWorker`、`TestFencingAndLeaseRecovery`、双 Worker MySQL+Redis 集成 | **PASS** |
| 微服务边界 | 单体 | API/Worker 独立进程、故障隔离 | `docker-compose.full.yml` | full profile 实启 + Redis 故障恢复 | **PASS** |
| 鉴权与 RBAC | 无 admin | 独立 token、角色、fail-closed | `server/admin/auth.py` | `test_admin_auth.py` | **PASS** |
| 事务/审计 | 无 | 同事务 Outbox + 审计 + 回滚 | `create_job_with_outbox`、`record_audit` | 回滚/审计测试 | **PASS** |
| 隐私脱敏 | 无 | 姓名/手机/证件/邮箱/token 脱敏 | `server/admin/privacy.py` | `test_admin_privacy.py` | **PASS** |
| 测试/CI | 已有 1010 pytest | 新增 pytest、86 vitest、typecheck、MySQL/Redis service job、admin smoke | `tests/`、`frontend/**/__tests__`、`.github/workflows/ci.yml` | 全量运行 + CI 全绿 | **PASS** |
| 性能优化 | cursor 分页 | 质检 N+1 批量化 7.1× + 索引验证 | `quality.py`、`benchmark_admin_queries.py` | `performance.md` | **PASS**（本机测量） |
| AI Coding 证据 | 无 | 需求→失败→修复→Review→验证记录 | `ai-coding-evidence.md` | 文档内命令 | **PASS** |
| OCR / 医疗 GCP | 无 | 不在本项目伪造 | — | — | **NOT_APPLICABLE** |
| 生产 SLA/容量 | 未做 | 明确不声称 | `performance.md` | — | **NOT_RUN** |

## 7. 一句话总结

这条演示的价值不是“页面很多”，而是：**一个写操作如何穿过 Vue 类型层、FastAPI
鉴权、业务服务、ORM 事务、Outbox、Redis/Worker、乐观锁审核和审计，并且在 Redis/
MySQL/凭据缺失时都不撒谎。**
