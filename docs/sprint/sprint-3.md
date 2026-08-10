# Sprint 3 — Synchronous Crawler Foundation

## Objective

Establish a reusable synchronous crawler foundation built on the approved
Sprint 2 configuration and observability baseline.

## Completed work

- Core crawler contracts and crawler error hierarchy
- HTTPX dependency and synchronous `HttpClient`
- Explicit `TimeoutPolicy` and `RetryPolicy`
- Synchronous `BaseCrawler` runtime
- Reusable `RobotsPolicy`
- Immutable `HtmlDocument` and strict `HtmlFetcher`
- Lazy `BaseParser` framework
- Generic `HtmlCrawler`
- Sprint 2 and Sprint 3 ADR library
- Post-Sprint architecture, API, dependency, technical-debt, and quality reviews

## Task inventory

- Task 3.1 — Core domain contracts
- Task 3.2a — HTTPX dependency
- Task 3.2b — Synchronous HTTP client
- Task 3.3 — Timeout and retry policies
- Task 3.4 — BaseCrawler runtime
- Task 3.5 — Robots policy
- Task 3.6 — HTML fetcher
- Task 3.7 — Parser framework
- Task 3.8 — Generic HTML crawler

## Architecture delivered

```text
Configured URLs
    → BaseCrawler / HtmlCrawler
    → HtmlFetcher
    → RobotsPolicy
    → HttpClient
    → HtmlDocument
    → BaseParser
    → CrawlerItem
```

Execution is synchronous. Request processing and parsing are lazy, preserve
order, and stop at the first failure. `HtmlCrawler` performs exactly one page
transport request per configured URL after the robots decision. Dependencies
are constructor-injected, and imports perform neither bootstrap nor network
execution.

## Key decisions

- Crawler contracts are immutable and slotted.
- Mapping inputs receive defensive top-level copies.
- HTTPX is isolated behind `HttpClient`.
- Timeout and retry policies are explicit; metadata never controls transport.
- `RobotsPolicy` is the robots authority.
- HTML validation and decoding are deterministic and strict.
- `BaseParser` validates every yielded result as a `CrawlerItem`.
- `_process_request` is the protected crawler specialization seam.
- Sprint 4 uses a partial API freeze under ADR-011.
- ADR-013 classifies Pydantic as a future direct dependency declaration; the
  metadata change remains separate and is not implemented by Sprint 3.
  **Resolved in Sprint 4:** Pydantic was declared directly in PR #22.
- Proposed ADR decisions remain unresolved and are not implemented policy.

## Pull requests

- PR #11 — `feat(crawler): add core domain contracts`
- PR #12 — `chore(deps): add httpx`
- PR #13 — `feat(http): add synchronous HTTP client foundation`
- PR #14 — `feat(http): add timeout and retry policies`
- PR #15 — `feat(crawler): add base crawler runtime`
- PR #16 — `feat(robots): add robots policy`
- PR #17 — `feat(html): add HTML fetcher`
- PR #18 — `feat(parser): add parser framework`
- PR #19 — `feat(crawler): add generic HTML crawler`
- PR #20 — `docs(architecture): add Sprint 3 ADR library`

## Verification

The final implementation baseline at Task 3.8 passed:

- Ruff lint
- Ruff formatting
- mypy
- pre-commit
- Full pytest: 304 passed
- Coverage: 96.69%, above the 70% threshold
- No external network access in tests

The separate ADR documentation change in PR #20 also passed documentation
pre-commit verification; the implementation counts above are not attributed
to that documentation PR.

## Deliverables

- `src/aa_crawler/crawler/`
- `src/aa_crawler/http/`
- `src/aa_crawler/robots/`
- `src/aa_crawler/html/`
- `src/aa_crawler/parser/`
- `tests/crawler/`
- `tests/http/`
- `tests/robots/`
- `tests/html/`
- `tests/parser/`
- `docs/adr/`

## Known limitations

- No platform-specific crawler or production crawler CLI
- No DOM parsing library
- No recursive crawling, scheduler, or concurrency
- No asynchronous runtime or browser automation
- No persistence or distributed execution
- No plugin registry

## Technical debt and governance findings

- The crawler package combines domain, runtime, and composition roles.
- The `BaseCrawler` lifecycle remains compatibility-sensitive.
- Request ownership must be validated through the first platform crawler.
- User-agent ownership, retry idempotency, and logging-redaction scope remain
  Proposed ADR topics.
- Pydantic's direct dependency declaration is approved but not implemented.
  **Resolved in Sprint 4:** the dependency metadata was aligned in PR #22.
- A full cross-package integration test remains recommended. **Resolved in
  Sprint 4:** synthetic source-composition integration was added in PR #32.
- Sprint 3 APIs are partially frozen rather than fully stable.

## Deferred work

The following are deliberate product or architecture deferrals, not claims of
implemented behavior:

- Platform-specific crawling and DOM extraction
- Recursive crawling and scheduling
- Async, browser, and distributed execution families
- Persistence and plugin discovery
- Production crawler CLI

## ADRs

The [ADR index](../adr/README.md) records 10 Accepted, 4 Proposed, and 2
Deferred decisions. Accepted ADRs govern the delivered baseline; Proposed and
Deferred ADRs do not represent implemented policy.

## Sprint 4 entry conditions

- Sprint 3 documentation closure is merged.
- Pydantic dependency metadata is aligned in a separate PR. **Resolved in
  Sprint 4:** PR #22 completed the alignment.
- The Sprint 4 backlog is approved.
- Proposed security or correctness ADRs are resolved before their corresponding
  production behavior is enabled.

## Status

Completed and ready for Sprint 4 planning after closure tasks.
