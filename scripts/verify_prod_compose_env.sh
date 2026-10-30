#!/usr/bin/env bash
# Real production-Compose credential tests.
#
# This script does not use the repository's .env.production. It creates
# temporary, mode-0600 env files with ephemeral test secrets and removes them
# in the cleanup trap. Nothing is committed.
#
# Cases:
#   1. missing env file                -> Compose fails closed
#   2. production without SESSION_SECRET -> app exits non-zero
#   3. admin enabled without ADMIN_TOKEN_SECRET -> app exits non-zero
#   4. valid SESSION_SECRET + ADMIN_*    -> API healthy and admin login works
#
# Usage:
#   PROD_API_IMAGE=gb-advisor:ci bash scripts/verify_prod_compose_env.sh
#   bash scripts/verify_prod_compose_env.sh   # builds the image if missing

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

IMAGE="${PROD_API_IMAGE:-gaobao-advisor-api:prod}"
PROJECT="gaobao-prod-envtest-$$"
PORT="${PROD_API_PORT:-18002}"
CONTAINER_NAME="gaokao-api-prod-envtest-$$"
TMP="$(mktemp -d)"
chmod 700 "$TMP"
touch "$TMP/valid.env"
chmod 600 "$TMP/valid.env"

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
    echo "[prod-env-test] image $IMAGE not found; building it (this can take a while)"
    docker build -t "$IMAGE" "$ROOT"
fi

compose() {
    PROD_ENV_FILE="${PROD_ENV_FILE:-$TMP/valid.env}" \
    PROD_API_IMAGE="$IMAGE" \
    PROD_API_PORT="$PORT" \
    PROD_API_CONTAINER_NAME="$CONTAINER_NAME" \
        docker compose -p "$PROJECT" -f "$ROOT/docker-compose.prod.yml" "$@"
}

cleanup() {
    PROD_ENV_FILE="$TMP/valid.env" \
    PROD_API_IMAGE="$IMAGE" \
    PROD_API_PORT="$PORT" \
    PROD_API_CONTAINER_NAME="$CONTAINER_NAME" \
        docker compose -p "$PROJECT" -f "$ROOT/docker-compose.prod.yml" down -v --remove-orphans >/dev/null 2>&1 || true
    rm -rf "$TMP"
}
trap cleanup EXIT

write_env() {
    local path="$1"
    local with_session="$2"
    local with_admin_secret="$3"
    local with_admin_user="$4"
    local admin_hash=""
    if [ "$with_admin_user" = "yes" ]; then
        admin_hash="$(docker run --rm --entrypoint python "$IMAGE" -c \
            'from server.admin.auth import hash_password; print(hash_password("compose-test-password-2026", iterations=10000))')"
    fi
    {
        echo "APP_ENV=production"
        echo "DATABASE_URL=sqlite:////app/data/demo.db"
        echo "QUALITY_TASK_MODE=inline"
        if [ "$with_session" = "yes" ]; then
            echo "SESSION_SECRET=$(openssl rand -hex 32)"
        fi
        if [ "$with_admin_user" = "yes" ]; then
            echo "ADMIN_USERS_JSON='[{\"username\":\"compose-admin\",\"password_hash\":\"${admin_hash}\",\"role\":\"admin\"}]'"
        fi
        if [ "$with_admin_secret" = "yes" ]; then
            echo "ADMIN_TOKEN_SECRET=$(openssl rand -hex 32)"
        fi
    } > "$path"
    chmod 600 "$path"
}

run_negative() {
    local env_file="$1"
    local expected="$2"
    local label="$3"
    local log="$TMP/${label}.log"
    local status=0
    set +e
    PROD_ENV_FILE="$env_file" compose run --rm --no-deps -T api >"$log" 2>&1
    status=$?
    set -e
    if [ "$status" -eq 0 ]; then
        echo "[prod-env-test] FAIL: $label unexpectedly started"
        cat "$log"
        exit 1
    fi
    if ! grep -q "$expected" "$log"; then
        echo "[prod-env-test] FAIL: $label exited but did not show expected message: $expected"
        cat "$log"
        exit 1
    fi
    echo "[prod-env-test] PASS: $label failed closed (exit=$status)"
}

echo "[prod-env-test] image=$IMAGE project=$PROJECT port=$PORT"

# 1. Missing env file: Compose itself must refuse to start.
set +e
PROD_ENV_FILE="$TMP/does-not-exist.env" compose config >"$TMP/missing-file.log" 2>&1
missing_status=$?
set -e
if [ "$missing_status" -eq 0 ]; then
    echo "[prod-env-test] FAIL: missing env file was accepted"
    cat "$TMP/missing-file.log"
    exit 1
fi
if ! grep -Eqi "env file.*not found|not found|required" "$TMP/missing-file.log"; then
    echo "[prod-env-test] FAIL: missing env file failed for an unexpected reason"
    cat "$TMP/missing-file.log"
    exit 1
fi
echo "[prod-env-test] PASS: missing env file rejected"

# 2. Production without SESSION_SECRET.
write_env "$TMP/no-session.env" no no no
run_negative "$TMP/no-session.env" "SESSION_SECRET must be set in production" "no-session-secret"

# 3. Admin configured but ADMIN_TOKEN_SECRET missing.
write_env "$TMP/no-admin-secret.env" yes no yes
run_negative "$TMP/no-admin-secret.env" "ADMIN_TOKEN_SECRET must be set in production" "no-admin-token-secret"

# 4. Valid configuration: start, become healthy, and log in.
write_env "$TMP/valid.env" yes yes yes
PROD_ENV_FILE="$TMP/valid.env" compose up -d --no-build api >"$TMP/up.log" 2>&1
ready=0
for _ in $(seq 1 45); do
    if curl --noproxy '*' -fsS "http://127.0.0.1:${PORT}/api/v1/health/ready" >"$TMP/health.json" 2>/dev/null; then
        ready=1
        break
    fi
    sleep 1
done
if [ "$ready" -ne 1 ]; then
    echo "[prod-env-test] FAIL: API did not become ready"
    cat "$TMP/up.log"
    docker logs "$CONTAINER_NAME" 2>&1 | tail -80 || true
    exit 1
fi

curl --noproxy '*' -fsS -X POST "http://127.0.0.1:${PORT}/api/v1/admin/auth/login" \
    -H 'Content-Type: application/json' \
    -d '{"username":"compose-admin","password":"compose-test-password-2026"}' \
    >"$TMP/login.json"
python3 - "$TMP/login.json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    body = json.load(handle)
assert body["user"] == {"username": "compose-admin", "role": "admin"}, body
assert len(body["access_token"]) > 20, body
print("[prod-env-test] PASS: valid production env started and admin login succeeded")
PY

echo "[prod-env-test] ALL PASS"
