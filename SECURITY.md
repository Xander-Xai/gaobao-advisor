# Security policy

## Supported versions

Until the first community release is published, security fixes target the
latest commit on the default branch and the local `3.1.x` community candidate.
After releases begin, this section will be updated with the supported release series.

## Report a vulnerability privately

Do not open a public issue for vulnerabilities, credentials, private prompts,
database contents, applicant information, conversation logs or report files.

Use GitHub's private vulnerability reporting form:

<https://github.com/yandexuanxuan/gaobao-advisor/security/advisories/new>

Include the affected commit or version, impact, minimal reproduction and a safe
way to validate the fix. Redact tokens and personal information. Do not attach
production databases or exploit unrelated systems.

The maintainers aim to acknowledge a report within 7 days and provide a triage
decision within 14 days. These are community targets, not a service-level
agreement.

## Scope priorities

High-priority reports include authentication or authorization bypass, remote
code execution, path traversal, prompt or retrieval injection that exposes
private data, cross-user report access, secret leakage, unsafe default
credentials, and dependency vulnerabilities with a reachable exploit path.

General admission-data corrections and model-quality disagreements are not
security vulnerabilities unless they demonstrate integrity compromise or
targeted manipulation. Use the normal issue templates for those reports.

## Safe research expectations

- Test only systems and data you own or are authorized to use.
- Stop if testing exposes another person's information.
- Do not persist, publish or redistribute exposed data.
- Give maintainers reasonable time to address a confirmed issue before public
  disclosure.

No bug bounty or payment programme is currently offered.
