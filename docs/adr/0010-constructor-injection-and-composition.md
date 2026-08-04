# ADR-010 — Constructor Injection and Explicit Composition Ownership

- Status: Accepted
- Date: 2026-08-04
- Decision owners: Tech Lead
- Related ADRs: ADR-001, ADR-003, ADR-008, ADR-011

## Context

Configuration and crawler services require explicit ownership and testable
lifetimes without global registries or hidden environment reads.

## Decision drivers

- Visible dependencies and lifetimes
- Deterministic tests
- No global settings or service locator
- Replaceable collaborators

## Considered options

1. Module-level singletons.
2. Global factories.
3. A service-locator or dependency-injection framework.
4. Constructor injection from explicit composition roots.

## Decision

Load one settings instance at the application composition root and inject it or
narrower collaborators. Runtime services use constructor injection. Modules do
not create global settings, clients, or registries.

## Rationale

Explicit object graphs keep ownership understandable and tests isolated without
adding a framework dependency.

## Consequences

### Positive

- Dependencies and object reuse are visible.
- Tests can supply deterministic collaborators.

### Negative

- Manual construction becomes verbose as the graph grows.
- Crawler runtime composition is not yet owned by bootstrap.

### Neutral

- No dependency-injection framework is selected.

## Compatibility implications

Constructor parameters form part of the public compatibility surface.

## Follow-up work

Extend composition ownership when a runnable platform crawler is introduced.

## Review triggers

Material object-graph growth, worker lifecycles, or plugin loading.
