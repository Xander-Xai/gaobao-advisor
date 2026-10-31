# Queue Recovery Experiment (Issue #40)

Compares three Redis delivery models under the same synthetic workload and the
same MySQL state machine:

- **List + Outbox** — current production path (`BRPOP` + outbox compensation).
- **BLMOVE processing list** — atomic move to a processing list plus a
  delivery-level lease/ACK.
- **Streams consumer group** — `XADD` / `XREADGROUP` / `XACK` /
  `XAUTOCLAIM` with a pending entries list.

The database remains the source of truth. Every scheme uses the real
`execute_job` claim/fencing/audit path. BLMOVE and Streams are experiment
adapters; production wiring is unchanged.

## Isolated environment

```bash
docker compose -p gaobao-qr \
  -f benchmarks/queue_recovery/docker-compose.yml up -d

MYSQL_BENCH_URL='mysql+pymysql://root:qrroot@127.0.0.1:3310/gaobao_queue_recovery_benchmark?charset=utf8mb4&read_timeout=5&write_timeout=5' \
REDIS_BENCH_URL='redis://127.0.0.1:6382/0' \
REDIS_CONTAINER=gaobao-qr-redis-1 \
MYSQL_CONTAINER=gaobao-qr-mysql-1 \
python -m benchmarks.queue_recovery.runner \
  --suite all --schemes list blmove streams \
  --repeats 5 --load-repeats 3 --default-repeats 3 \
  --json-out /tmp/queue-recovery.json
```

`docker-compose.yml` uses a dedicated project, database, Redis AOF volume,
ports 3310/6382, and a MySQL/Redis ownership guard. It never calls
`FLUSHDB`, `FLUSHALL`, or drops a shared database.

## Fault scenarios

`published_not_consumed`, `after_consume`, `after_claim`,
`during_execute`, `after_db_before_ack`, `after_ack_crash`,
`duplicate_delivery`, `two_recoverers`, `redis_unavailable`,
`redis_restart`, `mysql_unavailable`, `max_attempts`.

Faults are real process deaths: the child writes a precise marker, then the
parent sends SIGKILL. Recovery latency is measured with `time.monotonic()` from
the fault marker to terminal DB state plus an empty delivery channel.

Short experiments use 4s delivery/running leases and a 1s recovery scan. The
production-default run uses the real `run_forever` worker with 60s delivery
lease / 30s scan / 600s running lease. Shortened results are **not** production
defaults.

## Results

See `docs/performance/redis-queue-recovery.md` and
`docs/performance/results/queue-recovery-final.json`.
