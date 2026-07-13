# Community release checklist

This checklist prepares a local candidate. It does not authorize a push, tag,
GitHub Release, package publication, announcement, or destructive history rewrite.

## 1. Candidate identity

- [ ] `python scripts/check_docs.py` reports one version across Python, frontend and OpenAPI manifests.
- [ ] `CHANGELOG.md` describes features, security fixes, experiments, limitations and data responsibility.
- [ ] The candidate commit and generated archive SHA-256 are recorded in `docs/open-source-readiness.md`.

## 2. Repository and rights boundary

- [ ] `bash scripts/audit_open_source.sh --release --history --require-gitleaks` passes.
- [ ] Every tracked data/content/visual asset is classified in `config/open_source_assets.tsv`.
- [ ] No asset classified `exclude` is present in the candidate archive.
- [ ] License, data, third-party, trademark, privacy, security and support policies are linked from README.
- [ ] Maintainer has reviewed any dependency license that the automated policy does not recognize.

## 3. Reproducible verification

- [ ] Create a clean archive or clone from the candidate commit; do not test only the dirty working tree.
- [ ] Run Ruff check/format and the complete Python test suite with the configured coverage floor.
- [ ] Run `pip-audit --strict --requirement requirements.lock`.
- [ ] Run frontend `npm ci`, tests, production build and moderate-level audit using Node.js 20.
- [ ] Start the no-key Docker demo; verify API health, frontend HTTP response, synthetic seed counts and SSE disclosure.
- [ ] Run documentation, dependency-license and open-source repository checks.

## 4. Human governance review

- [ ] Confirm demo output says synthetic, non-official and unsuitable for real admission decisions.
- [ ] Confirm numeric recommendations expose source and year or say they cannot be verified.
- [ ] Confirm logs, reports and errors do not disclose session credentials or applicant details by default.
- [ ] Confirm official examination-authority and university verification paths are visible.
- [ ] Review the final staged diff and archive file list manually.

## 5. Explicit publication authorization

- [ ] Show the maintainer the final commit, archive checksum, gate results, known limitations and remaining risks.
- [ ] Obtain explicit authorization for each intended external action: push, tag, GitHub Release, package publish or announcement.
- [ ] If complete-history secret scanning finds a real secret, obtain separate explicit approval before any history rewrite or force push.

Without the final authorization above, stop after producing the local candidate and evidence report.
