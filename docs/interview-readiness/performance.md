# 运营后台性能与故障恢复记录

> 日期：2026-10-30
> 环境：本机 Python 3.11.15 / SQLite（WAL）/ `scripts/benchmark_admin_queries.py`
> 结论只代表本机可复现测量，不是生产 SLA。

## 1. 基准数据

脚本在临时目录生成（不提交数据库文件）：

| 表 | 行数 |
|---|---:|
| schools | 2,000 |
| admission_scores | 10,000 |
| enrollment_plans | 2,000 |

```bash
.venv/bin/python scripts/benchmark_admin_queries.py --schools 2000 --repeat 15
```

## 2. 查询延迟（毫秒）

| 查询 | median | p95 |
|---|---:|---:|
| 院校列表第 1 页（20 条） | 9.879 | 10.274 |
| 院校列表深页（OFFSET 1980） | 9.962 | 10.135 |
| 按省份筛选 + 名称排序 | 10.630 | 11.862 |
| 院校详情（分数 + 计划） | 3.428 | 5.307 |
| 统计聚合 | 2.402 | 2.742 |
| 质检扫描（1 个省份，约 500 校） | **58.352** | 83.228 |

> 深页在这个数据量下与首页接近，因为 2,000 行仍小；大表应优先使用已有的
> cursor pagination（`db/pagination.py`），后台当前使用 offset 是为了页码 UI 语义。

## 3. 索引验证（EXPLAIN QUERY PLAN）

| 查询 | 实际计划 |
|---|---|
| `admission_scores` 按 school/province/year/subject | `SEARCH admission_scores USING INDEX ix_adm_lookup (...)` |
| `schools` 按 province | `SEARCH schools USING INDEX ix_schools_province (province=?)` |
| `data_quality_jobs` 按 status + created_at | `SEARCH data_quality_jobs USING INDEX ix_dq_jobs_status_created (status=?)` |

说明现有复合索引被真实查询使用，而不是只存在于模型定义里。

## 4. 一次实际优化：质检扫描 N+1 → 批量预取

**问题：** `server/admin/quality.py` 最初对每所院校分别查询分数和招生计划；
500 所院校 ≈ 1,000 次查询。基准中位数为 **416.791 ms**（p95 426.635）。

**修改：** 按 100 个 school_id 分块批量查询，再按 school_id 分组；保留每校
`MAX_ROWS_PER_SCHOOL=2000` 的上限和问题去重。

**结果：** 同一数据/同一脚本，中位数 **58.352 ms**（p95 83.228），约 **7.1×**。
`tests/test_admin_quality_batching.py` 通过 SQLAlchemy 事件统计语句数，防止回退成 N+1。

## 5. 故障恢复验证

| 场景 | 测试 | 结果 |
|---|---|---|
| Redis 不可用，async 模式 | `tests/test_admin_quality_jobs.py::TestQueueSemantics::test_async_mode_without_redis_does_not_fake_success` | 202 + PENDING + warning，不返回成功 |
| Redis 投递失败 | `test_queue_failure_keeps_job_pending`、`TestOutboxDispatch::test_dispatch_failure_keeps_outbox_pending` | Outbox 保持 PENDING，attempts+1 |
| Worker 重复消费 | `TestWorker::test_worker_success_and_duplicate_claim` | 第二次 claim 跳过，问题数不翻倍 |
| Worker 瞬时失败 | `TestWorker::test_transient_failures_retry_then_fail` | PENDING→PENDING→FAILED（3 次上限） |
| Worker 永久失败 | `TestWorker::test_permanent_failure_marks_failed` | 立即 FAILED，错误码可见 |
| Worker 崩溃后租约过期 | `TestWorker::test_stale_running_job_is_requeued` | RUNNING→PENDING + `WORKER_LEASE_EXPIRED` |
| BRPOP 后、claim 前崩溃 | `TestDeliveryCrashWindow::test_orphaned_pending_dispatched_job_is_rearmed` | PENDING+DISPATCHED → Outbox 重新 PENDING，attempts+1 |
| 崩溃窗口恢复后重投 | `TestDeliveryCrashWindow::test_recovered_job_is_redelivered_and_processed` | 补偿后 Worker 处理成功，不重复产生问题 |
| 真实 Redis+MySQL 丢消息 | full profile：`redis-cli BRPOP` 取走消息、停 Worker、回拨 `updated_at`、重启 Worker | 日志 `requeued 1 orphaned dispatched job(s)`；job **SUCCEEDED** |
| 周期租约恢复 | `test_worker_loop_runs_periodic_recovery_before_consuming`、`test_recover_worker_state_runs_both_bounded_scans` | 运行期先恢复再消费；两类扫描均执行 |
| 重试耗尽 | `test_lease_exhaustion_marks_failed`（max=1/3）、MySQL `test_mysql_lease_exhaustion_marks_failed` | 未耗尽 PENDING；耗尽 FAILED + `WORKER_LEASE_EXPIRED` |
| 旧 Worker 延迟提交 | `test_claim_returns_fencing_attempt_and_stale_complete_is_rejected`、`test_stale_failure_cannot_overwrite_new_execution` | `EXECUTION_FENCED`；成功审计/问题不重复 |
| 双 Worker 争抢 | `test_two_workers_race_for_one_redis_message` | 一个 SUCCEEDED、一个 IDLE；started/succeeded 审计各 1 |
| 并发恢复 | `test_two_workers_recover_one_stale_lease` | 两个恢复者结果 `[0,1]`；只产生一次 retry 审计 |
| 重复投递 | `test_duplicate_delivery_does_not_duplicate_issues` | 问题数不翻倍；succeeded 审计 1 次 |
| MySQL 短暂不可用 | full profile 停 MySQL：`/health/ready` 503、创建任务 500；恢复后 202 → SUCCEEDED | 无假成功 |
| 真实 Redis 端到端 | `tests/test_redis_worker.py`（`REDIS_TEST_URL`） | 3 passed：入队/出队、Outbox→Worker、不可达 Redis 显式失败 |

```bash
REDIS_TEST_URL=redis://127.0.0.1:6379/0 \
  .venv/bin/python -m pytest tests/test_redis_worker.py -q
# 3 passed
```

## 6. MySQL 与 full compose 实测

- **已完成并从 BLOCKED 转为 PASS**：本机拉取 `mysql:8.4` 成功，启动真实 MySQL 8.4
  后运行 `tests/test_admin_mysql.py`：**5 passed**（列表/详情、质检+审核事务、崩溃窗口补偿、
  异常回滚、dialect 断言）。
- **迁移 + seed 实测**：fresh MySQL 上 `python -m db.migrate upgrade` 创建 4 张运营表
  和 `alembic_version`；`seed_demo_data --database-url` 引导 14 张历史表演示表，
  共 8 校 / 128 分数 / 48 计划。
- **full compose 实测**：MySQL 8.4 + Redis 7 + API + Worker + Frontend + Nginx
  全部 healthy；MySQL/Redis 无宿主机端口，容器间通过服务名通信；异步质检
  `PENDING → RUNNING → SUCCEEDED`，审核写审计。
- **双 Worker 实进程**：同一 worker 容器内启动两个 `python -m server.admin.worker`，
  并发处理 3 个任务；`issues=15=SUM(issue_count)`，每个 job 的 succeeded 审计恰好 1 次。
- **MySQL 短暂不可用**：停止 MySQL 后 `/health/ready` 返回 503，创建任务返回 500；
  恢复后任务 202 → SUCCEEDED。Worker 健康检查同时依赖 MySQL 与 Redis。
- **故障注入**：停止 Redis 后创建任务返回 `202 + PENDING + queue_state=UNAVAILABLE`；
  恢复 Redis 后 Worker 从 Outbox 自动补投并完成，未出现假成功或丢任务。
- **真实 BRPOP 丢消息**：停 Worker → 创建任务 → `redis-cli BRPOP` 取走消息并丢弃 →
  回拨 DB `updated_at` → 启动 Worker；启动日志出现
  `requeued 1 orphaned dispatched job(s)`，任务最终 **SUCCEEDED**。
- **生产 Compose 凭据**：`scripts/verify_prod_compose_env.sh` 用临时 env 文件验证：
  缺失 env 文件、缺 `SESSION_SECRET`、启用管理员缺 `ADMIN_TOKEN_SECRET` 均 fail-closed；
  有效配置启动并完成 admin 登录。
- 复现命令：

```bash
MYSQL_TEST_URL='mysql+pymysql://root:testroot@127.0.0.1:3307/gaobao_test?charset=utf8mb4' \
  .venv/bin/python -m pytest tests/test_admin_mysql.py -q

PROD_API_IMAGE=gb-advisor:ci bash scripts/verify_prod_compose_env.sh

python scripts/setup_full_env.py
docker compose --env-file .env.full \
  -f docker-compose.yml -f docker-compose.full.yml --profile full up --build
```

## 7. 监控与审计

- Prometheus 新增 `admin_quality_jobs_total{status,execution_mode}`、
  `admin_quality_queue_unavailable_total`；
- HTTP 指标已有 `http_requests_total` / `http_request_duration_seconds`；
- 审计记录可通过 admin API 查询，`request_id` 与响应头 `X-Request-ID` 关联；
- 审计详情落库前递归脱敏（`server/admin/privacy.py`）。

## 8. 未声称的能力

- 没有生产容量/并发/SLA 测试；
- 没有慢查询日志采集或 APM 链路追踪；
- MySQL 只验证了新增运营表 + 演示查询路径，14 张历史表无生产级迁移；
- Redis 单实例，没有集群/高可用；BRPOP 丢消息靠补偿扫描，不是 Redis 消费组确认；
- at-least-once 语义允许重复投递；恢复延迟受 60 秒投递租约和 30 秒扫描周期影响；
- 所有数字来自本机临时 SQLite，不代表真实招生数据规模。
