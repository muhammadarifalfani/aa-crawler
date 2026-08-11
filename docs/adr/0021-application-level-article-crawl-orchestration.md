# ADR-021 — Application-Level Article Crawl Orchestration

- Status: Accepted
- Date: 2026-08-11
- Decision owners: Application owner, Crawler owner, Tech Lead
- Related ADRs: ADR-003, ADR-005, ADR-007, ADR-010, ADR-011, ADR-014,
  ADR-015, ADR-016, ADR-017, ADR-018, ADR-019, ADR-020

## Context

Sprint 4 completed the synchronous acquisition, article parsing, declarative
source, and parser-composition boundaries. The implemented source-composition
flow starts from an existing `HtmlDocument`; no application service currently
connects source selection, robots-aware acquisition, final-source validation,
parser construction, and crawler-facing output for one URL.

Sprint 5 requires the smallest synchronous application boundary that completes
that flow without moving HTTP, robots, parsing, identity, source-governance, or
composition responsibilities into a new coordinator.

This ADR accepts the architecture. `aa_crawler.application`,
`ArticleCrawlService`, `UnsupportedSourceError`, and `SourceBoundaryError` are
approved contracts for later Sprint 5 implementation; none exists at the time
of this decision.

## Decision drivers

- Complete one explicit single-URL article crawl use case
- Preserve every established subsystem owner
- Reject unsupported or disabled sources before network access
- Enforce the selected source boundary after acquisition
- Maintain constructor injection and visible dependency lifetimes
- Preserve parser zero-or-more output cardinality
- Avoid publisher-specific orchestration and dynamic loading
- Enable deterministic tests without live publisher access

## Considered options

### Place orchestration in `aa_crawler.crawler`

Rejected. The package already owns crawler contracts and the template
lifecycle. Making it import source lookup, parser composition, and acquisition
would broaden its responsibility and risk dependency cycles because parsers,
article contracts, HTTP, and robots already depend on crawler contracts.

### Add `aa_crawler.orchestration`

Rejected. It would overlap conceptually with the existing `composition`
package, which deliberately owns parser construction only. The distinction
between parser composition and application coordination would be unnecessarily
ambiguous.

### Create one orchestrator per publisher

Rejected. Publisher identity and exact hosts are declarative `SourceProfile`
data. Schema-compatible publishers reuse the generic parser; a publisher name
alone does not justify another orchestration class.

### Let parsers or source profiles acquire content

Rejected. Parsers interpret an existing document, and source profiles remain
immutable, declarative, and network-free. Hidden acquisition would violate
ADR-020 and make tests and dependency direction less explicit.

### Let the application service own robots or retries

Rejected. `RobotsPolicy` and `HtmlFetcher` own robots-aware acquisition;
`HttpClient` and `RetryPolicy` own transport attempts and backoff. Duplicating
those rules creates conflicting authorities.

### Use global mutable dependencies

Rejected. Global clients, registries, identities, or service locators hide
lifetimes, introduce test-order coupling, and violate ADR-010.

### Return `None` for unsupported sources

Rejected. A public crawl operation must distinguish an unsupported operational
input from a successful parse that produces no items.

### Add dynamic plugins, reflection, or redirects

Rejected. Dynamic loading remains outside ADR-020, and redirect traversal has
robots and source-boundary implications that require a separate review.
Neither is needed for the synchronous application flow approved here.

## Decision

### Application ownership

Application-level article crawl coordination belongs in a new
`aa_crawler.application` package. It sits above the existing domain and
infrastructure packages and may depend on their public APIs. Existing packages
must not depend on the application package.

The package must remain a narrow application-use-case boundary rather than a
general service container or publisher-specific runtime.

### Primary abstraction

The intended public abstraction is `ArticleCrawlService` with this minimal
contract:

```python
class ArticleCrawlService:
    def __init__(
        self,
        *,
        source_registry: SourceRegistry,
        html_fetcher: HtmlFetcher,
        parser_composer: ParserComposer,
    ) -> None:
        ...

    def crawl(
        self,
        url: str,
        *,
        metadata: Mapping[str, object] | None = None,
    ) -> tuple[CrawlerItem, ...]:
        ...
```

This is an accepted architectural contract, not an implementation claim.

The service receives all collaborators through constructor injection. It does
not construct dependencies, discover globals, or use a service locator. It
exposes one synchronous operation and returns an eager immutable tuple. The
tuple preserves the existing parser contract in which one document may produce
zero or more `CrawlerItem` values; the service does not force one-item
cardinality or expose `ArticleItem` as its application output.

### Runtime responsibility

`ArticleCrawlService` coordinates only:

1. requested-source resolution;
2. HTML acquisition;
3. final-source validation;
4. parser construction;
5. parsing; and
6. return of crawler-facing output.

It owns none of the validation, transport, robots, retry, identity, parsing, or
source-governance rules implemented by its collaborators.

### Single-URL sequence

The approved sequence is:

```text
requested URL
  → SourceRegistry.get_by_url()
  → enabled SourceProfile
  → HtmlFetcher.fetch()
  → HtmlDocument
  → SourceRegistry.get_by_url(document.final_url)
  → same enabled SourceProfile
  → ParserComposer.create()
  → parser.parse()
  → tuple[CrawlerItem, ...]
```

### Requested-source gate

The requested URL must resolve through normal `SourceRegistry.get_by_url()`
lookup before `HtmlFetcher` is called. Malformed, non-HTTPS, unknown-host, and
disabled-source URLs must not reach acquisition.

Normal orchestration must not use `include_disabled=True`. That option remains
an explicit inspection mechanism, not an operational path.

### Final-source gate

After acquisition, `document.final_url` must resolve through normal enabled
lookup. The resulting profile must be the same authoritative profile selected
before acquisition.

The current registry eagerly stores exact `SourceProfile` instances and returns
those same instances from lookups. The initial implementation will therefore
require identity equality (`final_profile is requested_profile`). It will not
invent new `SourceProfile` identity semantics or accept a separately
constructed value merely because its fields compare equal.

A missing, disabled, or different final profile raises `SourceBoundaryError`
before parser construction.

### Redirect scope

Automatic redirect following is not enabled by the current `HttpClient`.
Ordinary 3xx responses are therefore not traversed and fail the existing
`HtmlFetcher` success-status requirement.

This ADR does not enable redirects. Final-source validation protects the
current response boundary and test doubles, but it is not sufficient for a
future redirect traversal: every followed destination may require source and
robots authorization before network access. Redirect support requires a
separate architecture review.

### Input and output

The input is a raw URL string. No shared URL value object exists, and
`SourceRegistry` already owns safe absolute HTTPS and exact-host lookup
validation. The application layer must not duplicate those parsing rules.

The output is `tuple[CrawlerItem, ...]`. No success wrapper, `ArticleItem`
return, forced single-item result, or optional-success convention is approved.

### Application errors

Two narrow application-owned errors are approved for later implementation:

- `UnsupportedSourceError` represents failure to select an enabled source for
  the requested URL. It covers malformed, non-HTTPS, unknown-host, and disabled
  inputs without requiring disabled-profile inspection.
- `SourceBoundaryError` represents successful acquisition whose final URL does
  not resolve to the same enabled profile selected before acquisition.

Both remain within the existing crawler/application error ecosystem and follow
current `CrawlerError` conventions. ADR-021 does not introduce a universal
project exception root or alter existing inheritance; ADR-018 remains
Deferred.

Subsystem errors normally propagate unchanged, including
`HtmlDisallowedError`, `RequestError`, `ResponseError`, `RobotsError`,
`HtmlContentTypeError`, `HtmlDecodingError`, `ParserCompositionError`,
`ParserError`, and `ArticleParserError`. Broad exception translation is not
approved.

### Robots ownership

`HtmlFetcher` and `RobotsPolicy` remain authoritative. The application service
must not call robots separately, parse robots content, implement allow/deny
rules, convert denial into empty success, or fetch after denial.

### Retry ownership

`HttpClient` and `RetryPolicy` remain authoritative. The application service
must not retry, sleep, calculate backoff, inspect retryable statuses, decide
method eligibility, process `Retry-After`, or allow metadata to influence retry
eligibility.

### Final transport boundary and canonical boundary

Final transport/source validation belongs to application orchestration and uses
`HtmlDocument.final_url`. Canonical article interpretation remains owned by
`JsonLdArticleParser` and `ArticleItem`. The application service must not parse
or validate canonical metadata.

### Identity ownership

`RequestIdentity` construction remains outside `ArticleCrawlService`. The
service receives an already composed `HtmlFetcher`; it does not construct or
compare identity values, mutate User-Agent headers, or inject identity into
`HttpClient`. Existing `HtmlFetcher` construction already validates consistency
with its `RobotsPolicy`.

### Network boundary

At the service level, `HtmlFetcher` is the only acquisition entry point.
Internally, `HttpClient` remains the only transport executor. `SourceRegistry`,
`SourceProfile`, `ParserComposer`, and parsers remain network-free.

### Dependency lifecycle

The application composition root constructs dependencies, owns the
`HttpClient` lifecycle, and wires one consistent request identity through
`RobotsPolicy` and `HtmlFetcher`.

`ArticleCrawlService` coordinates injected dependencies. It does not close or
globally cache them. This ADR does not change `bootstrap_application()`; a
later Sprint 5 task will decide the concrete composition-root lifecycle.

### State and concurrency

The service is stateless per crawl operation and reusable for sequential
synchronous calls. It is concurrency-neutral and makes no thread-safety
guarantee. In particular, `RobotsPolicy` has mutable per-instance cache state
without a synchronization contract.

Async execution, browser acquisition, workers, and distributed execution are
outside this ADR.

### Source governance

Orchestration consumes current `SourceRegistry` governance unchanged. It does
not modify `CNN_INDONESIA_PROFILE`, `KOMPAS_PROFILE`, or
`DEFAULT_SOURCE_PROFILES`. CNN Indonesia remains enabled and Kompas remains
disabled.

`enabled=True` means available to normal project lookup; it is not legal,
publisher-policy, robots, rate-limit, or operational authorization.

### Parser timing

`ParserComposer.create()` occurs only after initial source resolution,
successful acquisition, and final-source validation. Unsupported and
boundary-invalid requests must not construct a parser.

## Rationale

A thin application service closes the currently missing use-case boundary while
leaving every technical rule with its existing owner. Early source resolution
prevents unauthorized or unsupported acquisition. Revalidating the final URL
protects the exact source selected for the operation. Constructor injection and
an existing-contract tuple result keep the service deterministic and easy to
test without creating another publisher hierarchy or transport abstraction.

## Consequences

### Positive

- Provides a complete explicit single-URL application flow.
- Preserves HTTP, robots, acquisition, parsing, source, and composition owners.
- Makes dependency construction and lifecycle boundaries visible.
- Rejects unsupported sources before network acquisition.
- Enforces the selected source boundary after acquisition.
- Avoids per-publisher orchestrator proliferation.
- Supports straightforward fake and mock-transport tests.
- Preserves existing crawler-facing output contracts and parser cardinality.

### Negative

- Adds a new public application package and two application-specific errors.
- Remains synchronous only.
- Does not support redirect traversal.
- Makes no thread-safety guarantee.
- Requires separate composition-root implementation and lifecycle work.
- Can use only parser families already supported by `ParserComposer`.

### Neutral

- Production source declarations and enablement remain unchanged.
- Existing subsystem errors retain their current inheritance and behavior.
- Application APIs remain subject to the repository's provisional API policy
  until exercised operationally.

## Compatibility implications

ADR-021 introduces a new application-facing API without changing existing
constructors or contracts. Callers may rely on pre-acquisition enabled lookup,
same-profile final-source validation, eager tuple output, and propagation of
existing subsystem errors once implementation lands.

Changing output cardinality, source-gate order, profile-identity comparison,
redirect behavior, or dependency ownership would alter the accepted contract
and requires review.

## Relationship to existing decisions

- ADR-014 remains authoritative for `RequestIdentity` and User-Agent ownership.
- ADR-015 remains authoritative for retry eligibility and backoff.
- ADR-020 remains authoritative for `SourceProfile`, `SourceRegistry`,
  `ParserComposer`, exact-host lookup, and enablement governance.
- ADR-016 remains Proposed; ADR-021 approves no broader redaction guarantee.
- ADR-017 remains Deferred; application metadata retains trusted in-process
  limits and no portability guarantee.
- ADR-018 remains Deferred; ADR-021 establishes no universal exception root.
- ADR-019 remains Proposed; async and browser execution are outside ADR-021.

## Follow-up work

- Implement the minimal `aa_crawler.application` contracts and focused tests.
- Implement `ArticleCrawlService` using the approved sequence.
- Add synthetic and mock-transport integration tests with no live network.
- Define composition-root construction and `HttpClient` lifecycle separately
  without changing `bootstrap_application()` implicitly.
- Update Engineering Standards and user documentation after implementation is
  verified.

## Review triggers

- Redirect following is proposed.
- Async crawling or browser execution is introduced.
- Workers, distributed execution, persistence, or queues are introduced.
- Runtime source-profile reload is required.
- A richer application result type or different parser cardinality is needed.
- A custom adapter runtime is implemented.
- `HttpClient` construction or lifecycle ownership changes.
- Shared concurrent `RobotsPolicy` use requires a synchronization guarantee.
