# ADR-020 — Declarative Source Architecture

- Status: Accepted
- Date: 2026-08-10
- Decision owners: Source owner, Parser owner, Tech Lead
- Related ADRs: ADR-002, ADR-007, ADR-010, ADR-011, ADR-014, ADR-015, ADR-019

## Context

Sprint 4 introduced the first production source declarations without creating
one parser class per publisher. News sites that expose compatible article
metadata need a low-cost onboarding path, while source ownership, operational
enablement, and parser construction must remain explicit and reviewable.

The implemented source-composition flow is:

```text
URL
  ↓
SourceRegistry
  ↓
SourceProfile
  ↓
ParserComposer
  ↓
JsonLdArticleParser
  ↓
ArticleItem
  ↓
CrawlerItem
```

This flow assumes that an `HtmlDocument` has already been acquired. It is not
the full application-level URL-to-network-acquisition-to-parsed-article
orchestrator. That orchestration boundary remains future work.

## Decision drivers

- Cheap onboarding for structurally compatible sources
- Reuse of source-agnostic parsing behavior
- Exact, auditable hostname ownership
- Explicit source enablement governance
- Deterministic construction and testability
- No hidden lifecycle or mutable global registry
- No premature plugin or adapter system
- A profile model that can scale to large source collections

## Considered options

### One parser class per source

Rejected as the default. It duplicates behavior for schema-compatible
publishers and does not scale as an ordinary-source onboarding model.
Source-specific behavior remains possible only after observed evidence shows
that the generic parser is insufficient.

### Dynamic plugins or reflection

Rejected for Sprint 4. Arbitrary import paths, reflection, `importlib`, entry
points, runtime plugin scanning, and arbitrary callable injection add loading,
security, lifecycle, and debugging complexity before a demonstrated need.

### Global mutable registry

Rejected because it introduces hidden construction, mutation, and test-order
dependencies. Registry construction stays explicit at the application
composition boundary.

### Wildcard or suffix domain matching

Rejected because it weakens technical and governance boundaries. Parent domains
must not implicitly authorize child domains, and child declarations must not
authorize their parent or siblings.

### Configuration files as the primary profile source

Deferred. Static Python declarations are appropriate for the initial small
profile set. External configuration or database loading may be reconsidered
when profile volume or operational ownership requires it.

### Immediate custom adapter API

Deferred until real source evidence requires source-specific behavior. A
reserved declarative key does not justify a loader, registry, or plugin API.

## Decision

Represent source-specific knowledge with immutable `SourceProfile` values,
resolve those profiles through an explicitly constructed `SourceRegistry`, and
construct parsers through a stateless `ParserComposer` with a closed,
reviewable parser-family mapping.

### SourceProfile responsibility

`SourceProfile` owns only:

- a stable source identifier;
- an explicit ordered hostname boundary;
- a constrained parser family;
- an optional inert adapter key; and
- an enabled state.

It remains immutable and declarative. It owns no HTTP or network behavior,
parser instance, dynamic loading, arbitrary runtime metadata, source discovery,
or operational lifecycle.

### Exact-host ownership

Every permitted hostname must be declared explicitly. The architecture does
not support wildcard domains, suffix matching, implicit parent-domain
inheritance, or automatic child-subdomain authorization.

Exact hosts are both a technical safety boundary and a governance boundary.
A source may own a parent and a subdomain only when each hostname is listed.

### SourceRegistry responsibility

`SourceRegistry` is the authoritative immutable mapping from:

- exact source identifier to `SourceProfile`;
- exact normalized hostname to `SourceProfile`; and
- safe absolute HTTPS URL to `SourceProfile` through its exact hostname.

The registry eagerly consumes and validates its input once, rejects duplicate
source identifiers and duplicate hostname ownership, preserves constructor
order and exact profile instances, and exposes read-only indexes indirectly
through lookup methods. It performs no network access, parser construction, or
adapter loading. It is not a crawler.

### Enabled and disabled governance

Profile existence does not authorize operational crawling.

- `enabled=True` makes a profile available through normal runtime lookup.
- `enabled=False` retains a known declaration for explicit inspection, excludes
  it from normal lookup, and requires `ParserComposer` to reject it.

`include_disabled=True` is an explicit inspection mechanism, not operational
authorization. Enabled state is an application governance control; it does not
replace robots.txt compliance, publisher-policy review, legal review,
operational rate limits, or network-level safety controls.

### Parser families

The accepted Sprint 4 parser family is exactly `jsonld_article`, mapped
statically to `JsonLdArticleParser`. Parser-family mapping is closed, explicit,
and reviewable. It does not use arbitrary import paths, reflection, dynamic
imports, entry points, plugin scanning, or caller-provided factories.

`JsonLdArticleParser` remains source-agnostic. It receives the source identifier
and all approved exact domains through composition and contains no
publisher-specific branches.

### ParserComposer responsibility

`ParserComposer` owns parser construction only. It receives an enabled
`SourceProfile`, maps `parser_family` explicitly, propagates the source and all
approved domains, and returns a new parser instance for each `create()` call.
It rejects disabled profiles and non-null adapter keys.

It remains stateless and performs no source lookup, URL discovery, network
access, adapter loading, or registry responsibility. `SourceRegistry` lookup
and `ParserComposer` construction remain separate operations.

### Adapter key

`adapter_key` is a reserved declarative seam. Sprint 4 supports only `None` at
composition time. A non-null value is validated as data by `SourceProfile` but
rejected by `ParserComposer`. No adapter registry, custom adapter API, dynamic
loader, fallback, or plugin mechanism exists.

### Ordinary-source onboarding

The default path for a structurally compatible source is:

1. Add one reviewed `SourceProfile` declaration.
2. Include it in the explicit profile collection.
3. Reuse the `jsonld_article` parser family.

A different publisher name alone is not a reason to create a source-specific
parser. Custom parser or adapter behavior requires observed evidence that the
generic parser cannot represent the source safely.

### Default profile collection

`DEFAULT_SOURCE_PROFILES` is an immutable, deterministic, explicitly ordered
tuple of plain immutable `SourceProfile` values. Importing it does not construct
a global `SourceRegistry`. Runtime registry construction remains explicit at
the application composition boundary.

## Initial production profile state

Sprint 4 records the following project governance state without claiming legal
permission or broader host authorization.

### CNN Indonesia

- Source: `cnn_indonesia`
- Exact domain: `www.cnnindonesia.com`
- Parser family: `jsonld_article`
- Adapter key: `None`
- Enabled: `True`

### Kompas

- Source: `kompas`
- Exact domains:
  - `www.kompas.com`
  - `nasional.kompas.com`
  - `surabaya.kompas.com`
- Parser family: `jsonld_article`
- Adapter key: `None`
- Enabled: `False`

No other Kompas hostname is authorized implicitly. CNN's enabled state and
Kompas's disabled state record current project governance only.

## Integration evidence

Sprint 4 synthetic integration tests validate:

```text
URL
  → SourceRegistry
  → SourceProfile
  → ParserComposer
  → JsonLdArticleParser
  → ArticleItem
  → CrawlerItem
```

They cover enabled CNN composition, disabled Kompas behavior, exact-host
boundaries, an ordinary synthetic source using the same generic flow,
deterministic repeated construction, immutable output, and safe parser failure.

The tests intentionally do not instantiate `HttpClient`, `RobotsPolicy`, or
`HtmlFetcher`. They validate source composition from a synthetic `HtmlDocument`,
not full network acquisition.

## Rationale

Most schema-compatible sources differ in identity and approved host boundary,
not parsing algorithm. Declarative profiles keep those differences as data,
while exact-host registry lookup and explicit parser construction provide
separate, narrow responsibilities. This supports large source collections
without introducing hundreds of duplicate parser classes or an unneeded plugin
runtime.

## Consequences

### Positive

- Ordinary source onboarding requires one small reviewed declaration.
- Generic parser behavior is reused consistently.
- Lookup and composition are deterministic and independently testable.
- Exact domains provide a strong technical and governance boundary.
- Enabled state makes operational participation explicit.
- No dynamic plugin loading or mutable global registry is required.
- Immutable indexed lookup scales to large profile collections.

### Negative

- Static production declarations require code changes and review.
- Enabled/disabled is a coarse-grained governance state.
- Source-specific adapter behavior is unavailable.
- Parser-family mapping is intentionally closed.
- Live profile configuration reload is not provided.

### Neutral

- Runtime reload would construct a new registry rather than mutate one.
- The source-profile API remains provisional through early operational
  crawling under ADR-011.
- Profile enablement does not supersede robots, publisher-policy, legal,
  rate-limit, or network-safety controls.
- Full acquisition orchestration remains outside this composition flow.

## Compatibility implications

Callers may rely on exact-host matching, disabled-by-default lookup behavior,
explicit registry construction, and new parser instances per composition.
Adding wildcard semantics, mutable reload, dynamic adapters, or a new parser
family changes observable architecture and requires review. Static profile
contents and provisional composition seams are not frozen beyond ADR-011's
current policy.

## Follow-up work

- Design the application-level acquisition and source-composition orchestrator
  when operational crawling is scheduled.
- Keep source approval evidence and enablement decisions reviewable.
- Revisit external profile storage or adapters only when a review trigger
  demonstrates the need.

## Relationship to existing decisions

- ADR-014 owns outbound `RequestIdentity`; ADR-020 does not redefine identity.
- ADR-015 owns HTTP retry idempotency; ADR-020 does not redefine transport
  attempts.
- ADR-019 remains the decision area for async, browser, and alternate execution
  families.
- ADR-002, ADR-007, ADR-010, and ADR-011 continue to govern immutability, parser
  lifecycle, constructor injection, and provisional API boundaries.

## Review triggers

- Hundreds or thousands of profiles create operational maintenance pressure.
- Profiles must be loaded from external configuration or a database.
- Runtime profile reload is required.
- A real publisher requires custom parser or adapter behavior.
- Multiple parser families are implemented.
- Async or browser acquisition families are introduced.
- Source ownership requires wildcard or pattern semantics.
- Governance requires richer states than enabled or disabled.
- Distributed workers require serialized profile configuration.
