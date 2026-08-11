# ADR-022 — Application Runtime Composition and Resource Ownership

- Status: Accepted
- Date: 2026-08-11
- Decision owners: Application owner, Runtime owner, Tech Lead
- Related ADRs: ADR-003, ADR-004, ADR-005, ADR-010, ADR-014, ADR-015,
  ADR-016, ADR-017, ADR-018, ADR-019, ADR-020, ADR-021

## Context

ADR-021 established `ArticleCrawlService` as the synchronous application
use-case coordinator and assigned construction and `HttpClient` lifecycle to an
external application composition root. The service, its application errors,
and synthetic integration verification are now implemented. The concrete
composition-root abstraction and resource-ownership model remain unresolved.

The current `bootstrap_application()` contract is already implemented and
tested. It loads one frozen `ApplicationSettings`, prepares runtime
directories, configures logging, and returns that same settings instance. It
does not construct crawler runtime dependencies or own network resources.

`HttpClient` owns a reusable synchronous HTTPX client. It exposes `close()` and
synchronous context-manager methods. Current locked-runtime behavior permits a
second close without additional effect, while use after close surfaces the
underlying runtime failure. `RobotsPolicy`, `HtmlFetcher`, and
`ArticleCrawlService` retain and use the client graph but do not close it.

`RequestIdentity` requires an explicit validated product version and
intentionally performs no package-metadata lookup. The installed project
metadata currently exposes the distribution name `aa-crawler`; the repository
does not expose a package `__version__`.

This ADR accepts the concrete lifecycle architecture. `ApplicationRuntime` and
`create_application_runtime()` are planned APIs for a later Sprint 5
implementation task. Neither exists at the time of this decision.

## Decision drivers

- One explicit and auditable owner for network resources
- Guaranteed cleanup after successful and partially failed construction
- One consistent request identity across robots and page acquisition
- Preservation of established subsystem responsibilities
- Compatibility with the existing bootstrap contract
- No global mutable runtime, hidden singleton, or service locator
- Deterministic network-free lifecycle testing
- A narrow public application surface

## Considered options

### Factory returning only ArticleCrawlService

Rejected. The returned service intentionally does not own or expose the
underlying `HttpClient`. A caller receiving only the service would have no
explicit lifecycle owner through which to release that client safely.

### Extend or replace bootstrap_application()

Rejected. `bootstrap_application()` has an established settings and startup
contract. Changing its return type or combining it with resource composition
would unnecessarily couple configuration, directory preparation, logging, and
network-resource lifetime.

### Generic dependency container or service locator

Rejected. A public mapping or lookup-based container would expose lower-level
implementation details, permit dependencies to be requested opportunistically,
and weaken constructor and lifecycle ownership.

### Global runtime or default application service

Rejected. Module-level construction hides resource acquisition, creates
import-time side effects, complicates tests, and introduces mutable process
state and ambiguous cleanup.

### Let a dependent component close HttpClient

Rejected. `ArticleCrawlService`, `RobotsPolicy`, and `HtmlFetcher` use the same
client graph but cannot know whether another dependent still needs it. Cleanup
would become order-dependent and could occur more than once through different
owners.

### Hidden policy and identity construction

Rejected. Separate identities risk inconsistent robots and page acquisition.
Implicit policy or version choices make the runtime graph difficult to audit.
Metadata must not become a policy or identity configuration channel.

### Pass unused ApplicationSettings into the runtime factory

Rejected. Current settings do not define request identity, timeout, retry,
source, or parser-composition values. Accepting settings without using an
approved field creates premature coupling.

### Synchronous ApplicationRuntime with explicit lifecycle

Accepted. A narrow runtime exposes one application use case while retaining one
private, deterministic cleanup owner for the complete synchronous graph.

## Decision

### Runtime abstraction

The application runtime is represented by a narrow synchronous
`ApplicationRuntime` abstraction created through
`create_application_runtime()`.

The runtime is the explicit lifecycle owner for resources constructed by the
application composition root. It owns resource lifetime, not subsystem
behavior.

These are accepted planned APIs. This ADR does not implement them.

### Public runtime surface

The planned public surface is:

```text
ApplicationRuntime
├── article_crawl_service
├── close()
├── __enter__()
└── __exit__()
```

Only `ArticleCrawlService` is exposed as the application use-case entry point.
The runtime must not expose a dependency dictionary, arbitrary lookup API,
mutable registration method, or every composed collaborator.

`ApplicationRuntime` must not become a generic service locator, dependency
registry, mutable container, global singleton, or hidden default runtime.

### Public package ownership

The runtime composition API belongs to `aa_crawler.application`. The expected
implementation location is conceptually:

```text
aa_crawler/application/runtime.py
```

When implementation lands, `aa_crawler.application` may explicitly export:

- `ApplicationRuntime`
- `create_application_runtime`

No package export changes are made by this ADR.

### Separation from bootstrap_application()

`bootstrap_application()` remains unchanged. It continues to:

1. load `ApplicationSettings`;
2. prepare runtime directories;
3. configure logging; and
4. return the same frozen settings instance.

`create_application_runtime()` separately constructs the application
dependency graph and owns its resource lifetime. It must not extend, replace,
or change the return type of `bootstrap_application()`.

Expected application usage keeps both phases explicit:

```python
settings = bootstrap_application(base_dir=base_dir)

with create_application_runtime() as runtime:
    items = runtime.article_crawl_service.crawl(url)
```

The settings value remains available to the caller even though the initial
runtime factory does not consume it.

### Dependency graph

The composition root explicitly constructs this graph:

```text
RequestIdentity ───────────────┬─→ RobotsPolicy ─┐
                               └─────────────────┼─→ HtmlFetcher ─┐
TimeoutPolicy ─┐                                 │                 │
RetryPolicy ───┼─→ HttpClient ──────────────────┘                 │
               │                                                   │
SourceRegistry ────────────────────────────────────────────────────┼─→ ArticleCrawlService
ParserComposer ────────────────────────────────────────────────────┘
```

Existing ownership remains authoritative:

- `HttpClient` owns HTTP execution behavior.
- `RetryPolicy` owns retry semantics.
- `RobotsPolicy` owns robots decisions and its per-instance cache.
- `HtmlFetcher` owns robots-aware HTML acquisition.
- `SourceRegistry` owns exact-host source lookup and enablement filtering.
- `ParserComposer` owns parser construction.
- `ArticleCrawlService` owns application use-case coordination only.
- `ApplicationRuntime` owns resource lifecycle only.

### RequestIdentity ownership

Construct exactly one `RequestIdentity` for each `ApplicationRuntime`. Inject
that same exact instance into `RobotsPolicy` and `HtmlFetcher`.

`HtmlFetcher` remains responsible for validating identity compatibility with
its `RobotsPolicy`. `RequestIdentity` is not injected into `HttpClient`, and
separate robots and page-acquisition identities are prohibited.

### Product version source

The composition root resolves the identity product version with:

```python
importlib.metadata.version("aa-crawler")
```

The distribution name is exactly `aa-crawler`. Version resolution occurs
before `HttpClient` creation. The runtime must not hardcode a duplicate version
such as `0.1.0`, add `__version__` solely for this purpose, or invent a fallback
version.

Supported application execution occurs from an installed or uv-managed project
environment where distribution metadata is available. If it is unavailable,
runtime construction fails before acquiring network resources.

### Timeout and retry policy construction

The composition root explicitly constructs:

```python
TimeoutPolicy()
RetryPolicy()
```

and passes both objects to `HttpClient`. This makes policy ownership visible
while preserving the existing default values. Retry decisions remain entirely
inside `RetryPolicy` and `HttpClient`; metadata cannot control retry behavior.

### HttpClient ownership

Exactly one `ApplicationRuntime` owns the `HttpClient` created for that runtime.
`ArticleCrawlService`, `RobotsPolicy`, and `HtmlFetcher` must never close it.

`ApplicationRuntime` provides `close()` and synchronous context-manager
support. No async lifecycle is introduced.

### Construction and cleanup strategy

`contextlib.ExitStack` is the preferred private ownership mechanism. The
planned construction order is:

1. Resolve the installed package version.
2. Construct `RequestIdentity`.
3. Construct `TimeoutPolicy`.
4. Construct `RetryPolicy`.
5. Construct `SourceRegistry(DEFAULT_SOURCE_PROFILES)`.
6. Construct `ParserComposer`.
7. Create and enter `HttpClient` into a temporary private `ExitStack`.
8. Construct `RobotsPolicy`.
9. Construct `HtmlFetcher`.
10. Construct `ArticleCrawlService`.
11. Transfer the owned cleanup stack into `ApplicationRuntime`.

Equivalent implementation details are permitted only when they preserve the
same single-owner and failure-cleanup guarantees.

### Partial-construction failure

If any step fails after `HttpClient` creation:

- the owned client is closed;
- the original construction exception propagates;
- partially built runtime state does not escape; and
- no global state remains.

This guarantee includes failures such as `HtmlFetcher` rejecting inconsistent
identity wiring. Cleanup must not silently convert construction failure into a
partially usable runtime.

### Close semantics

`ApplicationRuntime` close behavior is:

- the first `close()` releases all owned resources;
- a second `close()` is safe and has no additional effect;
- `__exit__()` calls `close()`; and
- cleanup has exactly one runtime owner.

Use after close is unsupported. This ADR does not introduce an
application-specific use-after-close exception. Current downstream
`HttpClient` behavior may surface its existing `RuntimeError`.

### SourceRegistry lifecycle

Construct `SourceRegistry(DEFAULT_SOURCE_PROFILES)` once per runtime. The
registry remains immutable, runtime-local, non-global, and without reload
semantics.

Declarative profile constants may be reused safely as constructor inputs. The
runtime does not modify profile enablement or turn enablement into legal,
publisher-policy, robots, rate-limit, or operational authorization.

### ParserComposer lifecycle

Construct one `ParserComposer` per runtime. It remains stateless, reusable, and
resource-free and requires no explicit cleanup.

### ArticleCrawlService lifecycle

Construct one `ArticleCrawlService` per runtime using the runtime-local:

- `SourceRegistry`;
- `HtmlFetcher`; and
- `ParserComposer`.

The service remains reusable for sequential synchronous operations. It does not
construct or close dependencies, own `HttpClient`, or own the
`RequestIdentity` lifecycle.

### Configuration relationship

`create_application_runtime()` initially receives no `ApplicationSettings`.
Current settings define no runtime identity, timeout, retry, source, or parser
composition configuration.

Future approved settings may be translated by the composition root into narrow
policy or domain objects. Lower-level packages must not become aware of the
configuration model solely to support composition.

### Runtime independence

Multiple `ApplicationRuntime` instances are independent and share no mutable
runtime state. Each runtime receives its own:

- `RequestIdentity`;
- `HttpClient`;
- `RobotsPolicy`;
- `HtmlFetcher`;
- `SourceRegistry`;
- `ParserComposer`; and
- `ArticleCrawlService`.

Existing immutable constants and declarative profile definitions may be reused
as safe inputs. No hidden singleton or global runtime is introduced.

### Concurrency scope

The runtime is synchronous and makes no thread-safety guarantee. This ADR does
not introduce asyncio, async context managers, browser execution, worker pools,
schedulers, queues, or distributed execution. ADR-019 remains authoritative
for future alternate execution families.

## Rationale

A narrow context-managed runtime makes resource ownership visible without
turning application coordination into infrastructure management. The runtime
can expose the single supported use case while privately retaining cleanup for
the shared transport graph. Resolving version metadata and constructing
non-resource dependencies before the client minimizes partial-construction
risk; `ExitStack` then provides deterministic transfer and cleanup of the sole
resource-owning client.

Keeping bootstrap and runtime composition separate preserves established
startup compatibility and avoids coupling lower-level services to settings they
do not use.

## Security and safety considerations

Explicit runtime composition:

- prevents hidden network-client ownership;
- prevents separate robots and page-acquisition identities;
- makes acquisition and cleanup auditable;
- keeps metadata from controlling identity or retry policy; and
- avoids global mutable runtime state.

Runtime composition does not itself grant legal authorization, publisher
permission, robots compliance, rate limiting, source enablement approval, or a
broader security guarantee. Existing subsystem and governance owners remain
authoritative for those concerns.

## Consequences

### Positive

- The complete dependency graph is explicit.
- Exactly one runtime owns transport cleanup.
- Context-manager usage is deterministic and familiar.
- Partial-construction failure closes acquired resources.
- Runtime instances remain independent and testable.
- No hidden global or service locator is introduced.
- Existing bootstrap behavior remains compatible.
- Runtime tests can remain synthetic and network-free.

### Negative

- One additional public runtime abstraction is introduced.
- Construction requires installed distribution metadata.
- The lifecycle remains synchronous only.
- Focused construction and cleanup tests are required.
- Use after close remains unsupported without a dedicated application error.

### Neutral

- Lower-level package ownership remains unchanged.
- `ArticleCrawlService` behavior remains unchanged.
- Source declarations and enablement remain unchanged.
- Retry, robots, acquisition, parser, and canonical semantics remain unchanged.
- `bootstrap_application()` continues returning settings.

## Compatibility implications

When implemented, callers may rely on `ApplicationRuntime` as the sole owner of
the resources it creates, idempotent close behavior, synchronous context
management, and access to one `article_crawl_service` entry point.

The runtime API will be additive. It does not change existing constructors,
`ArticleCrawlService`, or `bootstrap_application()`. Changing ownership,
version resolution, public service exposure, or close semantics requires
review.

## Testing implications

Implementation tests must verify:

- every dependency is constructed once per runtime;
- the same exact identity instance reaches robots and HTML acquisition;
- the service receives the composed registry, fetcher, and parser composer;
- `HttpClient` closes on context exit;
- explicit close is idempotent;
- failure after client construction closes the client;
- the original construction error propagates;
- partially constructed state does not escape;
- multiple runtimes remain independent;
- no global runtime state appears;
- installed package metadata supplies the product version;
- no external network is required; and
- `bootstrap_application()` behavior and return contract remain unchanged.

Tests should use controlled fakes or mock transport and must not rely on live
publisher access.

## Relationship to existing decisions

- ADR-021 remains authoritative for `ArticleCrawlService` orchestration,
  source gates, parsing order, output, and application errors.
- ADR-022 governs the concrete composition-root and resource-lifecycle model
  that ADR-021 intentionally left unresolved. Neither ADR supersedes the other.
- ADR-014 remains authoritative for request identity and User-Agent
  propagation.
- ADR-015 remains authoritative for retry eligibility and idempotency.
- ADR-020 remains authoritative for declarative profiles, source lookup, and
  parser composition.
- ADR-016 and ADR-019 remain Proposed.
- ADR-017 and ADR-018 remain Deferred.

## Follow-up work

- Implement `ApplicationRuntime` and `create_application_runtime()` in
  `aa_crawler.application`.
- Add focused construction, cleanup, version-resolution, and independence
  tests.
- Add network-free integration verification for the complete runtime graph.
- Update Engineering Standards and user documentation only after the runtime
  implementation is verified.

## Review triggers

- An async application runtime is proposed.
- Browser execution is introduced.
- Multiple resource-owning transports are required.
- Runtime policies become configurable.
- Source-registry reload is introduced.
- A plugin runtime or dependency-injection framework is proposed.
- Long-running workers, schedulers, or queues own runtime lifecycles.
- Thread-safety guarantees become necessary.
- The installed-distribution metadata strategy changes.
- The runtime must publicly expose multiple application use-case services.
