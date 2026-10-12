# Privacy

## What this demo stores

The service writes only what the running application produces locally:

* `data/demo.db` — the generated synthetic database
* `data/reports/<session_id>/*.json` — conversation reports, when the report
  feature is used

Both paths are gitignored and neither is committed. The container generates the
database on start and discards it with the container.

## No telemetry

The repository's test suite emits Sentry events only when a developer has
`SENTRY_DSN` configured in their own environment; no DSN is shipped and CI does
not configure one.

## Session tokens

A session token is an HMAC of the session id under `SESSION_SECRET`. It is
returned to the client in the chat response and is not a user account. It grants
capability over exactly one session and nothing else.

## Not a production privacy notice

This deployment handles no real personal data because it has no real data.
Anyone deploying it with real users must replace this document with their own
notice before doing so.
