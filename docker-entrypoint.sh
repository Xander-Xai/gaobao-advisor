#!/bin/sh
# Container entrypoint for the public demo and the optional full profile.
#
# SQLite (default): generate the deterministic SYNTHETIC database if absent.
# MySQL (full profile): wait for readiness, run Alembic migrations, and
# optionally seed the synthetic demo once. No credentials are baked into the
# image; everything comes from the environment.

set -eu

DB_PATH="${GAOBAO__DB_PATH:-data/demo.db}"
export DATABASE_URL="${DATABASE_URL:-sqlite:///${DB_PATH}}"

# RAG ships enabled against the bundled SYNTHETIC_DEMO knowledge corpus.
export ENABLE_RAG_KB="${ENABLE_RAG_KB:-true}"

case "${DATABASE_URL}" in
    mysql://*|mysql+pymysql://*)
        echo "[entrypoint] MySQL mode; waiting for migrations"
        attempt=1
        while ! python -m db.migrate; do
            if [ "${attempt}" -ge 30 ]; then
                echo "[entrypoint] migrations failed after ${attempt} attempts" >&2
                exit 1
            fi
            attempt=$((attempt + 1))
            sleep 2
        done
        if [ "${AUTO_SEED_DEMO:-false}" = "true" ]; then
            echo "[entrypoint] ensuring SYNTHETIC_DEMO dataset exists"
            python -m scripts.seed_demo_data --database-url "${DATABASE_URL}"
        fi
        ;;
    *)
        if [ ! -f "${DB_PATH}" ]; then
            echo "[entrypoint] no demo database at ${DB_PATH}; generating SYNTHETIC data..."
            python -m scripts.seed_demo_data --db "${DB_PATH}" --reset
        else
            echo "[entrypoint] using existing demo database at ${DB_PATH}"
        fi
        ;;
esac

echo "[entrypoint] starting: $*"
exec "$@"
