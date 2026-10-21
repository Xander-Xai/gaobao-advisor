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

## Dependency policy

The **runtime** dependency set (`requirements.txt` → `requirements.lock`) must
have **zero known vulnerabilities**. CI enforces this with `pip-audit`; the
job is a hard gate and a red `Security Audit` means the runtime set is not
acceptable to ship.

Optional tooling that is not part of the runtime lives in its own file
(`requirements-legacy-admin.txt` → `requirements-legacy-admin.lock`), is never
installed by default, never enters the container image and is audited
separately against an explicit, recorded exception list.

The reviewed version pins live in `requirements.lock.constraints`, and the
current state of the policy — including every exception, its rationale and the
open decisions — is documented in
[`docs/dependency-exceptions.md`](docs/dependency-exceptions.md). Regenerate
the lock with `make lock`; do not hand-edit it and do not re-resolve it
without the constraints file.

Report a vulnerable dependency the same way as any other issue: privately, not
in a public issue or pull request.
