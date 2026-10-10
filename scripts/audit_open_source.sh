#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

require_gitleaks=0
scan_history=0
release_mode=0

usage() {
  cat <<'EOF'
Usage: bash scripts/audit_open_source.sh [--history] [--require-gitleaks] [--release]

Audits the tracked public candidate for generated artifacts, sensitive file
types, oversized files, and optionally secrets in the complete Git history.
EOF
}

while (($#)); do
  case "$1" in
    --history) scan_history=1 ;;
    --require-gitleaks) require_gitleaks=1 ;;
    --release) release_mode=1 ;;
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
tracked_risk_pattern='(^\.claude/|(^|/)node_modules/|^backups/|^data/reports/|^frontend/test-results/|^test-results/|^logs/|^data/.*\.(db|sqlite|sqlite3)(\.|$)|(^|/)\.session_secret$)'
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

section "Data and content classification"
asset_registry="config/open_source_assets.tsv"
if [[ ! -f "$asset_registry" ]]; then
  fail "asset registry is missing: $asset_registry"
else
  unclassified_assets=""
  excluded_assets=""
  candidate_assets="$(git ls-files | grep -E \
    '^(data/|knowledge/|prompts/|content_scripts/|memory/|frontend/public/|frontend/src/assets/)|^skills/gaokao/.*\.md$|\.(png|jpe?g|gif|svg|webp|woff2?|ttf|otf)$' || true)"
  while IFS= read -r asset; do
    [[ -z "$asset" ]] && continue
    classified=0
    while IFS=$'\t' read -r path_prefix _asset_class distribution; do
      [[ -z "$path_prefix" || "$path_prefix" == \#* ]] && continue
      if [[ "$asset" == "$path_prefix"* ]]; then
        classified=1
        if [[ "$distribution" == "exclude" ]]; then
          excluded_assets+="$asset"$'\n'
        fi
        break
      fi
    done < "$asset_registry"
    if ((classified == 0)); then
      unclassified_assets+="$asset"$'\n'
    fi
  done <<< "$candidate_assets"

  unclassified_assets="${unclassified_assets%$'\n'}"
  excluded_assets="${excluded_assets%$'\n'}"
  if [[ -n "$unclassified_assets" ]]; then
    printf '%s\n' "$unclassified_assets"
    fail "tracked data/content assets are missing from the classification registry"
  else
    pass "all tracked data/content assets are classified"
  fi

  if ((release_mode)) && [[ -n "$excluded_assets" ]]; then
    printf '%s\n' "$excluded_assets"
    fail "release candidate still contains assets classified as exclude"
  elif [[ -n "$excluded_assets" ]]; then
    printf 'classified_exclusions=%s (release audit will fail until removed)\n' \
      "$(printf '%s\n' "$excluded_assets" | wc -l)"
  else
    pass "no tracked asset is classified as exclude"
  fi
fi

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
elif command -v docker >/dev/null 2>&1 && timeout 5 docker info >/dev/null 2>&1; then
  scan_root="$ROOT"
  candidate_dir=""
  if ((scan_history)); then
    gitleaks_command=(git .)
    scan_label="complete-history"
  else
    candidate_dir="$(mktemp -d)"
    trap 'rm -rf "$candidate_dir"' EXIT
    git archive "$(git write-tree)" | tar -xf - -C "$candidate_dir"
    scan_root="$candidate_dir"
    gitleaks_command=(dir /repo)
    scan_label="staged-candidate"
  fi
  if docker run --rm -v "$scan_root:/repo:ro" -w /repo \
    ghcr.io/gitleaks/gitleaks:v8.30.1 "${gitleaks_command[@]}" \
    --config /repo/.gitleaks.toml --redact=100 --no-banner; then
    pass "gitleaks ${scan_label} scan via container"
  else
    fail "containerized gitleaks found potential secrets in ${scan_label}"
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
