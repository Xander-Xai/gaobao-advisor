# Benchmarks

Synthetic-data, dedicated-database benchmarks. They do **not** use the business
database and are not production SLA claims.

## Safety

- MySQL URL must contain `benchmark` or `test`, must not equal `DATABASE_URL`,
  and must be empty or carry `_gaobao_benchmark_ownership`.
- Redis tests use a dedicated queue key; worker benchmark uses a random
  `gaobao:bench:worker:<uuid>` key and never FLUSHDB.
- Only synthetic data is generated.

## Admin SQL/repository benchmark

```bash
MYSQL_BENCH_URL='mysql+pymysql://root:benchroot@127.0.0.1:3307/gaobao_benchmark?charset=utf8mb4' \
python -m benchmarks.mysql_admin_benchmark \
  --schools 2000 --scores-per-school 5 \
  --audit-rows 50000 --job-rows 2000 \
  --concurrency 10 --warmup 3 --repeat 10 \
  --json-out docs/performance/results/medium-admin.json
```

It measures repository/SQL latency (not HTTP), p50/p95/p99, throughput, error
rate, EXPLAIN ANALYZE plans, and an audit-index Before/After experiment.

## Worker throughput

```bash
MYSQL_BENCH_URL='mysql+pymysql://root:benchroot@127.0.0.1:3307/gaobao_benchmark?charset=utf8mb4' \
REDIS_BENCH_URL='redis://127.0.0.1:6380/0' \
python -m benchmarks.worker_throughput \
  --workers 1 2 4 --jobs 50 --schools 500 --scores-per-school 5 \
  --json-out docs/performance/results/worker-1-2-4.json
```

Each scenario resets only the guarded benchmark schema, creates synthetic
quality jobs, dispatches to Redis, starts real worker processes, and verifies
terminal DB state (not just HTTP 202).

## Results

See `docs/performance/mysql-benchmark.md` and `docs/performance/results/*.json`.
