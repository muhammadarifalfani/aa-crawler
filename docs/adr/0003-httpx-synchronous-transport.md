# ADR-003 — HTTPX as the Synchronous Transport Boundary

- Status: Accepted
- Date: 2026-08-04
- Decision owners: Tech Lead, HTTP owner
- Related ADRs: ADR-004, ADR-005, ADR-015, ADR-019

## Context

Crawler components require reusable synchronous HTTP while domain contracts
must remain independent of transport response objects.

## Decision drivers

- Reusable connections and explicit timeout support
- Structured exceptions and mock transport
- Python 3.12 compatibility
- Isolation of third-party transport types

## Considered options

1. `urllib.request`.
2. `requests`.
3. HTTPX behind a project client and adapters.
4. A custom universal transport abstraction before selecting a client.

## Decision

Use HTTPX behind `HttpClient`. Convert crawler contracts and HTTPX objects in
dedicated adapters and translate HTTPX failures into crawler-domain errors.

## Rationale

HTTPX supplies the approved synchronous capabilities with a small dependency
footprint and strong isolated-testing support.

## Consequences

### Positive

- Crawler request and response contracts remain transport-neutral.
- The client is reusable and testable without network access.

### Negative

- Some HTTP package signatures expose HTTPX transport and timeout types.
- Replacing HTTPX is not cost-free.

### Neutral

- The application runtime remains synchronous.

## Compatibility implications

The `HttpClient` constructor, `send()` behavior, and HTTPX-facing policy method
are compatibility-sensitive.

## Follow-up work

Review third-party type exposure before a stable external API.

## Review triggers

Async execution, browser acquisition, streaming, or transport replacement.
