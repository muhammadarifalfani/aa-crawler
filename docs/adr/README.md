# Architecture Decision Records

Architecture Decision Records (ADRs) preserve significant technical and
governance decisions for AA Crawler. They explain not only what was selected,
but also the context, alternatives, consequences, compatibility commitments,
and conditions that require review.

## Statuses

- **Accepted** — approved and part of the supported architecture.
- **Proposed** — documented for review; no option is approved yet.
- **Deferred** — intentionally postponed until a stated trigger occurs.
- **Superseded** — replaced by a later ADR that preserves the historical record.

## Numbering and filenames

Files use an immutable four-digit sequence and a lowercase kebab-case title,
for example `0001-configuration-source-precedence.md`. Documents display the
same decision as `ADR-001`. Gaps are allowed when candidates are merged or not
adopted. Accepted ADRs are never renumbered.

Accepted ADRs may receive non-semantic corrections, but their decisions must
not be silently rewritten. A changed architectural decision requires a new ADR
that supersedes the historical record.

## Index

| Number | Title | Status | Summary | Related implementation | Review trigger |
|---|---|---|---|---|---|
| [ADR-001](0001-configuration-source-precedence.md) | Configuration source precedence and explicit dotenv selection | Accepted | Overrides, OS environment, one explicit dotenv file, then defaults | `configuration/loader.py` | New configuration source or secret manager |
| [ADR-002](0002-immutable-settings-and-contracts.md) | Immutable settings and domain contracts | Accepted | Use frozen models with defensive top-level copies | Configuration and domain models | Persistence, plugins, or cross-process transfer |
| [ADR-003](0003-httpx-synchronous-transport.md) | HTTPX as the synchronous transport boundary | Accepted | Isolate HTTPX behind `HttpClient` and adapters | `http/` | Async, browser, streaming, or transport replacement |
| [ADR-004](0004-explicit-timeout-and-retry-policies.md) | Explicit timeout and retry policies | Accepted | Inject immutable transport policies; never use metadata | `http/policies.py` | Non-GET requests, jitter, or distributed retries |
| [ADR-005](0005-robots-aware-html-acquisition.md) | Robots-aware HTML acquisition | Accepted | Keep robots, transport, acquisition, and decoding boundaries distinct | `robots/`, `html/` | Alternate acquisition or long-lived cache requirements |
| [ADR-007](0007-lazy-parser-lifecycle.md) | Lazy parser lifecycle and output validation | Accepted | Lazily yield validated `CrawlerItem` values | `parser/` | Non-HTML or async parsing |
| [ADR-008](0008-crawler-lifecycle-and-html-composition.md) | Crawler lifecycle and generic HTML composition | Accepted | Use the base template lifecycle and protected specialization seam | `crawler/` | First platform crawler or follow-up requests |
| [ADR-010](0010-constructor-injection-and-composition.md) | Constructor injection and explicit composition ownership | Accepted | Build dependencies explicitly; prohibit service locators and global settings | `bootstrap.py`, package constructors | Material object-graph or lifecycle growth |
| [ADR-011](0011-sprint-4-api-and-package-policy.md) | Sprint 4 public API and package policy | Accepted | Partially freeze mature APIs while crawler seams remain provisional | Public package facades | First platform crawler completion |
| [ADR-013](0013-pydantic-dependency-classification.md) | Pydantic dependency classification | Accepted | Treat directly imported Pydantic as a strategic direct dependency | Configuration models and loader | Dependency metadata PR or Pydantic upgrade |
| [ADR-014](0014-user-agent-ownership.md) | User-agent ownership | Proposed | Select one authoritative identity for robots and page requests | `robots/`, `html/` | Before production crawling |
| [ADR-015](0015-retry-idempotency.md) | Retry idempotency | Proposed | Define retry eligibility for non-idempotent methods | `http/` | Before any non-GET request |
| [ADR-016](0016-logging-redaction-scope.md) | Logging redaction scope | Proposed | Define guarantees across owned and unrelated handlers | `observability/` | Before sensitive platform logging |
| [ADR-017](0017-metadata-portability.md) | Metadata portability | Deferred | Retain in-process mappings until portability is required | Crawler and HTML contracts | Persistence, plugins, queues, or workers |
| [ADR-018](0018-error-root-taxonomy.md) | Error-root taxonomy | Deferred | Revisit independent configuration and crawler roots before stable API | Exception packages | Application supervision or version 1.0 |
| [ADR-019](0019-future-execution-families.md) | Future execution families | Proposed | Keep async/browser runtimes and heavy dependencies isolated | Future architecture | Alternate runtime approval |
