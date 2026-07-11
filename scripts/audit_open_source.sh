#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

require_gitleaks=0
scan_history=0

usage() {
  cat <<'EOF'
Usage: bash scripts/audit_open_source.sh [--history] [--require-gitleaks]

Audits the tracked public candidate for generated artifacts, sensitive file
types, oversized files, and optionally secrets in the complete Git history.
EOF
}

while (($#)); do
  case "$1" in
    --history) scan_history=1 ;;
    --require-gitleaks) require_gitleaks=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

failures=0
warnings=0

section() {
  printf '\n== %s ==\n' "$1"
}

fail() {
  printf 'FAIL %s\n' "$1"
  failures=$((failures + 1))
}

warn() {
  printf 'WARN %s\n' "$1"
  warnings=$((warnings + 1))
}

pass() {
  printf 'PASS %s\n' "$1"
}

section "Repository"
printf 'root=%s\n' "$ROOT"
printf 'commit=%s\n' "$(git rev-parse HEAD)"
printf 'branch=%s\n' "$(git branch --show-current)"

section "Tracked runtime and restricted artifacts"
tracked_risk_pattern='(^\.claude/|^backups/|^data/reports/|^frontend/test-results/|^test-results/|^logs/|^data/.*\.(db|sqlite|sqlite3)(\.|$)|(^|/)\.session_secret$)'
tracked_risks="$(git ls-files | grep -E "$tracked_risk_pattern" || true)"
if [[ -n "$tracked_risks" ]]; then
  printf '%s\n' "$tracked_risks"
  fail "tracked runtime/restricted artifacts found"
else
  pass "no tracked runtime/restricted artifacts"
fi

section "Tracked sensitive filenames"
sensitive_name_pattern='(^|/)(\.env($|\.)|secrets?\.(toml|ya?ml|json)$|credentials?\.(json|ya?ml)$|.*\.(pem|p12|pfx|key)$)'
sensitive_names="$(git ls-files | grep -E "$sensitive_name_pattern" || true)"
allowed_sensitive_names='^\.env\.example$|^\.streamlit/secrets\.toml\.example$'
unexpected_sensitive="$(printf '%s\n' "$sensitive_names" | grep -Ev "$allowed_sensitive_names" || true)"
if [[ -n "$unexpected_sensitive" ]]; then
  printf '%s\n' "$unexpected_sensitive"
  fail "unexpected tracked sensitive filenames found"
else
  pass "only approved configuration examples are tracked"
fi

section "Oversized tracked files"
large_files="$({
  while read -r _mode object _stage tracked_file; do
    printf '%s %s\n' "$object" "$tracked_file"
  done < <(git ls-files -s)
} | git cat-file --batch-check='%(objectsize) %(rest)' | awk '$1 >= 10485760')"
if [[ -n "$large_files" ]]; then
  printf '%s\n' "$large_files"
  fail "tracked files at or above 10 MiB found in current commit"
else
  pass "no tracked file is 10 MiB or larger"
fi

section "Asset categories"
printf 'code_files=%s\n' "$(git ls-files '*.py' '*.js' '*.vue' '*.ts' | wc -l)"
printf 'data_files=%s\n' "$(git ls-files 'data/**' '*.json' '*.csv' '*.db' | wc -l)"
printf 'content_files=%s\n' "$(git ls-files 'knowledge/**' 'prompts/**' 'content_scripts/**' | wc -l)"
printf 'documentation_files=%s\n' "$(git ls-files '*.md' | wc -l)"

section "Secret scanning"
if command -v gitleaks >/dev/null 2>&1; then
  if ((scan_history)); then
    if gitleaks git --config .gitleaks.toml --redact --no-banner; then
      pass "gitleaks complete-history scan"
    else
      fail "gitleaks found potential secrets in Git history"
    fi
  elif gitleaks dir . --config .gitleaks.toml --redact --no-banner; then
    pass "gitleaks working-tree scan"
  else
    fail "gitleaks found potential secrets in the working tree"
  fi
elif ((scan_history)) && command -v docker >/dev/null 2>&1 && timeout 5 docker info >/dev/null 2>&1; then
  if docker run --rm -v "$ROOT:/repo:ro" -w /repo \
    ghcr.io/gitleaks/gitleaks:v8.30.1 git . \
    --config /repo/.gitleaks.toml --redact=100 --no-banner; then
    pass "gitleaks complete-history scan via container"
  else
    fail "containerized gitleaks found potential secrets in Git history"
  fi
elif ((require_gitleaks)); then
  fail "gitleaks is required but neither the CLI nor a working Docker daemon is available"
else
  warn "gitleaks not installed; run CI or install it before release"
fi

section "Summary"
printf 'failures=%s warnings=%s\n' "$failures" "$warnings"
if ((failures > 0)); then
  exit 1
fi

pass "open-source repository audit completed"
