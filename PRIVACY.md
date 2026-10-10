# Privacy notice for self-hosted deployments

> **Status: draft pending review.** This document describes the repository
> defaults and is written for the operator of a deployment. It has not been
> reviewed against the law of any specific jurisdiction and it does not record a
> retention period. Treat it as a starting point for a review you perform, not
> as an approved privacy notice. See
> `docs/finalization/SECURITY_AND_LICENSE_BLOCKERS.md` for the open items.

gaobao-advisor is self-hosted software. The person or organization operating a
deployment controls its configuration and is responsible for providing an
appropriate user-facing privacy notice and complying with applicable rules.
This document describes the repository defaults; it is not legal advice.

## Data processed by the application

Depending on enabled features, the application can process:

- session identifiers and conversation messages;
- province, score or rank, subject selection, interests and intended majors;
- generated recommendation reports;
- structured analytics events and feature usage;
- audio sent to speech recognition or synthesis providers;
- prompts and retrieved context sent to a configured model provider.

Do not request or enter a real name, national identifier, phone number, exact
address, account credential or other unnecessary identifying information. This
is particularly important when the user may be a minor.

## Default local storage

- Conversations and profiles may be stored in the configured SQLite database.
- Reports are JSON files under the configured reports directory; the default is
  `data/reports/`.
- Analytics events may be stored in a separate SQLite database and contain a
  session identifier, event type and shortened structured event data.
- Logs and monitoring systems may retain request or error context according to
  operator configuration.

These local stores are not encrypted by the application at rest. Operators
should use filesystem access controls, encrypted storage, backups with limited
access and a documented retention period.

## Third-party processing

When a remote LLM, embedding, search, speech, monitoring or error-reporting
provider is enabled, relevant input is sent to that provider. Review the
provider's terms, region, retention and training settings before enabling it.
The community demo must keep optional remote services disabled by default.

## Retention and deletion

The repository does not impose a universal retention period. Operators should
choose the shortest period required for their use case. Deleting a user's data
may require removing the corresponding database rows, report directory,
analytics events, logs and backups. Removing a live file does not remove copies
from backups.

## Public issue hygiene

Never submit conversation transcripts, API keys, session tokens, report JSON,
database files or identifiable applicant profiles in a public issue. Use
synthetic values and redact screenshots. Sensitive incidents belong in the
private process described by `SECURITY.md`.
