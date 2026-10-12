# Security Policy

## Reporting

Please **do not** open a public issue for a vulnerability. Use GitHub's
private vulnerability reporting ("Security" → "Report a vulnerability") on this
repository. If that is unavailable, contact the maintainer privately first.

Please do not include real personal data, working credentials, or exploit
payloads against any third-party system in a report.

## Threat model of this demo

This repository is a **demonstration**, not a production service. Its security
posture is scoped accordingly.

Protected:
- Session identity (server-issued ids, HMAC-bound bearer tokens)
- Prompt-injection detection on user input
- Output boundary rules (no fabricated data, source marking)
- Absence of real data and credentials

Explicitly **not** claimed:
- No account system, no authentication of humans, no authorization model
- No rate limiting that survives a determined attacker at scale
- No availability or durability guarantees
- No multi-tenant isolation guarantees

## Running it safely

- Set a strong, random `SESSION_SECRET` for anything beyond a local demo.
  Without it a fresh secret is generated per process, which invalidates tokens
  across restarts and workers.
- `SESSION_SECRET` is a bearer-authority secret. Anyone holding it plus a
  session id can mint that session's token.
- Do not expose this service to the public internet as-is. There is no
  multi-tenant isolation and the dataset is synthetic anyway.
