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
- **迁移范围**：本轮 Alembic 初始 revision 只覆盖新增的 4 张运营表。14 张历史表的
  MySQL 生产迁移不在本轮承诺内；演示 full profile 由 seed 脚本 `create_all` 引导。
  这一点在 README/本 ADR 明确标注，避免声称「全量 MySQL 兼容」。

### 2. 异步任务：Redis List + 事务 Outbox

- 只有一个队列 `gaobao:quality:jobs`，只承载 job id；数据库是状态唯一真源。
- 创建任务时，`data_quality_jobs` + `quality_task_outbox` + 审计在**同一事务**提交；
  提交后再尝试投递，失败不丢任务。
- Worker 用原子 `UPDATE ... WHERE status='PENDING'` 抢占，`attempts` 递增；重复消息
  因状态守卫被跳过（幂等）。
- 失败策略：可重试错误回到 `PENDING` 并重新武装 Outbox，最多 `max_attempts`
  （默认 3）；永久/耗尽失败进入 `FAILED`，错误码/错误信息可见。
- Worker 崩溃留下的 `RUNNING` 超过租约会被 `requeue_stale_running` 回收。
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
  可选 seed → uvicorn。
- 凭据由 `.env.full`（`scripts/setup_full_env.py` 生成，0600，gitignore）注入，不提交。

## 备选方案

| 方案 | 未采用原因 |
|---|---|
| 直接 `create_all` 代替迁移 | 无法版本化、无法安全演进；生产不可审计 |
| 先入队后写库 | 队列成功而 DB 失败会产生孤儿任务 |
| 多队列/多 broker | 本轮只有一个业务任务，过度设计 |
| Redis 不可用就同步等待并返回 SUCCEEDED | 违反「不伪造成功」 |
| 立即迁移 14 张历史表 | 成本高、无真实数据验证；先保证新增表双库工作并明确范围 |

## 后果

- 正面：默认演示零依赖；MySQL/Redis 可按需启用；任务状态、审计、失败语义可测试。
- 负面：MySQL 全量历史表迁移未完成；Worker 租约/重试是应用层实现，不是企业级调度；
  Outbox 由 Worker 轮询而不是 CDC。
- 边界：不承诺生产 SLA、不承诺 MySQL 所有历史查询路径完全等价；实际运行证据见
  `docs/interview-readiness/performance.md` 与最终报告。
