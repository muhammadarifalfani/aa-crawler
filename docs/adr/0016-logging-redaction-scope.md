# ADR-016 — Logging Redaction Scope

- Status: Proposed
- Date: 2026-08-04
- Decision owners: Observability owner, Security owner
- Related ADRs: ADR-010

## Context

Sensitive-data filters are attached to AA Crawler-owned handlers. Unrelated
handlers are preserved and may process the shared `LogRecord` before an owned
handler redacts it. Owned filters also mutate that shared record.

## Decision drivers

- Prevent secret leakage
- Preserve predictable handler behavior
- Retain unrelated handlers where safe
- Define a testable security guarantee

## Considered options

1. Guarantee redaction only on owned outputs.
2. Apply redaction at logger level.
3. Copy records per handler.
4. Prohibit unrelated handlers on the application logger.
5. Treat filters only as defense-in-depth and prohibit sensitive log inputs.

## Decision

No guarantee is approved yet. The final decision must state whether redaction
is an owned-output guarantee, a logger-wide guarantee, or defense-in-depth only.

## Rationale

Handler ordering makes the current broad security interpretation ambiguous.

## Consequences

### Positive

- The security boundary becomes explicit and testable.

### Negative

- A stronger guarantee may constrain third-party handlers.

### Neutral

- Comprehensive PII detection remains out of scope.

## Compatibility implications

Third-party logging integrations may observe different record behavior.

## Follow-up work

Approve the guarantee and test unrelated handlers before and after owned ones.

## Review triggers

Before platform code logs headers, cookies, credentials, or response context.
