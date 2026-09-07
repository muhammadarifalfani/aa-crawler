# ADR-030 — SQLite Crawl Result Sink

- Status: Accepted
- Date: 2026-09-07
- Decision owners: Persistence owner, Tech Lead
- Related ADRs: ADR-013, ADR-017, ADR-024, ADR-027, ADR-028, ADR-029

## Context

ADR-024 introduced `aa_crawler.persistence` with one deliberately minimal
concrete sink, `FileCrawlResultSink`: append-only, no deduplication, no
idempotency guarantee. ADR-024 named its own review triggers for revisiting
this: "a database or schema technology needs selecting for real
deployment" and "worker, queue, or scheduler work is scheduled and needs
durable state." Sprint 13 (ADR-028) and Sprint 14 (ADR-029) both landed
since then, giving the CLI genuine scheduled and batch crawling. Running
either of those against `FileCrawlResultSink` for real, over time, means
the same URL is re-crawled and re-appended on every interval or pass, with
no deduplication — the destination file grows without bound, full of
near-identical repeated records for unchanged content. This ADR adds a
second concrete sink that gives a caller who wants it a durable,
idempotent alternative, without touching the CLI's existing wiring or the
first sink's behavior at all.

## Decision drivers

- Directly answer ADR-024's own named review trigger, now that scheduled
  and batch crawling exist and make the append-only sink's unbounded
  growth a concrete, visible problem rather than a hypothetical one.
- Prefer the smallest technology choice that solves the problem: no new
  runtime dependency, consistent with ADR-013's "core environment stays
  small" philosophy and every persistence-adjacent ADR's shared caution
  about premature complexity (ADR-017, ADR-019).
- Give real idempotency (ADR-024's other named trigger) for the specific,
  now-common case of re-crawling the same URL repeatedly.
- Keep the change isolated to the persistence layer; do not touch the
  CLI, `ArticleCrawlService`, or `ApplicationRuntime` in this sprint.

## Considered options

1. Add `SqliteCrawlResultSink` using the standard-library `sqlite3` module,
   upserting by `requested_url` for idempotency.
2. Add a sink backed by a third-party ORM or database driver (e.g.
   SQLAlchemy, `asyncpg`, a document database client).
3. Add deduplication to `FileCrawlResultSink` itself (e.g. read-modify-
   write the whole file, or maintain a separate index file).
4. Wire the new sink into the CLI in this same sprint (a `--sink` flag
   selecting between `file` and `sqlite`).

## Decision

Adopt Option 1. Add `SqliteCrawlResultSink(BaseCrawlResultSink)` to
`aa_crawler.persistence`, backed entirely by the standard-library
`sqlite3` module — no new runtime dependency. It stores results in one
table:

```sql
CREATE TABLE IF NOT EXISTS crawl_results (
    requested_url TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
```

`save(item)` upserts by `item.data["requested_url"]`: an
`INSERT ... ON CONFLICT(requested_url) DO UPDATE` replaces `payload` (the
same `json.dumps(dict(item.data), sort_keys=True)` serialization
`FileCrawlResultSink` already uses) and `updated_at` (an ISO 8601 UTC
timestamp) for that URL, rather than duplicating a row. Re-crawling the
same URL under `--interval` or across repeated `--urls-file` passes keeps
exactly one row per URL, always reflecting the latest successful crawl.
`requested_url` is required to be present and a non-empty string in
`item.data`; every current shipped parser family always produces it (it is
part of the documented output contract), so this is a real, not merely
theoretical, requirement — a missing or malformed value raises
`PersistenceWriteError`, matching `FileCrawlResultSink`'s existing
serialization-failure behavior.

Options 2 and 3 are rejected: Option 2 would add a runtime dependency this
project has consistently avoided without a concrete, approved deployment
requirement (ADR-013); Option 3 would give `FileCrawlResultSink` two
different behaviors depending on hidden internal logic, contradicting its
own documented, simple append-only contract, which existing callers may
already depend on. Option 4 (CLI wiring) is explicitly deferred, mirroring
the ADR-024-then-ADR-027 precedent: this ADR adds the sink itself, exactly
as ADR-024 added the first one without CLI exposure; CLI selection between
sinks is separate, future, explicitly-approved work.

## Rationale

SQLite via the standard library is the smallest change that gives a real
idempotency guarantee for the common "re-crawl the same URL/list
repeatedly" case ADR-028/ADR-029 introduced, without adding any
dependency, without touching the CLI's existing behavior, and without
weakening `FileCrawlResultSink`'s simple, already-relied-upon contract.

## Consequences

### Positive

- Real idempotency for the specific case scheduled/batch mode makes
  common: the same URL never produces more than one row, regardless of
  how many times it is crawled.
- No new runtime dependency; `sqlite3` ships with every supported Python
  version.
- `FileCrawlResultSink` is completely unmodified; every existing caller
  and test keeps its exact current behavior.
- A durable, queryable destination (a real SQL table) is available to any
  caller who wants one, without adopting a database server.

### Negative

- Upserting by `requested_url` means a URL whose canonical target changes
  over time (redirects, republished content) still overwrites the same
  row; there is no history of prior crawls for that URL. This sink trades
  history for idempotency deliberately; a caller wanting history should
  use `FileCrawlResultSink` (or both, since sinks may be composed
  independently) instead.
- SQLite is a single-file, single-writer-friendly database, not a
  multi-process or networked store; concurrent writers from separate
  processes are not addressed by this ADR.
- Not wired into the CLI this sprint: a caller must compose
  `SqliteCrawlResultSink` directly in Python, exactly as
  `FileCrawlResultSink` could be before ADR-027.

### Neutral

- No change to `ArticleCrawlService`, `ApplicationRuntime`, the CLI, or
  any parser family; this is entirely a `aa_crawler.persistence` addition.

## Compatibility implications

`FileCrawlResultSink`'s behavior, `BaseCrawlResultSink`'s abstract
contract, and every existing CLI invocation are completely unchanged. This
ADR is purely additive.

## Testing implications

- New unit tests exercise: a fresh database file is created on first
  `save()`; a repeated `save()` for the same `requested_url` upserts (one
  row, latest payload and `updated_at`) rather than duplicating; distinct
  URLs produce distinct rows; a missing or empty `requested_url` raises
  `PersistenceWriteError`; a serialization failure (an unserializable
  value in `item.data`) raises `PersistenceWriteError`, matching
  `FileCrawlResultSink`'s precedent; the destination file's parent
  directory must already exist, matching `FileCrawlResultSink`'s existing
  documented behavior.
- No test performs a live network acquisition; all tests exercise
  `SqliteCrawlResultSink` directly against `tmp_path`-based database files.

## Relationship to existing decisions

- ADR-024 (Application-Level Persistence Boundary) remains authoritative
  for `BaseCrawlResultSink`'s abstract contract; this ADR adds a second
  implementation without changing the port itself or
  `FileCrawlResultSink`.
- ADR-027 (CLI-Triggered Persistence) and its `--output`/`FileCrawlResultSink`
  wiring are unaffected; CLI selection of `SqliteCrawlResultSink` is
  explicitly deferred (see Follow-up work).
- ADR-028 (CLI Scheduled Crawl Mode) and ADR-029 (CLI Batch/Multi-URL
  Input) motivate this ADR but are not modified by it: neither's failure
  policy, exit codes, or output contract changes.
- ADR-013 (Pydantic Dependency Classification) and the project's general
  small-core-dependency philosophy are honored: no new runtime dependency
  is introduced.
- ADR-017 (Metadata Portability) remains Deferred; this sink still stores
  `item.data` as an opaque JSON payload, not a typed/portable schema,
  consistent with ADR-017's still-unmet trigger conditions.

## Follow-up work

- CLI wiring (a flag selecting `SqliteCrawlResultSink` alongside or instead
  of `FileCrawlResultSink`) is explicitly deferred to a separate,
  future-approved sprint.
- Multi-process concurrent write safety is not addressed.
- Schema evolution (what happens if a future parser family's output shape
  changes) is not addressed beyond storing the payload as opaque JSON.

## Review triggers

CLI wiring for sink selection is proposed; a concrete multi-process
concurrent-write requirement is identified; a schema/typed-storage
requirement beyond an opaque JSON payload is identified.
