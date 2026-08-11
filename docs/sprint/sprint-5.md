# Sprint 5 Completion Report

## 1. Status

Sprint 5 implementation is complete. Documentation is complete pending final
repository verification and formal closure.

Formal closure must not be declared until this report is merged, the final
repository quality gate passes on the merged state, and local `main` is
synchronized cleanly with `origin/main`.

## 2. Objective

Sprint 5 moved AA Crawler from individually implemented crawler, acquisition,
source, and parser subsystems to an explicit application-level article crawl
flow with auditable runtime composition and resource ownership. The delivered
scope remains synchronous and deliberately narrow.

## 3. Architecture decisions

- [ADR-021 — Application-Level Article Crawl Orchestration](../adr/0021-application-level-article-crawl-orchestration.md)
  is **Accepted** and defines application source gates, acquisition sequencing,
  parser composition, and output behavior.
- [ADR-022 — Application Runtime Composition and Resource Ownership](../adr/0022-application-runtime-composition-and-resource-ownership.md)
  is **Accepted** and defines the synchronous runtime graph and transport
  cleanup ownership.

Earlier accepted decisions remain authoritative in their existing areas:

- [ADR-014 — User-Agent Ownership](../adr/0014-user-agent-ownership.md)
- [ADR-015 — Retry Idempotency](../adr/0015-retry-idempotency.md)
- [ADR-020 — Declarative Source Architecture](../adr/0020-declarative-source-architecture.md)

The [ADR index](../adr/README.md) records 15 Accepted, 2 Proposed, 2 Deferred,
and 0 Superseded decisions. ADR-016 and ADR-019 remain Proposed; ADR-017 and
ADR-018 remain Deferred. This report does not change those statuses.

## 4. Application package

Sprint 5 introduced `aa_crawler.application` with this exact public API:

- `ApplicationError`
- `ApplicationRuntime`
- `ArticleCrawlService`
- `SourceBoundaryError`
- `UnsupportedSourceError`
- `create_application_runtime`

The package coordinates existing boundaries. It does not take ownership of
HTTP, robots, retry, identity, source, or parsing policy.

## 5. Article crawl orchestration

`ArticleCrawlService` implements this sequence:

```text
raw requested URL
    → enabled SourceRegistry lookup
    → HtmlFetcher.fetch()
    → HtmlDocument
    → final URL SourceRegistry lookup
    → exact same-profile validation
    → ParserComposer
    → parser
    → tuple[CrawlerItem, ...]
```

The initial source lookup occurs before acquisition. Malformed, non-HTTPS,
unknown, and disabled sources fail through the application source gate before
`HtmlFetcher` is called. Acquisition receives the original requested URL.

After acquisition, `HtmlDocument.final_url` is resolved through the same
authoritative registry. The resolved object must be the exact originally
selected `SourceProfile`. A transition between exact hosts declared by that
same profile is allowed. A missing, disabled, or different final profile fails
before parser construction.

Parser composition occurs only after both source gates pass. Parser output is
materialized as an eager immutable `tuple[CrawlerItem, ...]`; item order and
zero-or-more cardinality are preserved. Existing acquisition, composition, and
parser errors propagate without broad application-layer wrapping.

## 6. Application errors

The implemented hierarchy is:

```text
CrawlerError
└── ApplicationError
    ├── UnsupportedSourceError
    └── SourceBoundaryError
```

- `UnsupportedSourceError` means no enabled source could be selected before
  acquisition.
- `SourceBoundaryError` means the acquired document crossed the originally
  selected source-profile boundary.

Canonical URL interpretation remains the responsibility of
`JsonLdArticleParser` and `ArticleItem`, not `SourceBoundaryError`. Application
error messages are concise and deterministic and retain no rejected URL,
source, response, headers, HTML, credentials, or metadata payload.

## 7. Metadata behavior

`ArticleCrawlService` forwards caller metadata to acquisition unchanged.
Metadata does not select a source, broaden retry eligibility, change request
identity, bypass source governance, or determine parser-family selection.

## 8. Runtime composition

`create_application_runtime()` constructs one independent synchronous
`ApplicationRuntime` in this order:

1. Resolve `importlib.metadata.version("aa-crawler")`.
2. Construct one `RequestIdentity`.
3. Construct explicit `TimeoutPolicy` and `RetryPolicy` instances.
4. Construct runtime-local `SourceRegistry(DEFAULT_SOURCE_PROFILES)` and
   `ParserComposer` instances.
5. Create and enter exactly one `HttpClient` under private cleanup ownership.
6. Construct `RobotsPolicy` and `HtmlFetcher` with the same exact identity.
7. Construct `ArticleCrawlService` with the runtime-local registry, fetcher,
   and composer.
8. Transfer cleanup ownership into `ApplicationRuntime`.

`RequestIdentity` is not injected into `HttpClient`. The runtime exposes only
`article_crawl_service` as its application service. Multiple runtimes receive
fresh identity, transport, robots policy, fetcher, registry, composer, and
service instances and share no mutable runtime state.

## 9. Resource ownership and cleanup

Each `ApplicationRuntime` owns exactly one `HttpClient`. `ArticleCrawlService`,
`RobotsPolicy`, and `HtmlFetcher` use but do not close it.

The runtime uses a private `ExitStack`, supports synchronous context management
and explicit `close()`, and makes repeated close harmless. Failure after client
acquisition closes acquired resources while preserving the original exception;
partially constructed runtime state does not escape. No thread-safety guarantee
is made.

## 10. Bootstrap boundary

`bootstrap_application()` and `create_application_runtime()` have separate
responsibilities:

- `bootstrap_application()` loads settings, prepares runtime directories,
  configures logging, and returns the same frozen `ApplicationSettings`.
- `create_application_runtime()` accepts no settings and constructs and owns
  the synchronous network runtime graph.

Neither function implicitly calls the other, and bootstrap does not return or
own `ApplicationRuntime`.

## 11. Production-source governance

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

Enablement is project governance state only. It does not establish legal
authorization, publisher permission, robots authorization, rate-limit
approval, or operational approval. Source ownership uses exact-host matching;
wildcard, suffix, parent-domain, and implicit subdomain authorization are not
supported.

## 12. Integration verification

Application-flow integration uses the real `SourceRegistry`, production
profiles, `ParserComposer`, `JsonLdArticleParser`, and crawler/article
contracts behind a synthetic acquisition boundary. Durable coverage includes:

- the enabled CNN Indonesia golden path;
- requested and canonical URL distinction;
- allowed same-profile multi-domain final URLs;
- cross-profile rejection before parser construction;
- disabled, unknown, malformed, and HTTP source rejection before acquisition;
- unchanged parser-error propagation and parser-owned canonical validation;
- metadata inertness for governance and parser selection;
- repeatable composition and fresh parser instances; and
- no external network, browser, or robots runtime.

Runtime integration verifies the real cross-package composition graph with a
network-guarded transport. Durable coverage includes:

- dependency construction order and one-instance-per-runtime cardinality;
- installed-version propagation and identity reuse;
- version lookup before transport acquisition;
- synchronous context and explicit cleanup;
- idempotent close and cleanup after partial construction failure;
- preservation of original construction exceptions;
- independence across repeated runtime cycles;
- compatibility with the separate bootstrap boundary;
- production-profile integrity; and
- no construction-time network request.

## 13. Quality gates

The repository verification strategy uses:

- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy`
- `uv run pytest`
- `uv run pytest --cov=aa_crawler`, with the configured minimum of 70%
- `uv sync --locked` for lockfile consistency
- `uv --cache-dir .uv-cache run pre-commit run --all-files`

Sprint 5 implementation and documentation tasks passed their applicable
focused and repository-wide gates. Final verification on the merged completion
state remains a closure requirement and is intentionally unchecked below.

## 14. Security and safety properties

Sprint 5 added focused controls without claiming comprehensive security or
legal compliance:

- enabled exact-profile gates before and after acquisition;
- safe absolute HTTPS source lookup and no wildcard host authorization;
- deterministic, payload-free application error messages;
- no retention of URLs, credentials, headers, HTML, responses, or metadata in
  application errors;
- metadata cannot override source governance, retry, identity, or parser
  selection;
- one runtime-local request identity shared by the required acquisition
  collaborators;
- explicit transport ownership and failure-safe cleanup; and
- synthetic, network-isolated application and runtime integration tests.

## 15. Current limitations

- Automatic redirect following remains disabled.
- No asynchronous or browser runtime exists.
- No worker, queue, scheduler, or distributed execution architecture exists.
- No persistence or storage pipeline exists.
- No dynamic adapter or plugin runtime exists.
- Runtime source-profile reload is not implemented.
- The synchronous runtime has no thread-safety guarantee.
- `jsonld_article` is the only supported parser family.
- Production source enablement remains intentionally small.
- Source enablement does not constitute legal or operational authorization.

## 16. Sprint 4 follow-up resolution

Sprint 4 correctly recorded application orchestration as future work at its
completion point. Sprint 5 subsequently implemented that boundary through
ADR-021 and implemented runtime composition through ADR-022. The later
[Sprint 4 Subsequent Resolution](sprint-4.md#18-subsequent-resolution)
annotation records this progression without rewriting Sprint 4 history.

## 17. Sprint 5 pull-request inventory

- PR #39 — ADR-021 application crawl orchestration decision
- PR #40 — application error contracts
- PR #41 — `ArticleCrawlService`
- PR #42 — application crawl integration verification
- PR #43 — ADR-022 runtime ownership decision
- PR #44 — `ApplicationRuntime` and runtime factory
- PR #45 — runtime composition integration verification
- PR #46 — ADR implementation-reference alignment
- PR #47 — Engineering Standards alignment
- PR #48 — README alignment
- PR #49 — Sprint 4 subsequent-resolution annotation

## 18. Sprint 5 closure checklist

- [x] ADR-021 accepted
- [x] Application error contracts implemented
- [x] `ArticleCrawlService` implemented
- [x] Application integration verification added
- [x] ADR-022 accepted
- [x] `ApplicationRuntime` and `create_application_runtime()` implemented
- [x] Runtime integration verification added
- [x] ADR implementation references aligned
- [x] Engineering Standards aligned
- [x] README aligned
- [x] Sprint 4 subsequent-resolution annotation merged
- [x] Sprint 5 completion report created
- [ ] Sprint 5 completion report merged
- [ ] Final repository verification passed after completion-report merge
- [ ] `main` synchronized after final merge
- [ ] Sprint 5 formally closed

## 19. Provisional Sprint 6 direction

No Sprint 6 architecture is approved by this report. Provisional future areas
supported by current documentation include separately reviewed redirect
behavior, broader source governance, persistence, scheduling, workers or
queues, alternate async/browser execution under ADR-019, and evidence-driven
adapter extensibility. Each requires explicit scope and architecture approval
before implementation.

## 20. Completion statement

Sprint 5 is ready for completion-report review. Formal closure occurs only
after this report is merged, the full repository quality gate passes on the
merged state, and local `main` is synchronized cleanly with `origin/main`.
