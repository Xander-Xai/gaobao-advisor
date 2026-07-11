# Open-source readiness

Status date: 2026-07-11

This document is the evidence ledger for preparing the community developer
edition. A checked item means that current commands or files prove the claim;
historical reports are not sufficient evidence.

## Release boundary

- Current implementation branch: `codex/open-source-readiness`.
- The existing private repository history remains intact.
- The public candidate will be produced as a clean mirror after local gates
  pass. Rewriting the existing repository history is not automatic.
- Creating a remote repository, pushing, making it public, publishing images,
  or creating a release requires final user authorization.
- The working tree contained pre-existing uncommitted development work when
  this effort began. Open-source commits stage only explicitly reviewed files.

## Reproducible audit

Run the local structural audit:

```bash
bash scripts/audit_open_source.sh
```

Run the release audit with complete-history secret scanning:

```bash
bash scripts/audit_open_source.sh --history --require-gitleaks
```

The second command is a release gate. A machine without Gitleaks cannot mark
the secret-scanning requirement as passed; CI provides the same gate.

## Initial high-risk inventory

| Category | Current evidence | Risk | Disposition |
| --- | --- | --- | --- |
| Database | `data/gaokao.db.corrupted` was tracked at about 86 MB | Unknown contents, repository bloat | Remove from public candidate; keep local file until owner confirms disposal |
| Backups | Two tracked SQL gzip archives under `backups/` | May contain licensed data or personal information | Remove from public candidate; do not publish |
| Reports | 34 tracked report JSON files and additional local generated reports | May contain profiles, conversation-derived content or session identifiers | Remove from public candidate and ignore the entire runtime directory |
| Local agent state | A tracked `.claude/worktrees/` gitlink | Couples the repository to a local worktree and may expose tool state | Remove from public candidate; preserve the local worktree |
| Secrets | Configuration examples plus repository history | Deleted credentials may remain in history | Scan working tree and complete history with Gitleaks; rotate any confirmed credential |
| Knowledge content | `knowledge/`, quote collections and prompts | Third-party text may not inherit the MIT code license | Classify in `THIRD_PARTY_NOTICES.md` before release |
| Data adapters | Baidu and other external data integrations | API access does not imply redistribution rights | Publish adapters only until data rights are documented |
| Branding | gaobao and references to third-party personalities | Risk of implied endorsement | Add an explicit trademark and non-affiliation statement |

## Asset classes

- **Code:** Python, Vue, configuration loaders, tests and deployment tooling.
- **Data:** databases, JSON/CSV datasets, embeddings and imported source data.
- **Content:** prompts, knowledge articles, quotes, images and marketing copy.
- **Runtime artifacts:** reports, logs, sessions, caches, test output and local
  monitoring state.
- **Restricted assets:** production data, backups, personal information,
  credentials, and material without a confirmed redistribution basis.

## Checkpoint A: release baseline

- [x] Reproducible asset and risk audit is available.
- [x] Public candidate and private-history boundaries are documented.
- [x] No history rewrite or remote publication was performed.

## Checkpoint B: repository hygiene and secret safety

- [x] Runtime artifacts are ignored by Git and Docker contexts.
- [x] Restricted and oversized artifacts are not tracked in the public candidate.
- [x] Working-tree Gitleaks scan passes: Gitleaks v8.30.1 scanned the 5.11 MB
  non-ignored candidate on 2026-07-11 and found no leaks.
- [x] Complete-history Gitleaks scan passes: 366 commits and 11.63 MB were
  scanned on 2026-07-11 with no leaks after the exact placeholder dispositions
  below. Every future finding must have a documented,
  reviewed disposition and any exposed credential has been rotated.

### Secret scan dispositions

- The two documented Slack webhook examples use literal `YOUR/WEBHOOK/URL` or
  `T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX` placeholder segments. Only
  those exact values are allowlisted.
- `Bearer YOUR_TOKEN` is an exact API documentation placeholder. Only that
  exact value is allowlisted.

### Local preservation evidence

- The two SQL archives and corrupted database remained on disk after being
  removed from the Git index; all three SHA-256 checks passed.
- All 207 local report files remained on disk and passed their SHA-256 checks.
- The local `.claude/worktrees/` directory remained present after its gitlink
  was removed from the Git index.

## Remaining release gates

- [x] Code, data, content, third-party and brand rights are classified in
  `config/open_source_assets.tsv` and the root policy documents. Assets marked
  `exclude` still need to be omitted from the final public archive.
- [x] Security, privacy, support and community governance documents are complete.
- [ ] README links to every policy document; this remains part of the planned
  README reconciliation because the file has pre-existing uncommitted changes.
- [ ] No-key demo configuration and synthetic sample data are verified.
- [ ] Backend, frontend, container and supply-chain CI gates pass.
- [ ] README and release documentation match the verified implementation.
- [ ] High-stakes education output and privacy controls pass their fixed tests.
- [ ] A clean candidate copy passes every completion criterion in the design.

## Checkpoint C: rights and governance

- [x] Tracked data, content and visual assets have an automated classification.
- [x] Data licensing, provenance, third-party and non-affiliation boundaries are
  documented without extending MIT to third-party assets.
- [x] Security, privacy, support, conduct, ownership and changelog files exist.
- [x] Public issue and pull-request templates warn against secrets and personal
  data and require provenance for new data contributions.
- [ ] README policy links are pending Task 14; Checkpoint C is otherwise ready.

## Current quality blockers

- `ruff check .` currently reports 19 errors in pre-existing uncommitted MCP,
  report, route, service, slot and test changes. The governance files do not
  introduce Python lint failures. Checkpoint E remains blocked until Task 12-13
  fixes or reconciles these files and reruns the full command.
