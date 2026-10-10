# Security and license blockers

This file records what is still missing before the project may be published. It
is a fact-finding checklist, not a legal opinion and not an approval. Nothing
here should be read as "cleared".

The machine-readable form of this list is `config/compliance_attestation.yaml`,
which `scripts/check_release_evidence.py` reads. While any item there is
`blocked`, the `release-evidence` CI job fails on purpose.

## Status

| Item | Status | Owner |
|---|---|---|
| Data rights for imported admission/school/major records | **blocked** | repository owner |
| Operator privacy notice accuracy | **blocked** | repository owner |
| Redistribution rights for public artifacts | **blocked** | repository owner |
| Third-party dependency and content license review | **blocked** | repository owner |
| Database archives in public Git history | **blocked** | repository owner |

Current verdict: **PUBLIC_RELEASE_BLOCKED**. `ENGINEERING_READY` and `DEMO_READY`
are unaffected and are separately green.

## B1 — Database archives are reachable in the public Git history

**Fact.** `git ls-tree -r origin/master backups/` lists two archives:

```
backups/gaokao_db_20260617_013418.sql.gz   16,910,890 bytes
backups/gaokao_db_20260617_025354.sql.gz   16,977,063 bytes
```

Their content is a gzipped SQLite database (see
`DATA_RECOVERY_AND_QUALITY.md §1`). The second archive contains 400,194
`admission_scores` rows, 3,020 schools and user conversation rows. They have
been tracked since they were committed and remain reachable from every commit on
`master` up to the release-boundary commit, including through PR #5's base.

**Why it matters.** The repository is public. The blobs contain the full imported
dataset plus conversation data. Even though this branch untracks them, anyone can
retrieve them with `git show origin/master:backups/<name>`.

**What was done here.** The archives were untracked and `backups/` was added to
`.gitignore`. `scripts/audit_open_source.sh` now fails on `master` and passes on
this branch. The archives themselves were **not** modified.

**What is required.** Decide whether the data may be redistributed at all
(see B2). If not, the blobs must be purged from history with
`git filter-repo --path backups --invert-paths` across **all** refs, followed by
a force-push and coordination with anyone who has cloned the repository. This is
destructive and irreversible and has **not** been performed. Until it is, the
history leak remains.

## B2 — Rights to the imported data

**Fact.** `DATA_SOURCES.md` lists the upstream sources used by the importers
under `scripts/import_*.py`. None of them carries a recorded written permission
for redistribution. The `DATA_LICENSE.md` position is that no license is granted
for imported records and that this is the operator's responsibility.

**Why it matters.** "Publicly accessible" is not "licensed for redistribution".
高考 admission data is collected by provincial examination authorities; usage and
redistribution terms vary and are frequently restricted.

**Fact-finding checklist** — for each source, record:

- [ ] Source name, URL and operator; date accessed; collection method.
- [ ] Whether the source publishes terms of use and what they say about reuse,
      redistribution and commercial use.
- [ ] Whether robots.txt / API terms permit automated collection at the rate used.
- [ ] Whether the data contains personal information (candidate names, IDs,
      scores tied to individuals). If yes, stop: it cannot be published.
- [ ] The legal basis for processing in the operator's jurisdiction.
- [ ] A named person and date for the decision.

Until every row above is answered and the answer permits redistribution, the
imported data must not be published and `data_rights` stays `blocked`.

## B3 — Operator privacy notice

**Fact.** `PRIVACY.md` describes the repository defaults, states that operators
are responsible for a user-facing notice, and — after this change — is explicitly
marked `Status: draft pending review`.

**Why it matters.** The application processes province, score, subject and
interest data, and is likely to be used by minors. `PRIVACY.md` names no
retention period and has not been checked against any jurisdiction's law.

**Checklist:**

- [ ] Choose a jurisdiction and review `PRIVACY.md` against its rules for
      personal information, including rules specific to minors.
- [ ] State a concrete retention period for conversations, reports, analytics
      events, logs and backups.
- [ ] Confirm the deletion procedure actually removes data from backups, or
      document that it does not.
- [ ] Confirm no real identifying information is requested in the UI.
- [ ] Record reviewer and date.

## B4 — Redistribution rights for public artifacts

**Fact.** `config/open_source_assets.tsv` classifies several tracked or
previously tracked assets as `exclude` because their provenance is unconfirmed:
`demo-preview.gif`, `frontend/public/favicon.svg`, `frontend/public/icons.svg`,
`frontend/src/assets/`, `frontend/src/design/prototypes/`, plus the entire
`knowledge/`, `prompts/`, `content_scripts/`, `memory/` and `skills/gaokao/`
trees.

**Why it matters.** Screenshots can embed third-party logos and real data;
upstream icon and design assets may be imported from an MIT/Apache project that
requires attribution; scraped editorial content may be copyrighted.

**Checklist:**

- [ ] Replace `demo-preview.gif` with a screenshot containing only synthetic data,
      or remove it. (It is already excluded from this branch's tracked tree.)
- [ ] Record the origin and license of every icon/mark in `frontend/public/` and
      `frontend/src/assets/`.
- [ ] Confirm `knowledge/`, `prompts/`, `skills/` contain no copied third-party
      text; if they do, either remove it or record the permission.
- [ ] Re-run `bash scripts/audit_open_source.sh --release` after each change.

## B5 — Third-party license review

**Fact.** `THIRD_PARTY_NOTICES.md` is generated from the dependency manifests.
`scripts/check_licenses.py` passes (no AGPL/SSPL/UNKNOWN identifiers in the
Python or npm dependency sets).

**Why it matters.** Automated license classification is a starting point. It
misses bundled assets, transitively vendored code, and copyright notices that
must be reproduced.

**Checklist:**

- [ ] A human reads `THIRD_PARTY_NOTICES.md` and confirms it covers every
      dependency with an attribution requirement.
- [ ] Confirm the `streamlit` dependency (declared in `requirements.txt` for the
      legacy UI) is intentional in the community edition, or remove it.
- [ ] Confirm no dependency was added under a license that conflicts with MIT.

## What is explicitly NOT claimed

- This repository has **not** received a legal review.
- `PRIVACY.md` and `DATA_LICENSE.md` are drafts. They are not approved statements
  and confer no rights.
- Passing `release-readiness` in CI means the mechanical checks passed. It does
  **not** mean the project is cleared to publish.
- No gate was skipped, mocked, or marked green to make CI look better. If
  `release-evidence` is red, that is the correct and intended state.

## How to clear a blocker

1. Perform the review described above.
2. Record the outcome in `config/compliance_attestation.yaml`: set the item to
   `approved`, `rejected` or `not-applicable`, and fill in `reviewer` and
   `reviewed_at`.
3. Re-run `python scripts/check_release_evidence.py`.
4. `PUBLIC_RELEASE_READY` may be claimed only when the command exits `0`.
