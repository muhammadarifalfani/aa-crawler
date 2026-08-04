# ADR-018 — Error-Root Taxonomy

- Status: Deferred
- Date: 2026-08-04
- Decision owners: Tech Lead
- Related ADRs: ADR-011

## Context

Configuration failures derive from `AACrawlerError`, while crawler-domain
failures derive from an unrelated `CrawlerError`.

## Decision drivers

- Clear bounded contexts
- Application-wide supervision
- Public exception compatibility
- Safe operational failure handling

## Considered options

1. Preserve independent roots.
2. Make `CrawlerError` derive from `AACrawlerError`.
3. Introduce a new universal root.
4. Keep roots separate and define an application orchestration boundary.

## Decision

Defer until an application-wide catch boundary is required or before version
1.0. Existing package-specific roots remain supported in the meantime.

## Rationale

The split causes little present harm, while exception inheritance changes can
silently alter caller control flow.

## Consequences

### Positive

- Avoids premature hierarchy migration.

### Negative

- There is no single project-wide catch today.

### Neutral

- Subsystem-specific catches remain clear.

## Compatibility implications

Any inheritance change requires explicit compatibility review.

## Follow-up work

Document both roots and revisit before stable API.

## Review triggers

CLI failure handling, worker supervision, public SDK adoption, or version 1.0.
