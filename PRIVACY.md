# Privacy

## What this demo stores

The running application writes only local runtime state:

* `data/demo.db` — the generated synthetic database;
* `data/reports/<session_id>/*.json` — conversation reports, when the report
  feature is used.

Both paths are gitignored and are not committed. The container generates the
database on start; `docker compose down -v` removes the demo volume.

## Historical exposure

A database file removed from the current tree remains reachable through an
older public Git object. The current tree contains no real admissions database
and no user messages. The open remediation record, the redacted forensic
summary and the owner-authorisation boundary are tracked in
[Issue #58](https://github.com/Xander-Xai/gaobao-advisor/issues/58) and
[SECURITY.md](SECURITY.md). Deleting a file from `master` is not a history
purge; this repository does not claim otherwise.

## No telemetry

No Sentry DSN, analytics endpoint or telemetry key ships with the repository.
The test suite only initialises Sentry when a developer explicitly configures
`SENTRY_DSN` in their own environment; CI does not.

## Session tokens

A session token is an HMAC of the session ID under `SESSION_SECRET`. It is a
capability over exactly one anonymous session, not an account. It contains no
profile data. Multi-worker deployments must set an explicit `SESSION_SECRET`.

## Not a production privacy notice

The default deployment handles synthetic data only. Anyone deploying this
software with real users must replace this document with their own privacy
notice and data-processing agreements before doing so.
