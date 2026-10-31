# ADR-009: Redis delivery model — keep List + Outbox compensation for now

- Status: Accepted (evaluation)
- Date: 2026-10-31
- Related: Issue #40, ADR-008, `server/admin/queue.py`, `server/admin/worker.py`

## Context

The current quality-job queue is a Redis List carrying job ids. Publishing is
protected by a transactional outbox; `BRPOP` can lose a message if the worker
dies before the database claim. A compensation scan re-arms
`PENDING + DISPATCHED` rows after a 60-second delivery lease. Workers scan every
30 seconds. The database is the source of truth; `claim_job` is atomic and uses
an attempts-based fencing token.

Issue #40 asks whether to replace this with Redis Streams/consumer groups or
another delivery mechanism. No production throughput or recovery-latency SLO
exists yet; this ADR is a technical comparison, not a refactor approval.

## Options

| Criterion | List + Outbox compensation (current) | BRPOPLPUSH/BLMOVE processing list | Redis Streams consumer group |
|---|---|---|---|
| Message handoff | `BRPOP` removes immediately | atomically moves to processing list | `XREADGROUP` creates pending entry |
| Explicit ACK | no | remove from processing list | `XACK` |
| Recovery after worker crash | 60s lease + 30s scan | inspect processing list; requeue immediately | `XAUTOCLAIM`/`XPENDING` with idle threshold |
| Duplicate delivery | possible; absorbed by atomic claim + fencing | possible; same | possible; same |
| Recovery latency | up to ~60s by design | seconds (scan interval) | seconds to idle-threshold |
| Redis storage | one list | one queue + one processing list | stream + PEL + consumer metadata |
| Operational complexity | low | medium (processing-list cleanup/leases) | high (consumer names, PEL, trimming, group recovery) |
| Existing tests | SQLite/MySQL/Redis + full Compose | would need new fault tests | would need new fault tests |
| Fit for current scale | sufficient | good upgrade path | likely overkill without measured need |

## Decision

Keep **List + Outbox + compensation** for this round.

Reasons:

1. The database is the source of truth; duplicate delivery is already safe
   (atomic `claim_job`, fencing token, unique quality-issue constraint).
2. The current recovery bound is explicit and tested (60s delivery lease,
   30s scan). There is no measured requirement that demands lower latency.
3. Introducing Streams would add consumer-group/PEL/trimming operations without
   load data proving a benefit.
4. The simplest future upgrade, if recovery latency becomes a requirement, is a
   `BLMOVE` processing list; Streams should be considered only after Issue #38
   produces throughput/latency data.

## Consequences

- Keep the documented at-least-once semantics; not exactly-once.
- Keep recovery latency visible in `performance.md`.
- Revisit when any of these triggers is met:
  - recovery p95 must be < 10 seconds;
  - queue depth/throughput exceeds the measured List baseline;
  - operational incidents show repeated 60s recovery is unacceptable.
- A future change must add fault injection for BRPOP/claim/ACK windows and
  preserve fencing/idempotency.

## References

- Issue #40
- ADR-008
- `docs/interview-readiness/performance.md`
- `tests/test_worker_integration.py`
