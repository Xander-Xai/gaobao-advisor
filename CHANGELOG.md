# Changelog

All notable changes to gaobao-advisor are documented here. The format follows
Keep a Changelog and the project uses semantic versioning for public releases.

## [Unreleased]

## [3.1.0] - 2026-07-13

### Added

- Open-source community edition design and implementation plan.
- Repository audit, secret-scanning gate and public-candidate boundaries.
- Data, third-party, trademark, security, privacy and support policies.
- No-key offline demo provider and a CC0 synthetic seed dataset.
- Required frontend, dependency-license, documentation and container CI gates.
- Source/year enforcement and privacy-safe operational log references.

### Changed

- Runtime reports, database backups and local agent state are excluded from the
  public source candidate.
- RAG, voice and network search are disabled in the default community setup.
- Concrete recommendations expose provenance status and official verification paths.

### Security

- Gitleaks scans the complete Git history in CI.
- DOMPurify and LangSmith were raised above known vulnerable versions.

### Known limitations

- The public distribution does not include real admission data or the internal knowledge corpus.
- RAG, MCP, quality scoring and monitoring remain experimental.
- The real-time voice path requires an independently configured ASR/TTS service.
- Version 3.1.0 is a local release candidate until a maintainer explicitly authorizes publishing.

## [3.0.0] - 2026-06-17

### Added

- FastAPI and Vue application baseline with RAG, report and profile modules.

[Unreleased]: https://github.com/yandexuanxuan/gaobao-advisor/compare/v3.1.0...HEAD
[3.1.0]: https://github.com/yandexuanxuan/gaobao-advisor/compare/v3.0.0...v3.1.0
[3.0.0]: https://github.com/yandexuanxuan/gaobao-advisor/releases/tag/v3.0.0
