# Sprint 4 Completion Report

## 1. Status

Sprint 4 is implementation-complete and documentation-complete pending final
repository verification and merge. This completion task changes documentation
only; it introduces no code or dependency changes.

Formal closure must not be declared until this report is merged, the final
repository quality gate passes, and `main` is synchronized cleanly.

## 2. Objective

Sprint 4 evolved the synchronous crawler foundation by:

- establishing an explicit outbound request identity;
- enforcing retry idempotency;
- adding a normalized article contract;
- adding generic JSON-LD article parsing;
- introducing a scalable declarative source architecture; and
- proving source composition without one parser class per publisher.

## 3. Implemented work

### Identity

- Added the immutable, validated `RequestIdentity` value object.
- Propagated one identity through `RobotsPolicy` and `HtmlFetcher`.
- Used the same User-Agent for robots retrieval, robots evaluation, and page
  retrieval.
- Rejected mismatched robots and HTML identities before network access.

### HTTP retry

- Restricted automatic retries to `GET` and `HEAD`.
- Preserved valid single-attempt behavior for every other method.
- Retained bounded attempts and deterministic capped backoff.
- Kept retry eligibility under HTTP-layer `RetryPolicy` ownership.

### Article contract

- Added the immutable, source-independent `ArticleItem` contract.
- Kept requested and canonical URLs distinct.
- Required timezone-aware timestamps and normalized them deterministically.
- Normalized, ordered, deduplicated, and preserved authors immutably.
- Added deterministic conversion to `CrawlerItem`.

### Parser

- Added the source-agnostic `JsonLdArticleParser`.
- Preferred `NewsArticle` over generic `Article` candidates.
- Bounded JSON-LD traversal to protect depth and visited-node work.
- Rejected ambiguous candidates rather than selecting silently.
- Used narrow generic fallbacks for canonical identity and optional metadata.

### Sources

- Added immutable declarative `SourceProfile` values.
- Added an immutable `SourceRegistry` with exact-source and exact-host lookup.
- Rejected conflicting source and host ownership during eager construction.
- Excluded disabled profiles from normal lookup while retaining explicit
  inspection through `include_disabled=True`.

### Composition

- Added stateless `ParserComposer` construction.
- Mapped `jsonld_article` explicitly to `JsonLdArticleParser`.
- Returned a new parser instance for every composition.
- Added no reflection, dynamic imports, entry points, or plugin scanning.
- Kept `adapter_key` inert in profiles and unsupported during composition.

### Production profiles

- Added an enabled CNN Indonesia profile for its explicitly declared host.
- Added a disabled Kompas profile for its explicitly declared hosts.
- Kept the default profile collection immutable and deterministic.

### Integration

- Added source-composition integration tests using synthetic HTML only.
- Covered enabled, disabled, unknown, unsafe, deterministic, and failure paths.
- Used no external network and instantiated no acquisition-layer components.

## 4. Architecture

The accepted Sprint 4 source-composition flow is:

```text
URL
  → SourceRegistry
  → SourceProfile
  → ParserComposer
  → JsonLdArticleParser
  → ArticleItem
  → CrawlerItem
```

This flow assumes an `HtmlDocument` already exists. It does not implement the
future application-level flow:

```text
URL
  → source resolution
  → robots-aware acquisition
  → HtmlDocument
  → parser composition
  → article output
```

Joining those boundaries remains future orchestration work.

## 5. Accepted ADRs

- [ADR-014 — User-Agent Ownership](../adr/0014-user-agent-ownership.md) is
  **Accepted** and governs immutable identity ownership and consistent
  propagation across robots and page acquisition.
- [ADR-015 — Retry Idempotency](../adr/0015-retry-idempotency.md) is
  **Accepted** and limits automatic retries to `GET` and `HEAD` under HTTP
  policy ownership.
- [ADR-020 — Declarative Source Architecture](../adr/0020-declarative-source-architecture.md)
  is **Accepted** and separates declarative profiles, exact-host lookup, and
  explicit parser construction.

The remaining reviewed decisions retain their existing status:

- ADR-016, Logging Redaction Scope: **Proposed**
- ADR-017, Metadata Portability: **Deferred**
- ADR-018, Error-Root Taxonomy: **Deferred**
- ADR-019, Future Execution Families: **Proposed**

These statuses are recorded by the [ADR index](../adr/README.md); this report
does not redefine those decisions.

## 6. Production-source governance

### CNN Indonesia

- `source`: `cnn_indonesia`
- `domains`: `www.cnnindonesia.com`
- `parser_family`: `jsonld_article`
- `adapter_key`: `None`
- `enabled`: `True`

### Kompas

- `source`: `kompas`
- `domains`:
  - `www.kompas.com`
  - `nasional.kompas.com`
  - `surabaya.kompas.com`
- `parser_family`: `jsonld_article`
- `adapter_key`: `None`
- `enabled`: `False`

An enabled profile is available to normal source lookup. A disabled profile is
retained for explicit inspection but excluded from normal lookup and rejected
by parser composition. Enablement is project governance state; it does not
replace `robots.txt`, publisher policy, legal review, rate limiting, or
operational approval, and it does not claim legal permission.

Host ownership is exact. No wildcard, suffix, parent-domain, or implicit
subdomain authorization exists.

## 7. Scalability decision

Adding an ordinary schema-compatible source should normally require only:

1. a reviewed `SourceProfile` declaration;
2. inclusion in the explicit profile collection; and
3. reuse of the generic parser.

The architecture does not create one parser class per publisher by default.
Source-specific adapters or parsers remain evidence-driven future work.

## 8. Testing and verification evidence

Sprint 4 implementation tasks passed package-focused tests and repository-wide
pytest verification. The repository quality workflow also exercises Ruff
linting, Ruff formatting checks, mypy, coverage, and pre-commit.

Source-composition integration uses deterministic synthetic HTML and metadata.
It does not use external networking, instantiate `HttpClient`, `RobotsPolicy`,
or `HtmlFetcher`, or copy live article content into fixtures.

Final repository verification remains a closure gate and is intentionally not
recorded as complete in this report before it runs on the final state.

## 9. Runtime dependencies

The direct runtime dependencies at Sprint 4 completion are:

- `httpx>=0.28.1,<0.29`
- `pydantic>=2.13.4,<3`
- `pydantic-settings>=2.14.2,<2.15`

The direct Pydantic declaration identified after Sprint 3 was completed in
Sprint 4 through PR #22.

## 10. Public APIs introduced

Sprint 4 introduced these principal public APIs:

- `RequestIdentity`
- `ArticleItem`
- `JsonLdArticleParser`
- `ArticleParserError`
- `SourceProfile`
- `SourceRegistry`
- `SourceRegistryError`
- `ParserComposer`
- `ParserCompositionError`
- `CNN_INDONESIA_PROFILE`
- `KOMPAS_PROFILE`
- `DEFAULT_SOURCE_PROFILES`

The source and composition APIs remain intentionally minimal. This report does
not claim long-term semantic-versioning stability beyond the current accepted
API policy.

## 11. Security and safety controls

Sprint 4 added focused controls without claiming comprehensive security:

- request identity validation and formatted-length limits;
- rejection of control characters and browser or third-party impersonation;
- public HTTPS project/contact validation for identity values;
- safe absolute HTTPS validation for source URL lookup;
- exact-host source ownership without wildcard authorization;
- automatic retry restriction to `GET` and `HEAD`;
- rejection of metadata as a retry-eligibility control;
- synthetic, network-isolated source-composition integration tests; and
- no copied live article content in integration fixtures.

## 12. Known limitations

- No application-level acquisition-to-parsing orchestrator
- No asynchronous execution or browser rendering
- No distributed crawling
- No persistence or storage layer
- No scheduler or queue layer
- No runtime source-profile reload
- Only the `jsonld_article` parser family
- No custom adapter runtime
- An intentionally small production-source set
- No live acquisition in source-composition integration tests

## 13. Deferred and future architecture

The following decisions remain open without being implemented here:

- ADR-016: logging redaction scope
- ADR-017: metadata portability
- ADR-018: error-root taxonomy
- ADR-019: future async, browser, and alternate execution families

Future operational work may include full acquisition orchestration, broader
integration coverage, reviewed source-profile expansion, an adapter API only
when evidence requires it, and observability or governance hardening.

## 14. Sprint 3 follow-up resolution

Sprint 3 recorded direct Pydantic dependency metadata and cross-package
integration testing as follow-up work. Sprint 4 resolved them through PR #22
and PR #32 respectively. The Sprint 3 completion record retains its historical
statements with explicit resolution annotations.

## 15. Sprint 5 entry conditions

Sprint 5 implementation must not begin until:

- Sprint 4 completion documentation is merged;
- final repository verification passes;
- local `main` is synchronized and clean;
- accepted ADRs accurately reflect implementation;
- production-source governance state is documented;
- no live-network integration is enabled silently; and
- Sprint 5 scope is reviewed and approved.

A recommended, non-committed direction is application-level orchestration that
joins source resolution, robots-aware acquisition, `HtmlDocument`, parser
composition, and article output. Broader reviewed source onboarding plus
integration and observability hardening may also be considered.

## 16. Closure checklist

- [x] Sprint 4 implementation merged
- [x] ADR-014 accepted
- [x] ADR-015 accepted
- [x] ADR-020 accepted
- [x] Engineering Standards aligned
- [x] README aligned
- [x] Sprint 4 completion report created
- [ ] Final repository verification passed
- [ ] Completion-report PR merged
- [ ] `main` synchronized after final merge
- [ ] Sprint 4 formally closed

## 17. Completion statement

Sprint 4 is ready for final verification. Formal closure occurs only after
this completion report is merged, the full repository quality gate passes on
the final state, and `main` is synchronized cleanly.

## 18. Subsequent Resolution

This annotation was added later during Sprint 5 documentation alignment. It
does not change the point-in-time Sprint 4 implementation record or the
original closure checklist above.

After this report was written, its completion-report pull request was merged,
local `main` was synchronized cleanly with `origin/main`, and final repository
verification passed. The completion-time quality gate included Ruff linting,
Ruff formatting, mypy, pytest, coverage above the configured threshold,
lockfile consistency, and pre-commit; the synchronized working tree remained
clean. The remaining unchecked closure items were therefore subsequently
satisfied, and Sprint 4 was formally closed.

Sprint 5 then built on, rather than retroactively extending, the Sprint 4
foundation. [ADR-021](../adr/0021-application-level-article-crawl-orchestration.md)
was accepted, `aa_crawler.application` and `ArticleCrawlService` were
introduced, pre- and post-acquisition source gates were implemented, and the
cross-package application flow was verified with network-isolated integration
tests.

[ADR-022](../adr/0022-application-runtime-composition-and-resource-ownership.md)
was subsequently accepted to define runtime composition and resource
ownership. Sprint 5 implemented `ApplicationRuntime` and
`create_application_runtime()`, made `HttpClient` lifecycle ownership explicit,
and verified runtime composition and failure-safe cleanup through integration
tests. These are Sprint 5 outcomes built on Sprint 4 foundations; they were not
part of the Sprint 4 implementation inventory or decisions.
