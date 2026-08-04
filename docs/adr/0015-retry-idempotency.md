# ADR-015 — Retry Idempotency

- Status: Proposed
- Date: 2026-08-04
- Decision owners: HTTP owner
- Related ADRs: ADR-003, ADR-004

## Context

Current retry decisions use transient exceptions and statuses without accounting
for whether repeating the HTTP method is safe.

## Decision drivers

- Prevent duplicated mutations
- Predictable client behavior
- Explicit caller responsibility
- Future non-GET support

## Considered options

1. Retry every method.
2. Retry only GET and HEAD.
3. Retry recognized idempotent methods.
4. Require an explicit idempotency declaration or key.
5. Disable retries for requests with bodies.

## Decision

No rule is approved yet. Existing behavior is authorized only for the current
GET-oriented framework and must not be interpreted as approval for mutation
retries.

## Rationale

Transport failures cannot determine application-level operation safety.

## Consequences

### Positive

- Current GET behavior remains usable while risk is explicit.

### Negative

- Non-GET support remains blocked on a policy decision.

### Neutral

- Jitter and distributed retry ownership are separate decisions.

## Compatibility implications

Changing retry eligibility is observable behavior and may affect request counts.

## Follow-up work

Approve method rules and add focused tests before non-GET requests are allowed.

## Review triggers

POST, PUT, PATCH, DELETE, idempotency keys, or distributed workers.
