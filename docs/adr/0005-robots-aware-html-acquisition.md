# ADR-005 — Robots-Aware HTML Acquisition

- Status: Accepted
- Date: 2026-08-04
- Decision owners: Robots owner, HTML owner
- Related ADRs: ADR-003, ADR-014, ADR-019

## Context

HTML acquisition requires robots compliance, transport execution, response
validation, and deterministic decoding without duplicating those concerns in
each crawler or parser.

## Decision drivers

- One robots authority and one transport boundary
- Deterministic status, media-type, and decoding behavior
- Reusable acquisition components
- Safe error translation

## Considered options

1. Implement robots and decoding in every crawler.
2. Put robots behavior inside `HttpClient`.
3. Use one combined transport/parser object.
4. Separate `RobotsPolicy`, `HttpClient`, and `HtmlFetcher`.

## Decision

`RobotsPolicy` is the only robots decision boundary. `HttpClient` remains the
only transport boundary. `HtmlFetcher` performs robots-aware page acquisition,
successful-status and HTML media-type checks, strict decoding, and immutable
`HtmlDocument` construction. DOM parsing remains outside acquisition.

## Rationale

The separation preserves single responsibilities and prevents platform
crawlers from reimplementing compliance and decoding policy.

## Consequences

### Positive

- Reusable robots and HTML behavior.
- Parsers receive deterministic decoded documents.

### Negative

- Several domain error families may propagate.
- User-agent ownership is currently duplicated.

### Neutral

- The complete response is buffered in memory.

## Compatibility implications

Robots status rules, media types, and strict decoding are public behavior.

## Follow-up work

Resolve identity ownership in ADR-014 and document the complete error surface.

## Review triggers

Browser automation, alternate media, streaming, or long-lived robots caching.
