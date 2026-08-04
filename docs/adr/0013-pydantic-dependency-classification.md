# ADR-013 — Pydantic Dependency Classification

- Status: Accepted
- Date: 2026-08-04
- Decision owners: Tech Lead, Dependency owner
- Related ADRs: ADR-001, ADR-002

## Context

The project declares `pydantic-settings`, but production code also imports
Pydantic directly and public settings models expose Pydantic behavior.

## Decision drivers

- Accurate dependency metadata
- Explicit compatibility ownership
- Reproducible dependency upgrades
- Honest public API documentation

## Considered options

1. Keep Pydantic transitive while importing it directly.
2. Declare Pydantic as a direct production dependency.
3. Remove direct Pydantic use.
4. Replace public settings with non-Pydantic models.

## Decision

Treat Pydantic as a strategic direct production dependency. Dependency metadata
must declare it directly with an approved range. The metadata and lockfile
change will occur in a separate dependency pull request; this documentation
decision does not modify dependencies.

## Rationale

Transitive availability is not a sufficient declaration for a library imported
directly and exposed through public model behavior.

## Consequences

### Positive

- Project metadata will reflect actual production coupling.
- Pydantic upgrades become explicit review events.

### Negative

- The direct runtime dependency count increases.
- Version compatibility must be coordinated with Pydantic Settings.

### Neutral

- The resolved environment may remain unchanged when metadata is corrected.

## Compatibility implications

Pydantic construction, validation errors, serialization, and frozen-model
behavior are acknowledged compatibility concerns.

## Follow-up work

Create a separate dependency PR updating `pyproject.toml` and `uv.lock` only.

## Review triggers

Any Pydantic or Pydantic Settings upgrade or public settings redesign.
