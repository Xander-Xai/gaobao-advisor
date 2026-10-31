# ADR-008: MySQL 可选化 + Redis Worker 的边界

- 状态：Accepted
- 日期：2026-10-30
- 关联：Phase 2 / `db/database.py`、`db/migrate.py`、`migrations/`、`server/admin/queue.py`、`server/admin/worker.py`、`docker-compose.full.yml`

## 背景

原项目默认 SQLite + WAL，满足零依赖演示，但 JD 要求 MySQL、Redis、消息队列和异步任务。
同时必须保证默认路径不依赖外部服务、旧表旧数据不被破坏、不能把同步等待伪装成异步。

## 决策

### 1. 数据库：SQLite 默认，MySQL 显式 opt-in

- `DATABASE_URL` 只允许 `sqlite`、`mysql`、`mysql+pymysql`；`mysql://` 自动规范化为
  `mysql+pymysql://`，其他 scheme 直接 `ValueError`，不再静默回退 SQLite。
- SQLite 专属的 `check_same_thread`、`PRAGMA journal_mode=WAL`、文件权限只作用于
  SQLite engine；MySQL 使用 `pool_pre_ping`、`pool_recycle`、`utf8mb4`、
  `connect_timeout`。
- 日志使用 `redact_database_url()`，密码不进入日志。
- SQLite 仍用 `Base.metadata.create_all`（兼容原行为）；MySQL 用户通过
  `python -m db.migrate` / `alembic upgrade head` 管理 schema。
- `DB_AUTO_CREATE=true` 仅用于自包含 demo 容器；生产不建议。
- **迁移范围（2026-10-31 更新）**：`20261030_0001` 创建 4 张运营表，
  `20261031_0002` 创建 14 张历史业务表，`20261031_0003` 创建管理员 Token 撤销表；
  Alembic 现在覆盖全部 19 张表。
- **已有 schema 策略**：legacy `create_all` 数据库必须显式运行
  `python -m db.migrate adopt-existing`；该命令先通过 `db/schema_contract.py` 对比
  列/PK/索引/唯一约束/FK，全部匹配后才 `stamp 20261030_0001`，随后 `upgrade` 验证并
  跳过已有表。不直接 `stamp head`。
- **迁移失败与回滚**：MySQL DDL 非事务；`0002` 先预检所有已有表，再按 FK 顺序创建缺失表，
  中途失败可安全重跑。`0002` 的 downgrade 被明确拒绝，回滚走备份/恢复，避免删除已有数据。
- **seed 边界**：MySQL 容器 seed 使用 `--no-create-schema`，证明迁移后不需要 `create_all`
  补建表；SQLite 默认 demo 仍保留 `create_all` 引导。

### 2. 异步任务：Redis List + 事务 Outbox + 执行 Fencing

- 只有一个队列 `gaobao:quality:jobs`，只承载 job id；数据库是状态唯一真源。
- 创建任务时，`data_quality_jobs` + `quality_task_outbox` + 审计在**同一事务**提交；
  提交后再尝试投递，失败不丢任务。
- Worker 用原子 `UPDATE ... WHERE status='PENDING'` 抢占，`attempts` 递增；重复消息
  因状态守卫被跳过（幂等）。
- **执行所有权（fencing）**：`claim_job()` 返回本次执行的 `attempts` 值，作为
  fencing token；`complete_job()` / `fail_job()` 使用
  `WHERE status='RUNNING' AND attempts=?` 的条件更新。租约过期后旧 Worker 即使恢复，
  也无法覆盖新执行的完成/失败状态、重复写问题或审计。
- 失败策略：可重试错误回到 `PENDING` 并重新武装 Outbox，最多 `max_attempts`
  （默认 3）；永久/耗尽失败进入 `FAILED`，错误码/错误信息可见。
- **周期租约恢复**：Worker 启动时和运行期每 30 秒执行一次有界扫描（默认 limit=50）；
  同时处理过期 `RUNNING` 和孤儿 `PENDING+DISPATCHED`，不依赖 Worker 重启。
  - 未耗尽次数：`RUNNING → PENDING`，重新武装 Outbox；
  - 已耗尽次数：`RUNNING → FAILED`，写入 `WORKER_LEASE_EXPIRED` 和失败审计；
  - 行级条件更新保证多 Worker 并发恢复只有一个成功。
  - 恢复耗时/数量写入 `admin_worker_recovery_runs_total`、
    `admin_worker_recovery_jobs_total`、`admin_worker_recovery_duration_seconds`，
    并记录 `worker.recovery` / `worker.recovery.failed` 结构化日志。
- **BRPOP 丢消息窗口**：`BRPOP` 在 DB claim 前就把消息从 Redis 移除。若 Worker 恰在此窗口崩溃，
  任务会停在 `PENDING` 而 Outbox 已是 `DISPATCHED`。`requeue_orphaned_dispatched`
  将超过 60 秒的该状态视为投递租约过期，重新把 Outbox 置为 `PENDING`；Worker 启动时和
  运行期每 30 秒扫描一次。重复投递由原子 `claim_job` 吸收，因此语义从 at-most-once
  提升为至少一次（at-least-once）。投递/恢复语义不是 exactly-once：重复投递允许发生，
  由 fencing + 原子 claim + 唯一问题约束吸收；恢复延迟受
  `WORKER_DELIVERY_LEASE_SECONDS`（默认 60 秒）和扫描周期影响。
- 队列不可用时：
  - `async`：返回 `202 + PENDING + warning`，绝不返回成功；
  - `auto`：开发环境显式内联执行并标记 `execution_mode=inline_degraded`；
  - `disabled`：503。
- 不引入 Celery/Kafka/RabbitMQ，避免多套基础设施。

### 3. 部署：默认 SQLite，full profile 可选

- `docker compose up` 保持 SQLite/frontend/nginx。
- `docker compose --env-file .env.full -f docker-compose.yml -f docker-compose.full.yml --profile full up`
  额外启动 MySQL 8.4、Redis 7、Worker。
- API 健康检查使用 `/api/v1/health/ready`（DB 断开返回 503），不是 liveness。
- Compose `depends_on: condition: service_healthy` 只负责启动顺序；应用启动后仍通过
  readiness/healthcheck 判断真实可用性。
- MySQL 启动顺序：healthcheck healthy → API entrypoint 执行 Alembic（重试 30 次）→
  可选 seed → uvicorn；Worker 等 API healthy 后才启动，避免两个进程并发 seed。
- API 数据目录使用命名卷 `gaobao_data`，避免宿主机 UID 与容器 appuser UID 不一致导致
  `.session_secret` 写入失败；full profile 同时注入独立 `SESSION_SECRET`。
- 默认/演示 Compose 使用 HTTP-only `nginx.demo.conf`；生产 `nginx.conf` 继续负责 TLS，
  由 `docker-compose.prod.yml` 挂载 `./certs`。
- 凭据由 `.env.full`（`scripts/setup_full_env.py` 生成，0600，gitignore）注入，不提交。
- full profile 的 MySQL/Redis **不发布宿主机端口**；API/Worker 只通过 Compose 网络访问
  `mysql:3306` / `redis:6379`，避免把数据库/队列暴露到宿主机。
- 生产 `docker-compose.prod.yml` 使用 required `env_file` 注入 `.env.production`，因为应用
  不会自动读取 `/app/.env`；缺失文件、缺 `SESSION_SECRET`、启用管理员却缺
  `ADMIN_TOKEN_SECRET` 时 fail-closed。验证脚本：`scripts/verify_prod_compose_env.sh`。
- Worker 健康检查同时验证 MySQL `SELECT 1` 与 Redis `PING`，数据库不可用时不会显示 healthy。
- MySQL `DATETIME` 秒级精度会把刚创建的 Outbox `next_attempt_at` 向上取整；调度查询使用
  1 秒容差，避免“已接收但被误报 UNAVAILABLE”。

## 备选方案

| 方案 | 未采用原因 |
|---|---|
| 直接 `create_all` 代替迁移 | 无法版本化、无法安全演进；生产不可审计 |
| 先入队后写库 | 队列成功而 DB 失败会产生孤儿任务 |
| 多队列/多 broker | 本轮只有一个业务任务，过度设计 |
| Redis 不可用就同步等待并返回 SUCCEEDED | 违反「不伪造成功」 |
| 直接 `stamp head` 而不对比 schema | 可能把缺列/缺索引的数据库标记为已完成；改用显式 `adopt-existing` + schema contract |

## 后果

- 正面：默认演示零依赖；MySQL/Redis 可按需启用；任务状态、审计、失败语义可测试。
- 负面：Worker 租约/重试是应用层实现，不是企业级调度；Outbox 由 Worker 轮询而不是 CDC；
  BRPOP 丢消息靠补偿扫描而非 Redis 消费组确认；0002 不支持破坏性 downgrade。
- 边界：不承诺生产 SLA、不承诺 MySQL 所有历史查询路径完全等价；实际运行证据见
  `docs/interview-readiness/performance.md` 与最终报告。
- 2026-10-31 可靠性复核：真实 MySQL 8.4 + Redis 7 上验证双 Worker 争抢、并发恢复、
  重复投递、BRPOP 丢消息、Fencing 旧结果、重试耗尽、MySQL 短暂不可用；
  `tests/test_worker_integration.py` 5 passed，SQLite 单测覆盖周期恢复/耗尽/失败。
- 2026-10-31 迁移复核：真实 MySQL 8.4 上验证空库 upgrade、重复 upgrade、seed
  `--no-create-schema`、已有 create_all schema 数据保留、索引 drift 拒绝；SQLite 默认
  回归保持通过。剩余边界：完整 Compose 未进 CI、at-least-once 非 exactly-once、
  分布式限流/Token 撤销未实现。

- 2026-10-31 基准复核：真实 MySQL 8.4 / Redis 7 上完成管理查询与 1/2/4 Worker
  吞吐测试；审计 `created_at` 索引第一页 p95 56.292→13.336 ms，4 Worker
  ~8.9 jobs/s。详见 `docs/performance/mysql-benchmark.md`。这是本机合成数据，
  不是生产 SLA；Issue #40 的 Streams/ACK 对比仍未完成。
