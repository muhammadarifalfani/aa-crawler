# ADR-031 — CLI Sink Selection

- Status: Accepted
- Date: 2026-09-07
- Decision owners: CLI owner, Persistence owner, Tech Lead
- Related ADRs: ADR-023, ADR-024, ADR-027, ADR-028, ADR-029, ADR-030

## Context

ADR-030 added `SqliteCrawlResultSink`, a second concrete
`BaseCrawlResultSink` with real per-`requested_url` idempotency, but
explicitly deferred any CLI exposure — its own review trigger names "CLI
wiring for sink selection is proposed" as the condition for revisiting
this. Today, `-o`/`--output PATH` (ADR-027) always constructs
`FileCrawlResultSink`, hardcoded identically in `cli/app.py`,
`cli/scheduler.py`, and `cli/batch.py`. A CLI user has no way to reach
`SqliteCrawlResultSink`'s idempotency at all — exactly the gap ADR-030
named. This ADR resolves it, mirroring the ADR-024-then-ADR-027 precedent
a second time: the port and sink existed first, CLI exposure follows as
its own separately-approved step.

## Decision drivers

- Let a CLI user actually reach `SqliteCrawlResultSink`'s idempotency,
  the specific gap ADR-030 named and deferred.
- Keep the change explicit, not inferred: this project has consistently
  preferred an explicit flag over guessing intent from a file extension
  or path shape (see ADR-020's exact-host-only matching, ADR-023's
  explicit exit-code mapping).
- Preserve every existing single-URL/scheduled/batch invocation's exact
  current behavior when the new flag is omitted.
- Avoid duplicating the small amount of sink-selection logic across the
  three CLI entry functions (`run_crawl`, `run_scheduled_crawl`,
  `run_batch_crawl`/`run_scheduled_batch_crawl`) that each currently
  hardcode `FileCrawlResultSink` identically.

## Considered options

1. Add an explicit `--sink {file,sqlite}` argument, default `file`,
   valid only together with `--output`; `main()` resolves it to the
   corresponding sink class and passes that class down as an injectable
   `sink_factory` parameter, replacing each function's hardcoded
   `FileCrawlResultSink(...)` construction.
2. Infer the sink type from `--output`'s file extension (e.g. `.db`/
   `.sqlite` → SQLite, otherwise file).
3. Add a second, sink-specific flag (e.g. `--sqlite-output PATH`)
   alongside the existing `--output PATH`, allowing both to be supplied
   together so a single crawl persists to both sinks at once.
4. Leave sink selection entirely to direct Python composition, as today;
   make no CLI change.

## Decision

Adopt Option 1. Add an optional `--sink {file,sqlite}` argument, valid
only together with `--output` (rejected by argument parsing otherwise,
mirroring `--max-runs`'s existing dependency on `--interval`), defaulting
to `file`:

```text
aa-crawler <url> -o results.jsonl                    # unchanged: FileCrawlResultSink
aa-crawler <url> -o results.jsonl --sink file         # equivalent, explicit
aa-crawler <url> -o results.db --sink sqlite          # NEW: SqliteCrawlResultSink
```

`FileCrawlResultSink` and `SqliteCrawlResultSink` share the exact same
constructor shape (`__init__(self, *, destination: Path) -> None`), so
`cli/__init__.py`'s `main()` resolves `--sink` to the corresponding class
once and passes it down as a new `sink_factory` keyword parameter to
`run_crawl()`, `run_scheduled_crawl()`, `run_batch_crawl()`, and
`run_scheduled_batch_crawl()`, defaulting to `FileCrawlResultSink` in
every one of them. Each function's internals change from constructing
`FileCrawlResultSink(destination=output)` directly to
`sink_factory(destination=output)` — a small, mechanical, behavior-
preserving change when `sink_factory` is omitted.

Options 2 and 3 are rejected. Option 2 (extension inference) introduces
implicit, guessable behavior this project has consistently avoided in
every prior CLI decision; a `.db` file is not unambiguously a SQLite
database, and silently picking a sink based on a filename risks a
surprising mismatch between an operator's intent and the actual
persistence behavior. Option 3 (dual-sink) adds real complexity (two
independent failure modes to reconcile in the exit-code and logging
contract) for a use case (writing the same result to two destinations at
once) no one has asked for; it can be reconsidered later as its own
proposal if a real need appears. Option 4 is rejected because it leaves
ADR-030's own named gap unresolved indefinitely.

## Rationale

Reusing the identical constructor shape both sinks already share makes
this the smallest possible CLI change: one new argument, one new
parameter threaded through three existing functions, no change to any
function's other behavior, no new exit code, and no change to
`FileCrawlResultSink`, `SqliteCrawlResultSink`, or any application-layer
code.

## Consequences

### Positive

- `SqliteCrawlResultSink`'s idempotency is now reachable from the CLI —
  the specific gap ADR-030 named is closed.
- Every existing invocation (with or without `--output`, with or without
  `--interval`/`--urls-file`) is byte-for-byte unchanged when `--sink` is
  omitted, since `file` is the default and matches the prior hardcoded
  behavior exactly.
- No new exit code: `PersistenceWriteError` from either sink still maps
  to `EXIT_PERSISTENCE_FAILURE`, unchanged.
- The sink-selection logic lives in exactly one place (`cli/__init__.py`),
  not duplicated across `cli/app.py`, `cli/scheduler.py`, and
  `cli/batch.py`.

### Negative

- A caller cannot persist to both sinks in one invocation (Option 3,
  rejected above); switching sinks requires a second invocation against
  a second destination.
- `--sink` adds one more argument to an already-growing CLI surface
  (`--output`, `--interval`, `--max-runs`, `--urls-file`, now `--sink`).

### Neutral

- No change to `ArticleCrawlService`, `ApplicationRuntime`,
  `FileCrawlResultSink`, or `SqliteCrawlResultSink`; this is entirely a
  CLI-layer wiring change.

## Compatibility implications

Default CLI behavior (no `--sink`, or `--sink file`) is completely
unchanged from ADR-027/028/029. `--sink sqlite` is new, off by default,
and requires `--output`; no existing invocation's behavior changes.

## Testing implications

- New unit tests exercise: `--sink` without `--output` is rejected;
  `--sink sqlite` with `--output` dispatches with `SqliteCrawlResultSink`
  as the resolved `sink_factory` (verified for all four entry functions —
  single-shot, scheduled, batch, scheduled batch); omitting `--sink`
  (or passing `--sink file` explicitly) preserves `FileCrawlResultSink`
  as the resolved factory; an invalid `--sink` value is rejected by
  `argparse`'s own `choices` validation.
- Existing single-URL, scheduled, batch, and scheduled-batch tests that
  never pass `sink_factory` continue to hold unmodified, proving the
  default preserves current behavior exactly.
- One real-pipeline integration test drives `--sink sqlite --output <path>`
  through the real CLI and confirms a real SQLite database file with the
  expected row is produced.

## Relationship to existing decisions

- ADR-027 (CLI-Triggered Persistence) remains authoritative for
  `--output`'s existence and off-by-default behavior; this ADR adds
  `--sink` as a modifier of which concrete sink `--output` targets,
  without changing `--output`'s own meaning.
- ADR-028 (CLI Scheduled Crawl Mode) and ADR-029 (CLI Batch/Multi-URL
  Input) are extended with the same `sink_factory` parameter, defaulting
  to preserve their existing exact behavior; neither's failure policy,
  exit codes, or output contract changes.
- ADR-030 (SQLite Crawl Result Sink) is fully realized by this ADR: its
  own named review trigger ("CLI wiring for sink selection is proposed")
  is the reason this ADR exists.
- ADR-024 (Application-Level Persistence Boundary) remains authoritative
  for the port itself; `ArticleCrawlService` and `ApplicationRuntime`
  remain fully unaware of persistence, unaffected by this ADR.

## Follow-up work

- Persisting to more than one sink in a single invocation (Option 3,
  rejected above) remains a candidate for separate future work if a real
  need appears.
- A third sink type, if ever proposed, would extend the same `--sink`
  choices and `sink_factory` pattern without needing to revisit this
  ADR's core design.

## Review triggers

A third concrete sink is proposed; a requirement to persist to more than
one sink in a single invocation is identified; `--output`'s own meaning
or default-off behavior needs to change.
