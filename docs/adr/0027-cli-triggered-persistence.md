# ADR-027 — CLI-Triggered Persistence

- Status: Accepted
- Date: 2026-09-06
- Decision owners: Application owner, Persistence owner, Tech Lead
- Related ADRs: ADR-010, ADR-017, ADR-018, ADR-023, ADR-024

## Context

ADR-023 gave `aa_crawler.cli` a deliberately thin process boundary: one
positional URL, one crawl, one JSON object on stdout, and a small,
CLI-local exit-code mapping. ADR-024 gave the project an optional
application-level persistence port (`aa_crawler.persistence`), explicitly
scoped so that neither `ArticleCrawlService`, `ApplicationRuntime`, nor
`aa_crawler.cli` would import or construct it — "CLI-triggered persistence
is explicitly out-of-scope future work requiring its own review" (ADR-024)
and "redirect/persistence/alternate-runtime CLI exposure" is one of
ADR-023's own listed review triggers.

The project owner's stated goal is an engine usable across many online
news sources, running toward real-time operation. Sprint 10 Task 10.1
(read-only architecture discovery) found a concrete gap standing in the
way of that goal: the CLI prints one result to stdout and exits — nothing
is ever durably saved unless a caller writes their own Python code against
`aa_crawler.persistence` directly. `tests/persistence/test_optionality.py`
today asserts, by static `ast` inspection, that `aa_crawler.cli.app`
imports nothing from `aa_crawler.persistence`; this ADR is the explicit,
reviewed decision to relax that specific assertion for `aa_crawler.cli.app`
only, exactly as ADR-024 anticipated.

This ADR governs only the mechanism connecting the two existing pieces. It
does not select a database, does not add a second concrete sink, does not
add batch/multi-URL input, does not resolve idempotency, and authorizes no
change to which sources are enabled or how they are acquired.

## Decision drivers

- Close the "crawled data currently evaporates when run via the CLI" gap
  identified by Task 10.1, without duplicating Sprint 7's persistence work
- Preserve default CLI behavior (no flag) exactly as it is today — this is
  the single most important compatibility constraint
- Reuse the existing `FileCrawlResultSink` exactly as built; do not design
  a new sink, a sink-selection mechanism, or a factory
- Keep the CLI's exit-code mapping small, explicit, and deterministic, per
  ADR-023
- Do not resolve ADR-024's open idempotency question or ADR-018's deferred
  error-root taxonomy
- Make the relaxation of `aa_crawler.cli.app`'s persistence-unawareness a
  reviewed, intentional, narrowly-scoped exception — not a silent one

## Considered options

### Persist unconditionally on every successful crawl

Rejected. This would change default CLI behavior for every existing
invocation, contradicting ADR-023's stable stdout-only contract and
requiring every caller to supply a destination whether they want
persistence or not.

### Add a pluggable `--sink` selection mechanism for future sink types

Rejected as premature. Exactly one concrete sink (`FileCrawlResultSink`)
exists. A selection mechanism for sinks that do not yet exist would repeat
the same premature-abstraction mistake ADR-020 and ADR-025 already reject
for parser families.

### Wire persistence into `ArticleCrawlService` or `ApplicationRuntime` instead of the CLI

Rejected. ADR-021 and ADR-022 scope those layers to orchestration and
runtime-resource composition only; ADR-024 deliberately kept persistence
outside both. Moving it there now would reopen accepted, unrelated
boundaries to solve a CLI-specific request.

### Add an optional `--output PATH` flag that triggers `FileCrawlResultSink` (chosen)

A single optional argument, absent by default, that — only when supplied —
constructs the existing `FileCrawlResultSink` and calls `save()` after a
successful crawl. No new sink, no new persistence code, no change to
default behavior.

## Decision

### CLI argument

`aa_crawler.cli` gains one new optional argument, `--output PATH` (short
form `-o`), alongside the existing required positional `url`. When absent,
`run_crawl()`'s behavior is byte-for-byte unchanged from ADR-023: exactly
one JSON object on stdout, no filesystem write, no import-time or
construction-time reference to `aa_crawler.persistence` on that code path.

### Persistence wiring

When `--output PATH` is supplied, `aa_crawler.cli.app.run_crawl()`
constructs `FileCrawlResultSink(destination=Path(PATH))` and calls
`.save(item)` with the single produced `CrawlerItem`, after the successful
crawl and after the JSON payload has already been printed to stdout.
Stdout output is unconditional on crawl success; persistence is an
additional, independent step that follows it. No new sink type, no
sink-selection mechanism, and no factory are introduced — this is the one
existing concrete sink from ADR-024, constructed directly.

### New exit code

A new CLI-local exit code, `EXIT_PERSISTENCE_FAILURE`, is added for the
case where the crawl succeeds (and its JSON is already on stdout) but the
subsequent `save()` call raises `PersistenceWriteError`. This extends
ADR-023's existing small exit-code table; it does not renumber or change
the meaning of any existing code, and it does not introduce a
project-wide error taxonomy (ADR-018 remains Deferred).

### Optionality test boundary updated, not removed

`tests/persistence/test_optionality.py` continues to assert that
`aa_crawler.application.runtime` and `aa_crawler.application.service`
never import `aa_crawler.persistence` — that boundary is unchanged and
remains fully enforced. Its assertion for `aa_crawler.cli.app` is relaxed
by this ADR only: `aa_crawler.cli.app` may now import
`aa_crawler.persistence`, and only when `--output` is supplied does it
construct or call a sink. `aa_crawler.cli.__init__` (argument parsing)
still does not need to import persistence directly.

### Idempotency unresolved

`FileCrawlResultSink.save()` remains append-only with no deduplication, as
ADR-024 already established. Running the CLI with `--output` twice against
the same URL appends the same result twice. This ADR does not resolve
that; a concrete idempotency guarantee remains explicitly deferred future
work, as ADR-024 already stated.

### No source, acquisition, or credential change

This ADR authorizes no change to `SourceRegistry`, `DEFAULT_SOURCE_PROFILES`,
`HtmlFetcher`'s content-type boundary, or any credential mechanism. It does
not enable any new production source.

### Non-goals

This ADR does not select a database, does not add a second concrete sink,
does not add batch or multi-URL CLI input, does not resolve idempotency,
and does not change which sources are enabled.

## Rationale

The gap Task 10.1 identified is narrow and already fully prepared for by
prior decisions: ADR-024 built exactly the sink this ADR now connects, and
both ADR-023 and ADR-024 explicitly named this exact connection as a
future, separately-reviewable step rather than ruling it out. Wiring it as
one optional flag — off by default, using the one existing sink, with one
new exit code — closes the gap without touching acquisition, application
orchestration, runtime composition, or governance, and without designing
anything speculative for sinks or sources that do not yet exist.

## Consequences

### Positive

- A caller can persist a crawl result through the CLI alone, with no
  custom Python code, closing the gap identified in Sprint 10 Task 10.1.
- Default CLI behavior (no `--output`) is provably unchanged.
- No new dependency, sink type, or source is introduced.

### Negative

- `aa_crawler.cli.app` is no longer fully unaware of `aa_crawler.persistence`;
  the optionality guarantee that package previously held for all three
  layers (`application.runtime`, `application.service`, `aa_crawler.cli`)
  now holds for only the first two. This is an intentional, reviewed
  narrowing, not an oversight.
- One more CLI-local exit code exists to document, test, and keep stable.
- Idempotency remains unresolved; repeated `--output` runs against the
  same URL will duplicate entries.

### Neutral

- `ArticleCrawlService`, `ApplicationRuntime`, `SourceRegistry`,
  `HtmlFetcher`, and all three parser families are unchanged.
- `FileCrawlResultSink`, `BaseCrawlResultSink`, and the persistence error
  hierarchy are unchanged; no new persistence code is introduced.
- ADR-016, ADR-017, ADR-018, and ADR-019 statuses are unchanged.

## Compatibility implications

This ADR is additive for CLI callers who never pass `--output`: their
behavior is unchanged. It is not additive for
`tests/persistence/test_optionality.py`'s existing assertion about
`aa_crawler.cli.app`, which this ADR deliberately narrows, as described
above. Adding a second concrete sink, a sink-selection mechanism, batch
input, or an idempotency guarantee would each alter this accepted contract
and requires its own review.

## Testing implications

Implementation tests must verify: default invocation (no `--output`)
remains byte-for-byte identical to the pre-ADR-027 CLI, including that no
file is written and no `aa_crawler.persistence` import occurs on that code
path at runtime; `--output PATH` durably appends the expected JSON line
via the real `FileCrawlResultSink`; a persistence failure after a
successful crawl still prints the stdout payload and returns
`EXIT_PERSISTENCE_FAILURE`; and the relaxed optionality test still passes
for `application.runtime` and `application.service`. Per the project
owner's explicit direction, verification against realistic data must use
fixtures whose markup structure mirrors a real, observed source
(`jsonld_article`, `generic_json_article`, or `microdata_article`) with
placeholder article content — never a verbatim copy of a real publisher's
copyrighted text — and must not perform any live network acquisition of a
real source.

## Relationship to existing decisions

- ADR-010 remains authoritative; the sink is still constructed explicitly
  by its caller (now optionally the CLI), never through a service locator.
- ADR-017 remains Deferred and is unaffected; this ADR does not change
  `CrawlerItem`'s portability posture.
- ADR-018 remains Deferred; the new exit code extends the existing
  CLI-local mapping only and creates no project-wide taxonomy.
- ADR-020, ADR-021, ADR-022, ADR-025, and ADR-026 remain authoritative and
  unrelated; source governance, application orchestration, runtime
  composition, and parser-family composition are unchanged.
- ADR-023 remains authoritative for the CLI's overall shape; this ADR
  exercises its own named review trigger ("persistence... CLI exposure")
  by adding exactly one optional argument and one new exit code.
- ADR-024 remains authoritative for the persistence port and
  `FileCrawlResultSink`'s behavior (including its unresolved idempotency);
  this ADR exercises its own named review trigger
  ("CLI-triggered persistence is proposed") without modifying either.

## Follow-up work

- Implement the `--output` argument, the `run_crawl()` wiring, and the new
  exit code.
- Update `tests/persistence/test_optionality.py` to reflect the narrowed
  boundary described above.
- Add a realistic-structure, content-sanitized fixture (per the Testing
  implications section) proving the full CLI → parse → persist path.
- Align documentation only after implementation and integration
  verification are complete, mirroring prior sprints' sequence.
- Do not enable any new production source, select a database, or resolve
  idempotency under this ADR; each requires its own future decision.

## Review triggers

- A second concrete sink type or a sink-selection mechanism is proposed.
- Batch or multi-URL CLI input is proposed.
- A concrete idempotency guarantee is required by real operational use.
- A new production source is proposed for enablement (a separate,
  project-owner governance decision, unrelated to this ADR's mechanism).
- Worker, queue, or scheduler work is scheduled and needs this CLI-level
  persistence as a building block.
