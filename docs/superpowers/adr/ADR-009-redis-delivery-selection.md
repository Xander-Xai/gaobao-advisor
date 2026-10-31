# ADR-009: Redis delivery model — keep List + Outbox compensation for now

- Status: Accepted (evaluation complete, 2026-10-31)
- Date: 2026-10-31
- Related: Issue #40, ADR-008, `server/admin/queue.py`, `server/admin/worker.py`

## Context

The current quality-job queue is a Redis List carrying job ids. Publishing is
protected by a transactional outbox; `BRPOP` can lose a message if the worker
dies before the database claim. A compensation scan re-arms
`PENDING + DISPATCHED` rows after a 60-second delivery lease. Workers scan every
30 seconds. The database is the source of truth; `claim_job` is atomic and uses
an attempts-based fencing token.

Issue #40 asked whether to replace this with Redis Streams/consumer groups or
another delivery mechanism. The comparison was executed against a real MySQL
8.4 + Redis 7.4 environment with real process-kill fault injection. No
production recovery SLO exists yet; this ADR is a technical comparison, not a
refactor approval.

Measured results (shortened 4s experiment lease, 1s scan; see
`docs/performance/redis-queue-recovery.md`):

| Scheme | Recovery p50 | Recovery p95 | Duplicate business executions | Load 100/4 p50 |
|---|---:|---:|---:|---:|
| List + Outbox | 2.615s | 3.884s | 0 | 24.49 jobs/s |
| BLMOVE | 2.338s | 6.459s | 0 | 22.51 jobs/s |
| Streams | 2.328s | 6.598s | 0 | 25.94 jobs/s |

The production-default List path (60s delivery lease / 30s scan / 600s running
lease) recovered in **60.56–62.10s** over 3 repeats. The 60s lease is **not a
strict maximum**: scan scheduling, queue/worker startup and MySQL second
precision can push recovery past 60s.

## Options

| Criterion | List + Outbox compensation (current) | BRPOPLPUSH/BLMOVE processing list | Redis Streams consumer group |
|---|---|---|---|
| Message handoff | `BRPOP` removes immediately | atomically moves to processing list | `XREADGROUP` creates pending entry |
| Explicit ACK | no | remove from processing list | `XACK` |
| Recovery after worker crash | 60s lease + 30s scan | inspect processing list; requeue immediately | `XAUTOCLAIM`/`XPENDING` with idle threshold |
| Duplicate delivery | possible; absorbed by atomic claim + fencing | possible; same | possible; same |
| Recovery latency | measured 60.56–62.10s at defaults; not a strict max | experiment p50 2.338s / p95 6.459s | experiment p50 2.328s / p95 6.598s |
| Redis storage | one list | one queue + one processing list | stream + PEL + consumer metadata |
| Operational complexity | low | medium (processing-list cleanup/leases) | high (consumer names, PEL, trimming, group recovery) |
| Existing tests | SQLite/MySQL/Redis + full Compose | would need new fault tests | would need new fault tests |
| Fit for current scale | sufficient; 24.49 jobs/s at 100/4 | good upgrade path; 22.51 jobs/s | 25.94 jobs/s but highest operational surface |

## Decision

Keep **List + Outbox + compensation** for this round.

Reasons:

1. The database is the source of truth; duplicate delivery is safe (atomic
   `claim_job`, fencing token, unique quality-issue constraint). All three
   schemes produced zero duplicate business executions in the fault matrix.
2. No production recovery SLO exists. The default List path was measured at
   60.56–62.10s; this is a documented at-least-once boundary, not a hidden
   exactly-once guarantee.
3. BLMOVE/Streams shortened recovery under the 4s experiment lease, but add
   processing-list ownership/cleanup or PEL/consumer-group/trimming operations.
   The measured benefit does not justify a production migration without an
   explicit requirement.
4. List remains competitive in throughput and has the smallest operational
   surface. If a <60s recovery SLO is later required, BLMOVE is the first
   candidate; Streams is justified only if consumer coordination/PEL
   observability/trimming become requirements.

The production `BRPOP` + outbox path is unchanged. A future implementation
issue must include migration, gray release, rollback, monitoring and acceptance
gates.

## Consequences

- Keep the documented at-least-once semantics; not exactly-once.
- Keep recovery latency visible in `performance.md` and
  `docs/performance/redis-queue-recovery.md`.
- Revisit when any of these triggers is met:
  - a recovery p95 SLO below 60s is explicitly required;
  - queue depth/throughput exceeds the measured List baseline;
  - operational incidents show repeated 60s recovery is unacceptable.
- A future change must preserve the real fault-injection harness
  (`benchmarks/queue_recovery/`) and the fencing/idempotency invariants.

## References

- Issue #40
- ADR-008
- `docs/interview-readiness/performance.md`
- `docs/performance/redis-queue-recovery.md`
- `benchmarks/queue_recovery/`
- `tests/test_worker_integration.py`
- `tests/test_queue_recovery.py`
