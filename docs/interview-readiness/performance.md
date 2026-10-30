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
| 真实 Redis 端到端 | `tests/test_redis_worker.py`（`REDIS_TEST_URL`） | 3 passed：入队/出队、Outbox→Worker、不可达 Redis 显式失败 |

```bash
REDIS_TEST_URL=redis://127.0.0.1:6379/0 \
  .venv/bin/python -m pytest tests/test_redis_worker.py -q
# 3 passed
```

## 6. MySQL 验证状态

- **已完成**：URL 白名单/规范化、密码脱敏、SQLite PRAGMA 隔离、MySQL 连接池参数、
  Alembic migration、MySQL dialect DDL 编译测试、MySQL API/事务集成测试代码。
- **未完成（BLOCKED）**：本机 Docker Hub 拉取 `mysql:8.4` 超时，无法启动真实 MySQL；
  因此 `tests/test_admin_mysql.py` 在本机是 **4 skipped**，不能标记 PASS。
- 复现命令（有 MySQL 时）：

```bash
MYSQL_TEST_URL='mysql+pymysql://root:testroot@127.0.0.1:3307/gaobao_test?charset=utf8mb4' \
  .venv/bin/python -m pytest tests/test_admin_mysql.py -q
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
- MySQL 无真实运行验证；
- Redis 单实例，没有集群/高可用；
- 所有数字来自本机临时 SQLite，不代表真实招生数据规模。
