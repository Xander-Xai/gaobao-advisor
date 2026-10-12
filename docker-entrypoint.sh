#!/bin/sh
# Container entrypoint for the public demo.
#
# Guarantees the service starts against a SYNTHETIC dataset. There is no real
# database in this image and none is downloaded at build or run time: if the
# demo database is absent it is generated locally from
# `scripts/seed_demo_data.py`, which is fully deterministic.

set -eu

DB_PATH="${GAOBAO__DB_PATH:-data/demo.db}"
export DATABASE_URL="${DATABASE_URL:-sqlite:///${DB_PATH}}"

# RAG is shipped disabled because no redistributable corpus is bundled.
# Force it off so a stray environment variable cannot make the service claim
# a retrieval capability it does not have.
export ENABLE_RAG_KB=false

if [ ! -f "${DB_PATH}" ]; then
    echo "[entrypoint] no demo database at ${DB_PATH}; generating SYNTHETIC data..."
    python -m scripts.seed_demo_data --db "${DB_PATH}" --reset
else
    echo "[entrypoint] using existing demo database at ${DB_PATH}"
fi

echo "[entrypoint] starting uvicorn on :8000 (data profile: SYNTHETIC_DEMO)"
exec "$@"