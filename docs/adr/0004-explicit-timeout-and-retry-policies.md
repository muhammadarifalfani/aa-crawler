# ADR-004 — Explicit Timeout and Retry Policies

- Status: Accepted
- Date: 2026-08-04
- Decision owners: HTTP owner
- Related ADRs: ADR-003, ADR-015

## Context

Transport policy must be explicit and must not turn crawler metadata into an
implicit configuration channel.

## Decision drivers

- Visible, deterministic transport behavior
- Immutable and reusable policy values
- Request-metadata neutrality
- Focused policy tests

## Considered options

1. Read timeout and retry values from request metadata.
2. Use hidden module constants.
3. Use mutable client attributes.
4. Inject frozen policy objects.

## Decision

Use frozen `TimeoutPolicy` and `RetryPolicy` objects. Attempts include the
initial request; no sleep occurs before attempt one. Backoff is deterministic,
exponential, and capped. Rebuild requests between attempts. Do not add jitter
or per-request metadata policy at this stage.

## Rationale

Dedicated policy objects make operational behavior explicit without weakening
domain metadata semantics.

## Consequences

### Positive

- Predictable retries and straightforward testing.
- Timeout and retry settings cannot hide in metadata.

### Negative

- Policies currently apply at client scope.
- Method idempotency remains unresolved.

### Neutral

- Jitter and distributed retry ownership remain deferred.

## Compatibility implications

Attempt counting, retry eligibility, and backoff calculations are observable.

## Follow-up work

Resolve non-idempotent request rules through ADR-015.

## Review triggers

Non-GET methods, `Retry-After`, jitter, cancellation, or distributed workers.
