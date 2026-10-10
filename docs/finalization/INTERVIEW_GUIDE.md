# Interview guide

Talking points for presenting this project, grounded in things that can be
demonstrated in the repository. Every claim below points at a file or a command.
Do not present a claim whose evidence you have not looked at.

## 1. One-paragraph pitch

> gaobao-advisor is a self-hosted AI college-application advisor. The point is
> not "chat with an LLM" — it is that a real consultation is engineered as an
> explicit pipeline: security scan → intent → slot extraction → profile check →
> data query → hybrid retrieval → reasoning → structured card → source
> attribution → quality check → memory, orchestrated with LangGraph. It ships
> with a no-key community demo that runs on marked-synthetic data, and it
> refuses to dress up unverified numbers as advice: any record whose source or
> year cannot be verified is downgraded and labelled in the answer.

## 2. Architecture, in the order it executes

`server/graph/graph.py` wires the nodes. The path that answers a complete
question is:

```
security_scan → intent_detect → scene_route → slot_extract → profile_check
   ├── incomplete → question_generate → render_reply
   └── complete   → quality_orchestrate → data_query → rag_retrieve → reason
                    → structure_output → render_reply → source_attribution
                    → quality_post_check → quality_judge → feedback
                    → memory_update → END
```

Good design questions to invite:

- **Why LangGraph instead of a chain?** The incomplete-profile branch is a real
  control-flow decision, and `quality_post_check` can loop back to
  `render_reply` once. A graph makes those edges explicit and testable.
- **Why is the LLM not a node?** `graph.py`'s module docstring notes
  `llm_reason` was removed so the SSE handler streams tokens directly, avoiding a
  double model call. Token streaming is a transport concern; keeping it out of the
  graph keeps the graph deterministic and cheap to test.
- **Where is the trust boundary?** `security_scan` runs before anything else,
  and `source_attribution` runs after generation but before the reply is
  considered final.

## 3. Five deep dives worth preparing

### 3.1 The provenance downgrade

`server/services/data_query.annotate_provenance()` is the most product-defining
piece of code. A record with no declared source or year becomes
`provenance_status="unverified"`, `confidence_score <= 20`, and a note reading
`无法验证来源或年份，请以省考试院和高校官网为准`. `source_attribution` then injects
`数据来源待补全` into any sentence that states a score without a source.

Expect: "isn't that just a disclaimer?" Answer: no — it is a data-flow rule. The
score does not reach the user without a provenance decision attached, and the
decision is stored, not printed at the end.

Evidence: `tests/test_data_provenance.py`, `tests/test_source_attribution.py`,
`tests/test_business_smoke.py::TestEmptyAndIncompleteData`.

### 3.2 The deduplication that refuses to delete

The obvious "remove duplicates" query is
`GROUP BY (school, major, province, year, batch, subject)`. Measured against the
real database, that would touch 6,074 rows in 1,968 groups — and 559 of those
groups disagree on the recorded score. Those are distinct published
observations, not noise. The tool splits the work into a tier that is provably
lossless (byte-identical rows: 3,429) and a tier that is reported only, never
deleted.

Expect: "why not just delete the extras?" Answer: because "duplicate" from the
database's point of view is not "duplicate" from the domain's point of view, and
the measurement is in the tool's output, not in an assumption.

Evidence: `scripts/dedupe_admission_scores.py`,
`docs/finalization/DATA_RECOVERY_AND_QUALITY.md §4–5`,
`tests/test_data_quality_and_dedupe.py`.

### 3.3 The backup that lied about its format

Two archives named `*.sql.gz` are gzipped SQLite files. Any restore built on the
extension is wrong. `scripts/db_archive.py` identifies content by magic bytes and
will not extract a non-SQLite payload into a database path. The restore command
is dry-run by default, refuses to overwrite, snapshots the current database
first, and requires an explicit data-rights acknowledgement.

Expect: "how do you know it works?" Answer: it is tested against a real
repository archive whose SHA-256 is pinned, plus truncated-gzip and SQL-dump
cases. And the tool found a bug in itself during review — a generated `DELETE`
that grouped by `id` and would have deleted everything — which is why
`test_exact_delete_sql_never_groups_by_id` exists.

Evidence: `scripts/db_archive.py`, `scripts/restore_db.py`,
`tests/test_db_archive.py`.

### 3.4 Honest CI

CI separates functional readiness from release readiness. `release-readiness`
runs mechanical checks; `release-evidence` reads a human attestation and fails
while the compliance review is outstanding. Turning it green requires a person
to record a review, not a code change.

Expect: "your CI is red, isn't that bad?" Answer: one job is red on purpose.
It means `PUBLIC_RELEASE_BLOCKED`, and the blocker list is explicit. A green
functional matrix plus a red evidence gate is the truthful state of the project.

Evidence: `.github/workflows/ci.yml`, `scripts/check_release_evidence.py`,
`config/compliance_attestation.yaml`.

### 3.5 The demo that cannot lie

`LLM_PROVIDER=demo` returns a fixed reply, the health payload reports
`mode=demo`, and the reply stream is prefixed with a disclosure stating the data
is synthetic and the tool is unofficial. The synthetic dataset uses fictional
schools in a fictional province, so a real-province query returns
`暂无…数据` rather than an invented school.

Expect: "why does the demo ask for a province it can't answer about?" Answer:
because the alternative — fabricating a plausible answer — is the failure mode
this whole design is built to avoid.

Evidence: `docs/finalization/DEMO_MODE_CONTRACT.md`,
`tests/test_demo_seed.py`, `tests/test_business_smoke.py`.

## 4. Security decisions

- **Prompt injection and credential exfiltration** are detected before the
  graph runs (`server/middleware/security.py`). Injection blocks the request;
  an over-length input is rejected. During this work a gap was found and closed:
  the English patterns covered "reveal your system prompt" but the Chinese
  pattern set did not cover "告诉我你的 API Key", and it was not
  case-insensitive. Tests now cover both directions, including false-positive
  guards for legitimate questions that merely contain the word `密码`.
- **XSS**: chat input is tag-stripped at the schema (`ChatRequest.sanitize_message`)
  and at the middleware; model output is sanitized with DOMPurify in the
  frontend; CSP is set without `unsafe-inline` for scripts.
- **SSRF**: `check_ssrf` guards configured base URLs.
- **Session isolation**: HMAC session tokens scope profile, voice and chat
  access; `verify_session_token` rejects a token issued for another session.

Evidence: `tests/test_middleware_security.py`,
`tests/test_business_smoke.py::TestSessionIsolation`.

## 5. Questions to ask back

- "The data-quality verdict is `degraded`, not `ok`. Which metric would you
  prioritise first: 251k rows with no major, or the 559 conflicting groups?"
- "Where should the compliance boundary sit — in the repository, in the
  operator's deployment, or both?"
- "The demo uses a fictional province. Would you rather it use a real province
  with obviously fake institutions, accepting the misreading risk?"

## 6. What not to claim

- Do not claim the system is production-ready or legally cleared. It is
  `PUBLIC_RELEASE_BLOCKED`.
- Do not claim the dataset is complete or authoritative. It is measured and
  incomplete, and the report says so.
- Do not claim the container build was verified on the CI runner. It was
  verified locally, partly through an offline wheelhouse.
- Do not quote a data metric without re-running the command that produced it.
