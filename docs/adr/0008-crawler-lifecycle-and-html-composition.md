# ADR-008 — Crawler Lifecycle and Generic HTML Composition

- Status: Accepted
- Date: 2026-08-04
- Decision owners: Crawler owner
- Related ADRs: ADR-003, ADR-005, ADR-007, ADR-011, ADR-014

## Context

The synchronous runtime needs one ordered lazy crawl loop while allowing HTML
acquisition to specialize processing without duplicating that loop.

## Decision drivers

- Sequential, lazy, order-preserving execution
- Reused dependencies
- No duplicated transport, robots, or parser validation
- A narrow specialization seam

## Considered options

1. Duplicate the loop in every crawler.
2. Require every crawler to parse raw responses.
3. Introduce middleware before a real requirement.
4. Use a template lifecycle with protected request processing.

## Decision

`BaseCrawler.crawl()` owns initial-request iteration and item yielding. The
default `_process_request()` sends through `HttpClient` and calls `parse()`.
Specialized crawlers may override the protected seam. `HtmlCrawler` delegates
to `HtmlFetcher` and `BaseParser` and performs exactly one page transport
request per configured URL.

## Rationale

The seam preserves one lifecycle without prematurely introducing middleware or
scheduling abstractions.

## Consequences

### Positive

- One reusable ordered crawl loop.
- Specialized HTML composition remains small.

### Negative

- Two effective subclassing styles exist.
- `HtmlCrawler` retains a base client it does not directly use.
- An orchestration request and a transport request represent one operation.

### Neutral

- Follow-up requests and concurrency remain out of scope.

## Compatibility implications

`crawl()`, `parse()`, and `_process_request()` are compatibility-sensitive.

## Follow-up work

Validate the lifecycle and request ownership through the first platform crawler.

## Review triggers

Platform composition, recursive requests, concurrency, middleware, or scheduler
integration.
