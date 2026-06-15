# ADR-006: Architecture Decision Record Process

**Status:** Accepted (implemented)
**Date:** 2026-06

## Context
The project accumulated multiple architectural changes without documented rationale.
New contributors (and AI agents) need context about why decisions were made.

## Decision
Record significant architecture decisions as ADRs in `docs/superpowers/adr/`.
Each ADR follows the template: Context → Decision → Consequences → Related ADRs.

## Template
```markdown
# ADR-NNN: Title

**Status:** [Proposed | Accepted | Deprecated | Superseded]
**Date:** YYYY-MM

## Context
[Problem description, constraints, alternatives considered]

## Decision
[What was chosen and why]

## Consequences
[+ Positive, - Negative, and Neutral implications]

## Related
[Links to other ADRs]
```

## Consequences
+ Lightweight process — no bureaucracy overhead
+ Provides context for both humans and AI agents
+ Each ADR is a standalone file — easy to reference
- Requires discipline to write before/after significant changes