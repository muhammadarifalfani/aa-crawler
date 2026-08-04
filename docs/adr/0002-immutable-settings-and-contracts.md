# ADR-002 — Immutable Settings and Domain Contracts

- Status: Accepted
- Date: 2026-08-04
- Decision owners: Tech Lead, Domain owners
- Related ADRs: ADR-001, ADR-017

## Context

Settings, crawler contracts, HTML documents, and transport policies pass through
multiple components and must not change unexpectedly after validation.

## Decision drivers

- Predictable dependency injection
- Clear ownership of caller-provided mappings
- Reduced shared-state defects
- Simple equality and isolation tests

## Considered options

1. Mutable dictionaries and classes.
2. Frozen models without copying inputs.
3. Frozen models with defensive top-level copies.
4. Recursively immutable and serializable value trees.

## Decision

Use frozen Pydantic models and frozen, slotted dataclasses. Defensively copy
mapping inputs and expose immutable top-level mappings. Recursive immutability
and serialization are not promised.

## Rationale

Top-level immutability provides strong in-process safety without prematurely
restricting platform metadata and extracted item values.

## Consequences

### Positive

- Values remain stable through runtime pipelines.
- Caller-owned mappings cannot mutate exposed top-level state.

### Negative

- Nested values may remain mutable or non-serializable.

### Neutral

- Updating settings requires constructing a replacement model.

## Compatibility implications

Later narrowing of metadata or item values may be breaking.

## Follow-up work

Document shallow immutability and govern portability through ADR-017.

## Review triggers

Persistence, public plugins, distributed workers, or stable platform schemas.
