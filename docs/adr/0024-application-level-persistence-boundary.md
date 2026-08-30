# ADR-024 — Application-Level Persistence Boundary for Crawl Results

- Status: Accepted
- Date: 2026-08-30
- Decision owners: Application owner, Persistence owner, Tech Lead
- Related ADRs: ADR-010, ADR-017, ADR-020, ADR-021, ADR-022, ADR-023

## Context

Sprint 6 closed the question "how can the existing crawler application
actually be executed by a user?" with an operational CLI (ADR-023): one
synchronous invocation produces one JSON object on stdout, then the process
exits and that result is gone. Sprint 7 Task 7.1 (read-only architecture
discovery) evaluated seven candidate directions against repository evidence
and found that a persistence boundary is the only candidate with no unmet
architectural prerequisite, genuine current value (crawled data currently has
no outcome beyond one process's stdout), and a directly implicated,
already-waiting decision: ADR-017 (Metadata and Item Portability, Deferred)
explicitly names "persistence... or stable item schemas" as one of its own
review triggers.

`CrawlerItem.data` is a `Mapping[str, object]` with no type-level portability
guarantee; `ArticleItem.to_dict()` produces fully JSON-safe values for the
currently shipped `jsonld_article` parser family only — this is the exact
same assumption the CLI already relies on for its stdout contract (ADR-023),
verified empirically in Sprint 6.

This ADR accepts the architecture for an application-level persistence
boundary. Neither a concrete port type, a concrete sink implementation, nor
any database technology exists at the time of this decision; those remain
narrowly scoped implementation work for a later Sprint 7 task.

## Decision drivers

- Give crawled article data a durable outcome beyond one process's stdout
- Preserve every established subsystem owner unchanged
- Answer ADR-017's "persistence" review trigger narrowly, without resolving
  its full portability policy
- Avoid premature database or schema selection
- Keep the CLI and `ArticleCrawlService` storage-agnostic
- Enable deterministic, network-free persistence tests

## Considered options

### Persist inside `ArticleCrawlService`

Rejected. ADR-021 scoped `ArticleCrawlService` to source gates, acquisition
sequencing, parser composition, and output only. Adding storage there would
silently widen an already-accepted, narrow use-case boundary.

### Persist inside `ApplicationRuntime`

Rejected. ADR-022 scoped the runtime to resource lifecycle (identity,
transport, robots, fetcher, registry, composer, service) only. Persistence is
a data-output concern, not a runtime resource, and does not belong in that
graph.

### Persist inside `aa_crawler.cli`

Rejected. ADR-023 explicitly scoped the CLI to argument parsing, invocation
sequencing, and stdout serialization only. Coupling the thin process boundary
to storage would duplicate responsibility and violate its accepted
single-purpose design.

### Fully resolve ADR-017's portability policy now

Rejected. No real multi-parser-family, plugin, or distributed-execution
requirement exists yet to justify a universal schema decision. ADR-017
remains Deferred for that broader question; this ADR answers only its
narrow "persistence" trigger for the one parser family currently shipped.

### Select a database or ORM immediately

Rejected. No operational evidence (volume, query patterns, retention
requirements) exists yet to justify a specific storage technology.

### Defer persistence entirely

Rejected. Task 7.1's evidence-based discovery found this to be the most
valuable, best-supported next architectural gap among all evaluated
candidates, with no unmet prerequisite.

## Decision

### Persistence ownership

A new, narrow, optional collaborator — conceptually a persistence port — owns
writing one crawl result to durable storage. It is not owned by
`ArticleCrawlService`, `ApplicationRuntime`, or `aa_crawler.cli`; it is
composed explicitly by whatever caller already holds a `CrawlerItem`. The
expected implementation location is conceptually:

```text
aa_crawler/persistence/
├── __init__.py   # public port protocol and its exact exported surface
└── ...           # one minimal concrete sink (exact shape decided in Task 7.3)
```

This is an accepted architectural contract, not an implementation claim. The
concrete sink technology (for example, a local file-based writer) is
deliberately left open for the following implementation task and is not
locked by this ADR.

### Serialization contract

The persistence port consumes `CrawlerItem.data` converted to a plain `dict`,
exactly as `aa_crawler.cli.app.run_crawl()` already does before
`json.dumps(...)`. This reuses today's proven JSON-safe assumption for the
currently shipped `jsonld_article` parser family only. This ADR does not
create a new serialization guarantee for hypothetical future parser families
and does not resolve ADR-017's full portability policy — it narrowly answers
ADR-017's "persistence" trigger for this one case, the same way ADR-023
narrowly answered ADR-018's "CLI failure handling" trigger without resolving
that taxonomy.

### Idempotency

Not guaranteed in this initial scope. Repeated persistence of the same URL
may duplicate or overwrite a prior result depending on the concrete sink.
This is an explicit, deliberately deferred open question — not a silently
ignored one — and must be resolved before any job/worker architecture is
built on top of this boundary.

### CLI independence

`aa_crawler.cli` remains entirely unaware of persistence under this ADR: no
new flag, no automatic write-through, no import of the persistence package.
This preserves ADR-023's thin-process-boundary discipline. CLI-triggered
persistence is explicitly out-of-scope future work requiring its own review.

### Application/runtime independence

`ArticleCrawlService` and `ApplicationRuntime` are not modified by this ADR.
Persistence is invoked by a caller that already holds a produced
`CrawlerItem`; it is not part of the dependency graph `create_application_
runtime()` composes. This preserves ADR-021 and ADR-022's ownership
boundaries unchanged.

### Optionality

Persistence must remain fully optional. The existing crawl flow — CLI,
`ArticleCrawlService`, `ApplicationRuntime` — must behave identically whether
or not a persistence collaborator is ever composed anywhere.

### Non-goals

This ADR does not select a database or storage technology, does not design a
schema or versioning system, does not add a CLI flag or any CLI wiring, does
not introduce worker/queue/scheduler architecture, and does not resolve
ADR-017's full portability policy.

## Rationale

A narrow, optional, explicitly-owned persistence port closes the "crawled
data currently evaporates" gap identified by Task 7.1 without disturbing any
accepted ownership boundary (ADR-021, ADR-022, ADR-023), without prematurely
committing to a database or schema, and without coupling the CLI to storage.
Reusing the CLI's own already-proven JSON-safe assumption keeps the narrow
scope internally consistent with recent, verified architecture rather than
inventing a new one.

## Consequences

### Positive

- Crawled data can outlive one process invocation.
- No existing subsystem's ownership boundary is disturbed.
- ADR-017's persistence trigger is answered narrowly, without a wholesale
  portability-policy change.
- The CLI remains simple, storage-agnostic, and independently testable.

### Negative

- Adds one new package and its own testing surface.
- Idempotency remains unresolved; a later decision must address it before
  any job/worker architecture depends on this boundary.
- The narrow serialization contract must be revisited if a second parser
  family with a different output shape is ever introduced.

### Neutral

- `ArticleCrawlService`, `ApplicationRuntime`, and `aa_crawler.cli` behavior
  is unchanged.
- Source declarations, enablement, retry, robots, and parser semantics are
  unchanged.
- ADR-016, ADR-017 (broader policy), ADR-018, and ADR-019 statuses are
  unchanged.

## Compatibility implications

This ADR is additive only. No existing constructor, public contract, or
runtime graph changes. Adding a stronger cross-parser-family portability
guarantee, CLI-triggered persistence, or a concrete idempotency guarantee
would each alter this accepted contract and requires review.

## Testing implications

Implementation tests must verify: the persistence port is fully optional and
the existing crawl flow is unaffected when no persistence collaborator is
composed; the concrete sink correctly serializes `CrawlerItem.data` for the
shipped parser family; no test contacts a real network or depends on
wall-clock or other external state; and `ArticleCrawlService`,
`ApplicationRuntime`, and `aa_crawler.cli` remain unmodified by this work.

## Relationship to existing decisions

- ADR-010 remains authoritative for constructor injection and explicit
  composition; persistence is composed explicitly by its caller, never
  globally.
- ADR-017 remains Deferred for its full portability policy; this ADR
  narrowly answers only its "persistence" review trigger, for the currently
  shipped parser family.
- ADR-020 remains authoritative and unrelated; source governance is
  untouched.
- ADR-021 remains authoritative; `ArticleCrawlService`'s sequence and
  ownership are unchanged.
- ADR-022 remains authoritative; `ApplicationRuntime`'s resource graph is
  unchanged — persistence is not part of it.
- ADR-023 remains authoritative; the CLI's thin process-boundary scope is
  unchanged and remains unaware of persistence.
- ADR-016, ADR-018, and ADR-019 are unrelated and unchanged.

## Follow-up work

- Implement the persistence port and one minimal concrete sink.
- Add focused and integration tests proving optionality and network
  isolation.
- Update Engineering Standards and README only after implementation is
  verified.
- Consider CLI-triggered persistence and a concrete idempotency guarantee
  only as later, separately-approved work.

## Review triggers

- A second parser family with a different output shape is introduced.
- Real operational use reveals a concrete idempotency requirement.
- CLI-triggered persistence is proposed.
- A database or schema technology needs selecting for real deployment.
- Worker, queue, or scheduler work is scheduled and needs durable state.
