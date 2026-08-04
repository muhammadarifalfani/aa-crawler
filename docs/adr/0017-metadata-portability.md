# ADR-017 — Metadata and Item Portability

- Status: Deferred
- Date: 2026-08-04
- Decision owners: Domain owner
- Related ADRs: ADR-002, ADR-007, ADR-011

## Context

Request, response, document, and item mappings accept `object` values. Their
top-level mappings are immutable, but nested values may be mutable and
non-serializable.

## Decision drivers

- Current platform flexibility
- Future persistence and schemas
- Plugin interoperability
- Distributed execution

## Considered options

1. Retain arbitrary objects permanently.
2. Restrict values to JSON-compatible data.
3. Require typed platform models.
4. Separate internal context from portable metadata.
5. Introduce versioned schema envelopes.

## Decision

Defer the portability policy until a real portability requirement exists.
Current mappings are approved only for trusted in-process communication and do
not promise recursive immutability or serialization.

## Rationale

Selecting a universal schema without real platform and storage requirements
would be premature.

## Consequences

### Positive

- Platform experimentation remains low-friction.

### Negative

- Cross-process portability is not guaranteed.

### Neutral

- Top-level defensive copying remains mandatory.

## Compatibility implications

Future narrowing may require migration or versioned contracts.

## Follow-up work

Document current limits and avoid claiming distributed compatibility.

## Review triggers

Persistence, public plugins, queues, workers, or stable item schemas.
