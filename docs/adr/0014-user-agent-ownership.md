# ADR-014 — User-Agent Ownership

- Status: Proposed
- Date: 2026-08-04
- Decision owners: Robots owner, HTTP owner
- Related ADRs: ADR-005, ADR-008

## Context

`RobotsPolicy` and `HtmlFetcher` independently receive user-agent strings, and
the robots retrieval request does not currently use the configured crawler
identity as its request header.

## Decision drivers

- Robots compliance
- Consistent crawler identity
- Platform-specific configuration
- One source of truth

## Considered options

1. Preserve independent values.
2. Let `HtmlFetcher` own and pass identity.
3. Let `RobotsPolicy` own identity.
4. Inject one immutable request-identity value into both.
5. Apply a global default in `HttpClient`.

## Decision

No ownership model is approved yet. The final decision must ensure robots
evaluation, robots retrieval, and page retrieval use one authoritative identity
unless an explicit, documented exception exists.

## Rationale

Independent values create correctness and compliance risk.

## Consequences

### Positive

- The proposal exposes the inconsistency before platform adoption.

### Negative

- Resolving it may change constructors and headers.

### Neutral

- Platform-specific identity remains possible under any option.

## Compatibility implications

Public constructor and request-header behavior may change.

## Follow-up work

Approve one owner, implement the invariant, and add end-to-end identity tests.

## Review triggers

Before the first production crawler or any user-agent rotation feature.
