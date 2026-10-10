# Data recovery and quality

All numbers in this document were measured from the working copy on 2026-10-10
with `scripts/data_quality_report.py` and `scripts/dedupe_admission_scores.py`.
None of them are carried over from an earlier report. Re-run the commands before
trusting a number.

## 1. What the backups actually are

Two archives exist under `backups/`. Their extension says `.sql.gz`; their bytes
say something else.

| File | Declared name | Actual content | SHA-256 |
|---|---|---|---|
| `gaokao_db_20260617_013418.sql.gz` | `.sql.gz` | `gzip → sqlite` | `e3aafbc32e1e5fc16335ca901c10dc2b9c4a5e082677c8328ba8b9ceab073db5` |
| `gaokao_db_20260617_025354.sql.gz` | `.sql.gz` | `gzip → sqlite` | `17ca2fc88038b0440b643400611f8279597946d7941e4a4c21eddd9c6e95da1b` |

`scripts/backup_db.sh` copied `data/gaokao.db` and gzipped it, then named the
result `.sql.gz`. It was never a SQL dump. Any tool that parses these by
extension — including a restore procedure that pipes them into `sqlite3` — is
wrong.

`scripts/db_archive.py` now identifies archives by magic bytes and reports the
mismatch:

```bash
python scripts/restore_db.py --archive backups/gaokao_db_20260617_025354.sql.gz
# [1] actual content : gzip -> sqlite
#     NOTE: the extension implies a SQL dump but the bytes are a SQLite database.
```

`scripts/db_archive.make_sqlite_backup()` replaces the copy-and-gzip approach
with SQLite's online backup API so a future snapshot is consistent even while
the database is in WAL mode.

## 2. These archives are currently tracked in the public repository

`git ls-tree origin/master backups/` lists both archives (~34 MB compressed,
~182 MB uncompressed). They are tracked on `origin/master` and on the PR #5
branch. The open-source release-boundary commit untracks them and adds
`backups/` to `.gitignore`; that is why `scripts/audit_open_source.sh` fails on
`master` but passes on this branch.

**Removing them from the current tree does not remove them from history.** The
blobs remain reachable from every commit on `master` up to the point they were
deleted. Scrubbing history requires a rewrite and a force-push, which is a
destructive, irreversible change to a public repository. It is listed as a
blocker and is **not** performed here. See
`SECURITY_AND_LICENSE_BLOCKERS.md`.

## 3. Restore procedure

`scripts/restore_db.py` is dry-run by default. It refuses to write unless every
precondition holds:

- the archive is identified from its bytes and must carry a `sqlite` payload;
- if `--sha256` (or `--manifest`) is supplied, the digest must match;
- `--confirm-data-rights` must be present, so an operator has to state that the
  data rights are cleared;
- the target must not already exist unless `--replace-target` is given;
- the current database is snapshotted to `backups/pre_restore_<timestamp>.db`
  before anything is written.

```bash
# inspect only (default)
python scripts/restore_db.py --archive backups/gaokao_db_20260617_025354.sql.gz

# restore into a scratch path once rights are cleared
python scripts/restore_db.py \
  --archive backups/gaokao_db_20260617_025354.sql.gz \
  --sha256 17ca2fc88038b0440b643400611f8279597946d7941e4a4c21eddd9c6e95da1b \
  --confirm-data-rights --target /tmp/restored.db --apply
```

`scripts/db_archive.write_manifest()` / `read_manifest()` record digests and
row counts so a later restore can be checked against the exact archive that was
reviewed, not just a file name.

## 4. Measured state of `data/gaokao.db`

### Row counts

| Table | Rows |
|---|---|
| `admission_scores` | 380,671 |
| `yi_fen_yi_duan` | 80,902 |
| `enrollment_plans` | 71,725 |
| `schools` | 3,020 |
| `quality_scores` | 1,159 |
| `subject_rankings` | 549 |
| `majors` | 215 |
| `career_trend` | 70 |
| `highlights` | 66 |
| `graduate_program`, `graduate_score`, `feedbacks` | 0 |

### Coverage and freshness

- `PRAGMA integrity_check` → `ok`.
- Schools with admission data: **2,908 / 3,020 (96.3%)**; **112** schools have
  none.
- Majors appearing in admission data: **194 / 215 (90.2%)**.
- Admission rows by year: 2022 `71,270` · 2023 `68,378` · 2024 `155,393` ·
  2025 `85,630`. Latest year **2025**; the freshness window is two years.
- **251,238** admission rows are not linked to a major (`major_id IS NULL`);
  these are school-level records and cannot support a major-level recommendation.
- Rows missing `min_score`: **106**. Rows missing `min_rank`: **595** (0.2%).
- Provinces: **31** real province labels plus one placeholder bucket `ALL` with
  **1,311** rows. `ALL` is not a province and is flagged by the report.

### Duplicates, classified

| Tier | Rows | Groups | Meaning |
|---|---|---|---|
| Byte-identical (every non-id column equal) | **3,429** | 2,190 | Safe to collapse; keeping `MIN(id)` loses nothing. |
| Same business key, conflicting payload | **3,826** | **559** | Distinct published observations (征集志愿 rounds, 降分录取, parallel batches). **Do not deduplicate blindly.** |

Earlier remediation removed 11,335 rows as duplicates. The measurement above
shows the residual is much smaller and that a meaningful part of what looks like
a duplicate actually carries conflicting scores. Treating all of it as noise
would have destroyed information.

## 5. Deduplication plan (dry run only)

`scripts/dedupe_admission_scores.py` separates the two tiers and refuses to
touch the second one.

```bash
python scripts/dedupe_admission_scores.py --database data/gaokao.db --json plan.json
```

| Output | Value |
|---|---|
| Rows that would be deleted (tier 1) | 3,429 |
| Groups affected (tier 1) | 2,190 |
| Keep rule | lowest `id` survives (first writer wins) |
| Rows in conflicting groups (tier 2) | 3,826 |
| Conflicting groups (tier 2) | 559 |
| Tier 2 action | reported only, never deleted |

Applying tier 1 to a **scratch copy** (verified, integrity `ok`): `380,671 →
377,242`, `deleted=3,429`, every removed id written to a JSON audit log under
`data/dedupe-logs/`.

Applying to the live database requires both `--apply` **and**
`--allow-live-database`. That was **not** run against `data/gaokao.db`; the live
database is unchanged at 380,671 rows.

### Suggested order of operations

1. Confirm data rights (blocker).
2. Copy `data/gaokao.db` to a scratch path.
3. Run tier 1 on the copy; confirm `PRAGMA integrity_check` is `ok` and the row
   count matches the plan.
4. Review the 559 tier-2 conflicting groups by hand — decide per group whether
   the multiplicity is real.
5. Only after review, apply to the live database with `--allow-live-database`.

## 6. The empty-database false pass is fixed

The previous checker printed `0/0` and reported "0% 缺失 / 0 条重复，因此通过"
for an database with no rows. Both cases now block:

| Input | Result |
|---|---|
| 0-byte file | `BLOCKED ... is a 'unknown' file, not a SQLite database`, exit `2` |
| Schema created, zero rows | `BLOCKED ... admission_scores holds 0 rows`, exit `2` |
| Missing `schools`/`majors`/`admission_scores` | `BLOCKED ... missing required tables`, exit `2` |

`scripts/data_quality_report.py` will not emit a `coverage`, `freshness` or
`duplicate` statement for a database it cannot measure.

## 7. Recommendation-quality consequence

`server/graph/nodes/data_nodes.py` records what it found, and
`server/services/data_query.annotate_provenance()` downgrades any record whose
source or year cannot be verified to `provenance_status = unverified` with
`confidence_score <= 20`. `reason` / `structure` then render the risk note
`来源或年份无法验证，不作为录取依据`.

The measured gaps — 112 schools with no data, 251,238 rows with no major, a
`ALL` province bucket, and 559 conflicting groups — all feed this path. The
observable behavior is covered by `tests/test_business_smoke.py`
(`TestEmptyAndIncompleteData`, `TestProfileAndExtraction`), and by
`tests/test_business_smoke.py::TestRuntimeConfigurationDifference` for the demo
disclosure contract.

A recommendation produced from a database this incomplete must not be presented
as a definite admission decision. The pipeline already prefixes demo replies
with the community-demo disclosure and appends the official-source disclaimer;
operators serving real data must keep an equivalent disclaimer.

## 8. Commands

```bash
python scripts/data_quality_report.py --database data/gaokao.db --json report.json
python scripts/dedupe_admission_scores.py --database data/gaokao.db
python scripts/restore_db.py --archive <archive> --sha256 <digest>
```

## 9. The test suite no longer writes to the working database

While measuring this database it was noticed that an ordinary `pytest` run
appended conversation rows to `data/gaokao.db` (73 → 82 rows) because
`db.database` resolves its path from `GAOBAO__DB_PATH` at import time and
defaults to the working database.

`conftest.py` now redirects `GAOBAO__DB_PATH`, `GAOBAO__ANALYTICS_DB_PATH` and
`GAOBAO__REPORTS_DIR` to a throwaway directory before the application is
imported, so a test run cannot mutate development or real data. Verified:
`conversations` remained at 82 across a full run.

To test against the configured database deliberately, set
`GAOBAO_TEST_USE_LIVE_DB=1`.

The rows those earlier runs added were not removed — that would be another
unrequested mutation of the working database. The measured metrics in this
document were taken after that point and are unaffected, because the added rows
are conversation records, not `admission_scores`.
