# Redis Queue Recovery Comparison (Issue #40)

> Environment: WSL2, MySQL 8.4.13, Redis 7.4.9, Python 3.11.15,
> Intel i5-14600KF / 20 logical CPUs / ~16 GB RAM. Synthetic data only.
> Raw results: `docs/performance/results/queue-recovery-final.json`.
> Production wiring is unchanged; BLMOVE and Streams are experiment adapters.

## 1. What was compared

| Scheme | Handoff | Explicit ACK | Recovery mechanism |
|---|---|---|---|
| List + Outbox (current) | `LPUSH` / `BRPOP` | No Redis ACK; DB claim + outbox | 60s delivery lease + 30s scan; 600s running lease |
| BLMOVE processing list | atomic ready → processing | remove processing entry after DB commit | processing-list lease + recovery scan |
| Streams consumer group | `XADD` / `XREADGROUP` | `XACK` | PEL + `XAUTOCLAIM` idle threshold |

All schemes use the real MySQL `claim_job` → `collect_issues` → `complete_job`
path, the same attempts-based fencing token, the same synthetic schools/jobs,
and the same success criteria. MySQL remains the sole task-state source of
truth. No second broker is introduced.

## 2. Fault injection matrix

Real child processes were SIGKILLed at precise hooks. Counts are PASS/repeats;
`N/A` means the scheme has no such ACK window and was not counted as a pass.

| Scenario | List + Outbox | BLMOVE | Streams |
|---|---:|---:|---:|
| Published, not consumed | 5/5 | 5/5 | 5/5 |
| After consume, before DB claim | 5/5 | 5/5 | 5/5 |
| After DB claim, before execute | 5/5 | 5/5 | 5/5 |
| During execution | 5/5 | 5/5 | 5/5 |
| DB committed, before ACK | N/A | 5/5 | 5/5 |
| After ACK, worker crash | N/A | 5/5 | 5/5 |
| Duplicate delivery | 5/5 | 5/5 | 5/5 |
| Two concurrent recoverers | 5/5 | 5/5 | 5/5 |
| Redis unavailable | 5/5 | 5/5 | 5/5 |
| Redis restart (AOF) | 5/5 | 5/5 | 5/5 |
| MySQL unavailable | 5/5 | 5/5 | 5/5 |
| Max attempts exhausted | 5/5 | 5/5 | 5/5 |

Totals: **172 scenario runs**; 50 List passes + 2 N/A, 60 BLMOVE passes,
60 Streams passes. **0 failed**, **0 duplicate business executions**,
**0 lost jobs**, **0 wrong terminal states**. Duplicate delivery was injected
in every scheme (5/5 runs); each duplicate produced exactly one DB claim and
one success audit. Every successful run had `audit_succeeded=1` and a
DISPATCHED/consistent outbox state.

## 3. Recovery latency

Definition: monotonic time from the fault marker (after real process kill) to
terminal DB state **and** an empty delivery channel. Shortened experiment
configuration: 4s delivery/running lease, 1s scan. This is **not** the
production default.

| Scheme | Samples | p50 | p95 | p99 |
|---|---:|---:|---:|---:|
| List + Outbox | 50 | 2.615 s | 3.884 s | 4.301 s |
| BLMOVE | 60 | 2.338 s | 6.459 s | 6.471 s |
| Streams | 60 | 2.328 s | 6.598 s | 6.720 s |

The shortened BLMOVE/Streams medians are similar; BLMOVE has a lower p95/p99
than Streams in this run. All three are bounded by the 4s experiment lease plus
scan/worker startup, not by a production SLO.

### Production default List validation

The real `run_forever` worker was run with **60s delivery lease / 30s scan /
600s running lease**, 3 repeats:

| Samples | p50 | p95 | p99 | min | max |
|---:|---:|---:|---:|---:|---:|
| 3 | 61.296 s | 61.575 s | 61.575 s | 60.560 s | 61.575 s |

**Correction to ADR-009:** 60 seconds is not a strict maximum. The observed
default recovery was **60.56–62.10 s** because the 60s lease, 30s scan
schedule, MySQL second-precision timestamps, worker startup and queue
scheduling all contribute. A future SLO must be defined explicitly; this
report does not invent one.

## 4. Load comparison

Small/Medium/Large = 20 jobs/1 worker, 50/2, 100/4; 3 repeats each. Latency is
measured with monotonic clocks; queue wait starts at publish.

| Scheme | Size | Jobs/s p50 | Queue wait p95 (median) | E2E p95 (median) | Errors |
|---|---:|---:|---:|---:|---:|
| List | 20/1 | 7.16 | 2.42 s | 2.55 s | 0 |
| List | 50/2 | 14.62 | 3.08 s | 3.19 s | 0 |
| List | 100/4 | 24.49 | 3.43 s | 3.73 s | 0 |
| BLMOVE | 20/1 | 6.39 | 2.78 s | 2.89 s | 0 |
| BLMOVE | 50/2 | 13.77 | 3.30 s | 3.43 s | 0 |
| BLMOVE | 100/4 | 22.51 | 3.92 s | 4.04 s | 0 |
| Streams | 20/1 | 6.44 | 2.80 s | 2.92 s | 0 |
| Streams | 50/2 | 13.10 | 3.49 s | 3.59 s | 0 |
| Streams | 100/4 | 25.94 | 3.38 s | 3.50 s | 0 |

All 27 load runs passed; 510 jobs per scheme, 0 failed, 0 redeliveries, 0
duplicate executions. The List path remains competitive at this scale.

### Resource sample

| Scheme | Worker CPU mean | Worker RSS max | MySQL CPU mean | MySQL RSS max | Redis CPU mean | Redis memory |
|---|---:|---:|---:|---:|---:|---:|
| List | 50.9% | 486 MiB | 48.4% | 1.10 GiB | 2.8% | ~2.3 MB |
| BLMOVE | 42.1% | 495 MiB | 44.4% | 1.11 GiB | 2.2% | ~2.3 MB |
| Streams | 45.3% | 521 MiB | 49.4% | 1.13 GiB | 3.5% | ~2.3 MB |

These are same-host Docker/WSL2 samples, not isolated capacity planning data.

## 5. Consistency and fencing

All scenarios preserve the MySQL invariants:

1. PENDING → RUNNING has one successful claim per attempt.
2. `attempts` increments on reclaim; stale workers cannot overwrite.
3. Duplicate messages cause one claim and one success audit.
4. Completed jobs are not executed again by duplicate delivery.
5. Max-attempts exhaustion ends in FAILED with `WORKER_LEASE_EXPIRED` and one
   failure audit.
6. Recovery is conditional/atomic; two recoverers do not duplicate a state
   transition.
7. Quality issues are deduplicated by the existing unique constraint; no
   duplicate issue rows were observed.
8. Outbox state is consistent or reconciled after alternative delivery.

## 6. Decision

**Decision A: keep List + Outbox + compensation.**

Reasons:

1. No production recovery SLO exists. The default path recovered in
   60.56–62.10s; that is a documented at-least-once boundary, not a hidden
   exactly-once claim.
2. BLMOVE/Streams shorten recovery under a 4s experiment lease, but add
   processing-list ownership/cleanup or PEL/consumer-group/trimming operations.
   The measured difference does not justify a production migration without a
   requirement.
3. List + Outbox remains competitive in throughput and has the smallest
   operational surface. It already preserves fencing/idempotency.
4. If a recovery SLO below 60s is later required, **BLMOVE is the first
   candidate** because its recovery model is simpler than Streams. Streams is
   only justified if consumer coordination, PEL observability, or trimming
   become requirements.

This is an evaluation decision, not a production queue change. The production
`BRPOP` + outbox path is untouched. Issue #40 can be closed with this evidence;
a future implementation issue must include migration, gray release, rollback,
monitoring and acceptance gates.

Re-evaluate if: recovery p95 SLO <60s is defined; queue depth/throughput
exceeds the measured List baseline; or incidents show 60s recovery is
unacceptable.

## 7. Limitations

- Synthetic 200-school/4-province workload, not production data.
- WSL2/Docker single host; no multi-AZ/network partition testing.
- Shortened 4s lease results are not production defaults; only List was
  validated at 60/30/600.
- Default validation has only 3 samples; p99 is not statistically strong.
- Redis restart uses AOF + `SAVE` on the dedicated volume; this is not a
  disaster-recovery test.
- `at-least-once` is not `exactly-once`; no claim is made otherwise.
