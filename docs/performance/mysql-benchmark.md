# MySQL 8.4 / Worker Benchmark

> Environment: WSL2, MySQL 8.4.13, Redis 7.4.9, Python 3.11.15, Intel i5-14600KF,
> 20 logical CPUs, ~16 GB RAM. Synthetic data only. Repository/SQL latency; no
> HTTP layer. These are **not** production SLA numbers.

Raw results: `docs/performance/results/*.json` (commit SHA, environment, plans,
p50/p95/p99, throughput, errors).

## 1. Dataset and method

| Level | Schools | Scores | Audit rows | Jobs | Warmup/Repeat |
|---|---:|---:|---:|---:|---|
| Small | 500 | 2,500 | 5,000 | 500 | 2/5 |
| Medium | 2,000 | 10,000 | 50,000 | 2,000 | 3/10 |
| Large | 10,000 | 50,000 | 20,000 | 1,000 | 1/3 |

- Dedicated `gaobao_benchmark` database with ownership marker; never `DATABASE_URL`.
- Fixed synthetic generator (seed in `scripts/seed_demo_data.py`/benchmark builder).
- Warmup followed by repeated samples; p50/p95/p99 from actual samples.
- MySQL DATETIME is second precision; worker wait/execution timestamps are coarse.

## 2. Medium admin workloads (2,000 schools / 10k scores / 50k audits)

| Workload | p50 ms | p95 ms | p99 ms | Throughput/s |
|---|---:|---:|---:|---:|
| Schools page 1 | 4.517 | 5.496 | 5.496 | 215.9 |
| Schools deep page | 4.813 | 9.160 | 9.160 | 183.5 |
| Province filter | 6.439 | 11.062 | 11.062 | 141.8 |
| Province + level + ranking sort | 6.353 | 8.686 | 8.686 | 146.9 |
| School detail | 8.549 | 13.253 | 13.253 | 109.2 |
| Stats aggregation | 22.593 | 32.221 | 32.221 | 41.5 |
| Quality scan (one province) | 102.481 | 135.000 | 135.000 | 8.9 |
| Jobs page 1 | 6.300 | 7.923 | 7.923 | 151.6 |
| Audit page 1 | 8.111 | 12.251 | 12.251 | 112.9 |
| Audit deep page (OFFSET 19,980) | 64.980 | 74.416 | 74.416 | 14.9 |

## 3. Concurrency (2,000 schools / 20k audits)

| Concurrency | p50 ms | p95 ms | p99 ms | Wall throughput/s | Errors |
|---:|---:|---:|---:|---:|---:|
| 1 | 5.790 | 6.965 | 18.606 | 120.7 | 0 |
| 5 | 8.259 | 22.974 | 24.272 | 305.9 | 0 |
| 10 | 19.277 | 70.476 | 84.138 | 243.8 | 0 |
| 20 | 26.351 | 261.167 | 290.012 | 285.1 | 0 |
| 50 | 30.996 | 560.252 | 703.573 | 286.6 | 0 |

Throughput plateaus around ~285 calls/s while p95 rises sharply at 20–50
concurrent clients. The benchmark engine uses SQLAlchemy default pool
(5 + 10 overflow); pool checkout is the likely bottleneck. No errors occurred.

## 4. Large dataset (10,000 schools / 50k scores)

| Workload | p50 ms | p95 ms | p99 ms |
|---|---:|---:|---:|
| Schools page 1 | 5.173 | 5.596 | 5.596 |
| Schools deep page | 8.688 | 8.860 | 8.860 |
| Province filter | 5.255 | 5.503 | 5.503 |
| Province + level + ranking sort | 12.893 | 14.394 | 14.394 |
| School detail | 17.070 | 20.916 | 20.916 |
| Stats | 24.676 | 29.493 | 29.493 |
| Quality scan (one province) | 103.386 | 103.548 | 103.548 |

The school query paths scale reasonably; quality scan is dominated by synthetic
row volume and remains ~100 ms for a province.

## 5. Before / After: audit `created_at` index

Optimization: migration `20261031_0004` adds `ix_audit_created` on
`operation_audit_logs.created_at`. The same data/DB was measured with the index
dropped, then created.

| Medium (50k audits) | Before p50/p95 | After p50/p95 |
|---|---:|---:|
| Audit page 1 | 37.204 / 56.292 ms | **8.139 / 13.336 ms** |
| Audit deep page (OFFSET 19,980) | 65.324 / 124.298 ms | **54.736 / 59.143 ms** |

Resource sample during a medium admin run: MySQL **36.76% CPU / 447.6 MiB**
(container limit ~15.5 GiB); the benchmark client ran on the same host, so this
is an indicative sample, not isolated capacity planning data.

Before plan: table scan + filesort over ~49,791 rows.
After plan: reverse index scan on `ix_audit_created`, no filesort.

Data-driven negative result: a matching `data_quality_jobs.created_at` index was
tested but MySQL 8.4 did not use it for the jobs query shape; it was **not
adopted**. On the large 20k-audit dataset the optimizer also chose a table scan
with the audit index, so the benefit is data-size/plan dependent, not universal.

## 6. Worker throughput (real processes)

Dataset: 500 schools / 5 scores per school; 50 jobs per scenario.

| Workers | Run 1 Jobs/s | Run 1 e2e p95 | Run 2 Jobs/s | Run 2 e2e p95 | Errors |
|---:|---:|---:|---:|---:|---:|
| 1 | 3.191 | 16 s | 2.842 | 18 s | 0 |
| 2 | 2.798 | 21 s | 4.284 | 15 s | 0 |
| 4 | 7.522 | 8 s | 8.912 | 6 s | 0 |

Second run is more representative; 2-worker variance is real and should not be
hidden. 4 workers scale to ~8.9 jobs/s with no errors/retries.

Resource sample (4 workers, 100 jobs, 1,000 schools): MySQL 41.75% CPU /
897 MiB, Redis 0.71% CPU / 3.5 MiB, DB threads 2–3; 5.15 jobs/s, e2e p95 20 s.
The larger per-job scan and MySQL work dominate; queue is not the only limit.

## 7. Conclusions and limits

- Audit page-1 latency improved ~4× p95 on the 50k-row medium dataset with a
  reversible index; deep offset still grows with OFFSET.
- The jobs index experiment was negative and was not added.
- Concurrency above ~10–20 hits pool/queueing limits; tune pool size and
  benchmark HTTP/API separately before production sizing.
- Worker throughput scales with processes but is bounded by scan/MySQL work.
- No HTTP latency was measured here; no production SLA, capacity, or real-data
  quality claim is made.
