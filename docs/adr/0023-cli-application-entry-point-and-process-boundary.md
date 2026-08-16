# ADR-023 — CLI Application Entry Point and Process Boundary

- Status: Accepted
- Date: 2026-08-16
- Decision owners: Application owner, CLI owner, Tech Lead
- Related ADRs: ADR-010, ADR-011, ADR-014, ADR-015, ADR-016, ADR-017,
  ADR-018, ADR-020, ADR-021, ADR-022

## Context

Sprint 5 completed `ArticleCrawlService` and `ApplicationRuntime`, giving AA
Crawler a fully composed synchronous single-URL application flow. No process
currently invokes that flow. The declared `aa-crawler` console script resolves
to `aa_crawler.main()`, which only prints a placeholder greeting and imports
nothing from `application`, `bootstrap`, or any lower-level package.

Sprint 6 Task 6.1 (read-only architecture discovery) evaluated CLI,
persistence, redirect, source-scaling, alternate-runtime, worker/queue, and
observability directions against repository evidence. The CLI direction was
the only candidate with every architectural prerequisite already met:
`create_application_runtime()` already exposes exactly one collaborator,
`article_crawl_service`, with full lifecycle ownership; `bootstrap_application()`
already returns settings independent of that runtime; and the shipped
`jsonld_article` parser family already produces JSON-safe output through
`ArticleItem.to_dict()`.

Discovery also found that the exception landscape a process boundary must
handle is fragmented: `AACrawlerError` (configuration) and `CrawlerError`
(crawl domain, including `ApplicationError`) are independent roots, and
`SourceRegistryError`/`ParserCompositionError` derive from plain `ValueError`
outside both. Runtime-integration tests further show that
`create_application_runtime()` can raise an unwrapped standard-library
`importlib.metadata.PackageNotFoundError`. ADR-018 already names "CLI failure
handling" as one of its own review triggers without resolving the taxonomy
itself. This ADR answers the process-boundary question that trigger
anticipated, without redesigning that taxonomy.

This ADR accepts the architecture. `aa_crawler.cli` and its public `main()`
entry point are approved contracts for later Sprint 6 implementation; neither
exists at the time of this decision.

## Decision drivers

- Give the existing application/runtime architecture one real, user-facing
  execution path
- Reuse `bootstrap_application()` and `create_application_runtime()`
  unchanged, with no duplicated ownership
- Keep the CLI a thin process boundary, not a second application layer
- Avoid a new runtime dependency
- Provide a small, explicit, testable mapping from existing exceptions to
  process exit codes without altering the exception hierarchy
- Keep machine-readable output and human-readable logging separated
- Avoid logging or printing sensitive request/response material
- Avoid touching any lower-layer ownership boundary or accepted ADR

## Considered options

### Extend `bootstrap_application()` to also execute a crawl and print output

Rejected. `bootstrap_application()` has an established settings/startup
contract confirmed unchanged by ADR-022. Coupling it to crawl execution and
process output would recombine responsibilities ADR-022 deliberately kept
separate.

### Place CLI code inside `aa_crawler.application`

Rejected. ADR-021 defines `aa_crawler.application` as "a narrow
application-use-case boundary rather than a general service container." A
process entry point with argument parsing, stdout/exit-code concerns, and
process-level error translation is a different responsibility from use-case
coordination and would blur that boundary.

### Add Click or Typer as a CLI dependency

Rejected for the initial scope. The approved surface is one synchronous
single-URL command. Standard-library `argparse` is sufficient, and no
repository evidence justifies a new runtime dependency for it.

### Accept multi-URL batch input or JSON Lines output now

Rejected. `ArticleCrawlService.crawl()` is an approved single-URL contract.
Batch orchestration, concurrency, and partial-failure semantics across
multiple URLs are separate concerns this ADR does not need to resolve to
deliver one operational execution path.

### Introduce a unified exception root before implementation

Rejected. ADR-018 remains Deferred and this ADR does not change that. A
process boundary can translate existing exceptions to exit codes without
altering `CrawlerError`, `AACrawlerError`, or the unrelated `ValueError`
subclasses.

### Print structured log records to stdout

Rejected. Crawl result data is the only intended stdout content. Human-facing
lifecycle and error logs continue through the existing `aa_crawler` logger
hierarchy, which already writes to stderr by default.

### Add a dedicated use-after-close runtime exception for this work

Rejected. ADR-022 already left this unresolved and it is not required to ship
one operational command.

## Decision

### CLI ownership

A new `aa_crawler.cli` package owns the process entry point. It sits above
`aa_crawler.application` and `aa_crawler.bootstrap` and may depend on their
public APIs. Neither existing package depends on `aa_crawler.cli`.

The expected implementation location is conceptually:

```text
aa_crawler/cli/__init__.py   # argument parsing and public main()
aa_crawler/cli/app.py        # bootstrap → runtime → crawl → serialize → exit
```

This is an accepted architectural contract, not an implementation claim.

### Entry point

`[project.scripts]` continues to declare `aa-crawler = "aa_crawler:main"`.
`aa_crawler.__init__.main()` becomes a thin delegator into
`aa_crawler.cli`'s public entry function. This avoids an unreviewed change to
the protected `pyproject.toml` script declaration while still moving all CLI
behavior into its own package.

### Argument parsing

Standard-library `argparse` is the approved parsing technology for the
initial scope: one command accepting one URL. No new dependency is approved
by this ADR.

### Bootstrap and runtime sequence

The approved process sequence is:

```text
CLI
  → bootstrap_application()
  → create_application_runtime()   (used as a context manager)
  → ArticleCrawlService.crawl(url)
  → serialize result
  → stdout / process exit
```

`bootstrap_application()` and `create_application_runtime()` remain exactly as
defined by ADR-022: neither is extended, merged, or given new parameters by
this decision. The CLI calls both explicitly and owns no runtime resource
directly; `ApplicationRuntime`'s existing context-manager support guarantees
the owned `HttpClient` is closed on every exit path, including exceptions
raised during or after `crawl()`.

### Output contract

The initial approved output is one JSON object per invocation, printed to
stdout, representing the produced `CrawlerItem` tuple for the one requested
URL. This matches the existing single-URL `ArticleCrawlService.crawl()`
contract; no wrapper envelope, batch array, or JSON Lines format is approved
yet. `ArticleItem.to_dict()` output is already composed of JSON-safe values
for the shipped `jsonld_article` family, so no new serialization code is
required for that family; this ADR does not extend that serialization
guarantee to hypothetical future parser families, which remains an ADR-017
concern.

### Exit-code translation

The CLI owns one explicit, narrow exit-code translation table mapping
existing exceptions to process behavior:

- Success: the crawl returns normally.
- Unsupported or disabled source: `UnsupportedSourceError`.
- Other crawl-domain failure: any other `CrawlerError` subtype raised by
  acquisition, robots, source-boundary, or parsing components (for example
  `SourceBoundaryError`, `HtmlDisallowedError`, `RequestError`,
  `ResponseError`, `ArticleParserError`).
- Configuration or startup failure: `AACrawlerError` and its
  `ConfigurationError` subtypes raised by `bootstrap_application()` or during
  runtime construction.
- Unexpected failure: any other exception, including `ValueError` subclasses
  outside the two roots above (`SourceRegistryError`, `ParserCompositionError`)
  and standard-library exceptions that can escape runtime construction (for
  example `importlib.metadata.PackageNotFoundError`).

This table is an application-boundary translation implemented entirely inside
`aa_crawler.cli`. It does not change `CrawlerError`, `AACrawlerError`, or any
existing exception's inheritance, and it does not resolve ADR-018.

### Logging and stdout separation

The CLI logs crawl-lifecycle facts only — for example a started event, a
completed event with item count, or a failure category — at existing log
levels through the existing `aa_crawler` logger hierarchy. It must not log
request or response headers, cookies, credentials, full response bodies, or
raw metadata payloads, consistent with ADR-016 remaining unresolved on the
strength of the redaction guarantee. Crawl result data is reserved for
stdout; every log record continues to reach stderr through the existing
default console handler. The CLI sets one correlation ID per invocation using
the existing `observability.context` API so lifecycle logs remain
correlated without introducing new observability infrastructure.

### Security posture

The CLI must not print raw exception internals that could contain response
content, and must not add a bypass for source, robots, or identity
governance (no flag disables `SourceRegistry` lookup, robots evaluation, or
identity validation in this scope).

### Scope boundaries

This ADR approves exactly one synchronous, single-URL, JSON-emitting command
built on the existing application and runtime layers. It does not approve
batch/multi-URL processing, persistence, redirect traversal, alternate
execution runtimes, worker or queue architecture, or new production source
onboarding. None of those directions are blocked by this ADR; they remain
separate future decisions.

## Rationale

Every dependency this command needs already exists and is already tested:
`ApplicationRuntime` was built specifically to expose one application service
under explicit lifecycle ownership, and `bootstrap_application()` was already
proven independent of runtime composition. A thin CLI package that only calls
these two existing entry points, plus a narrow local exit-code translation,
delivers the first real operational execution path without introducing a new
dependency, without touching any lower-layer ownership boundary, and without
requiring any other accepted ADR to be revisited.

## Consequences

### Positive

- AA Crawler gains its first real user-facing execution path.
- `ArticleCrawlService`, `ApplicationRuntime`, identity reuse, source gates,
  and existing logging/redaction infrastructure are exercised by a real
  process for the first time.
- No new runtime dependency is introduced.
- No lower-layer constructor or ownership boundary changes.
- Exit-code behavior is explicit, narrow, and testable without changing the
  exception hierarchy.

### Negative

- Adds one new public package and its own testing surface.
- The exit-code table must be maintained by hand as new exception types are
  introduced elsewhere in the codebase; it is not automatically exhaustive.
- Remains synchronous and single-URL only; no batch ergonomics are provided.

### Neutral

- `bootstrap_application()` and `create_application_runtime()` behavior is
  unchanged.
- Source declarations, enablement, retry, robots, and parser semantics are
  unchanged.
- ADR-016, ADR-017, ADR-018, and ADR-019 statuses are unchanged.

## Compatibility implications

`aa_crawler.cli` is additive. It does not change any existing constructor,
`ArticleCrawlService`, `ApplicationRuntime`, or `bootstrap_application()`
signature. The `aa-crawler` console script keeps its current declared target;
only the behavior behind `aa_crawler.main()` changes, from a placeholder
greeting to a delegating call into the new package. Changing the output
format, exit-code categories, entry-point package, or CLI dependency choice
after implementation would alter this accepted contract and requires review.

## Testing implications

Implementation tests must verify:

- argument parsing for the approved single-URL command shape;
- the bootstrap-then-runtime sequence occurs in the approved order and the
  runtime is closed on every exit path, including failure paths;
- each exit-code category is reachable from its corresponding exception,
  including the unexpected/unmapped catch-all;
- stdout contains only the serialized result, never log output;
- no request/response headers, cookies, or bodies are logged; and
- no external network is required, using the same fake/guarded-transport
  patterns already established in `tests/integration/`.

## Relationship to existing decisions

- ADR-010 remains authoritative for constructor injection and explicit
  composition; the CLI composes existing public factories only.
- ADR-011 continues to govern provisional API boundaries; this ADR does not
  freeze `aa_crawler.cli` beyond that existing policy.
- ADR-014 and ADR-015 are unaffected; the CLI injects no identity or retry
  behavior of its own.
- ADR-016 remains Proposed; this ADR imposes a conservative logging policy
  without resolving the underlying redaction guarantee.
- ADR-017 remains Deferred; the CLI's JSON output relies on the current
  in-process serialization behavior of the shipped parser family and creates
  no new portability promise.
- ADR-018 remains Deferred; this ADR is the response to ADR-018's own
  "CLI failure handling" review trigger, and it resolves that trigger through
  a local translation table rather than a taxonomy change.
- ADR-019 remains Proposed and is unrelated; the CLI is synchronous only.
- ADR-020, ADR-021, and ADR-022 remain fully authoritative and unchanged;
  the CLI calls their public contracts without altering source governance,
  application orchestration, or runtime composition.

## Follow-up work

- Implement `aa_crawler.cli` per the approved sequence, output contract, and
  exit-code table.
- Add focused unit tests and one synthetic, network-isolated CLI integration
  test.
- Update Engineering Standards and README only after implementation is
  verified.

## Review triggers

- Multi-URL batch input or JSON Lines output is proposed.
- A CLI dependency beyond `argparse` is proposed.
- The exit-code table needs a new category outside the approved roots.
- Redirect support, persistence, or an alternate execution runtime is
  approved and needs CLI-surfaced behavior.
- ADR-016, ADR-017, or ADR-018 status changes in a way that affects CLI
  logging, output portability, or error handling.
