# ADR-028 — CLI Scheduled Crawl Mode

- Status: Accepted
- Date: 2026-09-07
- Decision owners: CLI owner, Application owner, Tech Lead
- Related ADRs: ADR-017, ADR-018, ADR-019, ADR-021, ADR-022, ADR-023, ADR-024, ADR-027

## Context

The project owner's long-term goal for `aa_crawler` is a realtime engine
usable across many online news sources. ADR-023 gave the CLI a
deliberately one-shot process boundary: one URL in, one synchronous crawl,
one JSON object on stdout, then exit. Nothing in the current architecture
repeats a crawl or runs unattended. Sprint 13's Architecture Discovery
evaluated the gap and found that "realtime" does not require jumping
straight to an asynchronous or queue/worker-based architecture:
ADR-019's own review trigger is "JavaScript-rendered targets, async
throughput requirements, or public plugins", and ADR-017's is "queues,
workers" — a scheduler that periodically repeats the existing synchronous
crawl does not, by itself, trigger either. This ADR introduces the
smallest capability that meaningfully moves toward the realtime goal:
letting the CLI repeat the same crawl on an interval, still fully
synchronous, still using the existing `ApplicationRuntime` and
`ArticleCrawlService` unchanged.

## Decision drivers

- Move toward the realtime goal without prematurely adopting async,
  browser, queue, or worker architecture that ADR-017/ADR-019 deliberately
  defer until a real requirement exists.
- Preserve ADR-023's single-shot mode as the unchanged default; scheduling
  must be strictly opt-in.
- Reuse the existing `ArticleCrawlService`/`ApplicationRuntime` composition
  unchanged — no new application-layer capability, no source, robots,
  retry, identity, or parser change.
- Keep the feature deterministically testable without real wall-clock
  waits or real process signals.
- Give an operator (the project owner, running this manually or under an
  external process supervisor) a bounded, predictable failure and shutdown
  contract for a long-running process, not just a single request.

## Considered options

1. Document external OS-level scheduling (cron, Windows Task Scheduler)
   invoking the existing single-shot CLI repeatedly; add no code.
2. Add an in-process, synchronous, interval-based repeat mode to the CLI,
   reusing one `ApplicationRuntime` across iterations.
3. Introduce an async event loop and a real scheduling library.
4. Introduce a queue/worker architecture (e.g. a message broker) for
   distributed, scaled scheduled crawling.

## Decision

Adopt Option 2. Add an optional `--interval SECONDS` CLI argument. When
supplied, the CLI enters **scheduled crawl mode**: it bootstraps the
application and opens exactly one `ApplicationRuntime` for the entire run
(not one per iteration), then repeatedly calls the existing
`ArticleCrawlService.crawl(url)` — crawling immediately on start, then
waiting `interval` seconds between each subsequent crawl — until either
the process receives a keyboard interrupt, an optional `--max-runs N`
iteration count is reached, or a terminal failure occurs (Section
"Per-iteration failure policy" below). `--max-runs` is only meaningful
together with `--interval` and is rejected otherwise. Options 3 and 4 are
explicitly rejected for this sprint: neither is required to deliver
periodic re-crawling, and both would trigger ADR-019's and ADR-017's own
deferral conditions prematurely.

### Per-iteration failure policy

Scheduled mode distinguishes **recoverable** conditions (logged; the loop
continues to the next scheduled iteration) from **terminal** conditions
(logged; the loop stops and the process exits with the same CLI-local exit
code ADR-023/ADR-027 already define for that condition):

| Condition | Policy | Rationale |
|---|---|---|
| `CrawlerError` during one iteration's crawl | Recoverable | Transport, robots, or acquisition failures are plausibly transient between scheduled runs. |
| A persistence failure (`PersistenceWriteError`) after a successful crawl | Terminal | Silently dropping results every iteration until noticed is worse than stopping loudly; matches ADR-027's existing single-shot semantics. |
| `UnsupportedSourceError` | Terminal | A static, configuration-level rejection will not resolve itself between iterations; retrying it forever is wasted work. |
| Any other unexpected `Exception` | Terminal | Conservative default: an unreasoned-about failure mode is not assumed safe to retry indefinitely. |
| `KeyboardInterrupt` (Ctrl+C, or an operator-issued `SIGINT`) | Clean shutdown | An operator-requested stop of a long-running process is normal, not a failure; the runtime is closed via its existing context-manager `__exit__`, and the process exits `EXIT_SUCCESS`. |
| `--max-runs` reached | Clean shutdown | Same as above — a bounded run count completing is success, not failure. |

No new `EXIT_*` constant is introduced; scheduled mode reuses exactly the
CLI-local exit codes ADR-023 and ADR-027 already define.

### Output contract

Single-shot mode's "exactly one JSON object on stdout" contract (ADR-023)
is unchanged when `--interval` is omitted. In scheduled mode, stdout
instead carries one JSON object per line per successful iteration — JSON
Lines, matching the format the `--output` file (ADR-027) already uses —
since a repeating process cannot honestly promise "exactly one" object.

### Testability

The interval wait is injected as a callable (defaulting to
`time.sleep`), not hardcoded, so tests can substitute a deterministic,
instant test double instead of a real wall-clock wait, per the project's
existing testing rule that "tests must be deterministic — no reliance on
wall-clock time." `--max-runs` exists specifically to make scheduled mode
finitely, deterministically testable without simulating process signals.

## Rationale

This is the smallest change that gives the project owner a genuinely
repeating, unattended crawl capability, while staying inside the
synchronous architecture every other module already assumes. It does not
foreclose Options 3 or 4 — ADR-017 and ADR-019 remain exactly as deferred
or proposed as before, to be revisited only when their own named triggers
(queues/workers; async throughput or JS-rendered targets) actually occur.

## Consequences

### Positive

- A real, working step toward the realtime goal, shippable and verifiable
  in one sprint.
- No new runtime dependency, no async, no browser automation, no
  queue/broker — the core installation and its supply-chain footprint are
  unchanged.
- Reuses one `ApplicationRuntime` (and therefore one `HttpClient`, one
  `RobotsPolicy` cache) across iterations, which is more efficient than
  repeated single-shot invocations and lets `robots.txt` caching actually
  pay off across a scheduled run.

### Negative

- Scheduled mode only ever re-crawls the same single URL; it does not
  itself deliver "many sources" — that remains separate, deferred future
  work (batch/multi-URL input).
- A long-running scheduled process has no built-in health check,
  metrics endpoint, or external supervision; an operator (or an external
  process manager) is responsible for restarting a process that exits
  with a terminal failure.
- stdout's contract now differs by mode (one JSON object vs. JSON Lines),
  which a caller must know to parse correctly.

### Neutral

- No change to `ArticleCrawlService`, `ApplicationRuntime`, `SourceRegistry`,
  or any parser family; this is entirely a CLI-layer addition.

## Compatibility implications

Default CLI behavior (no `--interval`) is unchanged: single-shot mode,
identical output contract, identical exit-code mapping. `--interval` and
`--max-runs` are new, off-by-default arguments; no existing invocation's
behavior changes.

## Testing implications

- New unit and CLI-process-boundary tests exercise: immediate first crawl,
  waiting between iterations via an injected fake sleep, `--max-runs`
  terminating cleanly at the expected count, a recoverable `CrawlerError`
  continuing to the next iteration, each terminal condition stopping the
  loop with its documented exit code, `--output` persisting once per
  successful iteration, and `--max-runs` being rejected without
  `--interval`.
- No test performs a live network acquisition or a real wall-clock sleep.

## Relationship to existing decisions

- ADR-023 (CLI Application Entry Point and Process Boundary) remains
  authoritative for single-shot mode; this ADR adds a second, opt-in mode
  alongside it without changing the first.
- ADR-024 (Application-Level Persistence Boundary) and ADR-027
  (CLI-Triggered Persistence) are reused unchanged: the same
  `FileCrawlResultSink`, the same off-by-default `--output` argument, now
  called once per successful iteration instead of once per process.
- ADR-021 (Application-Level Article Crawl Orchestration) and ADR-022
  (Application Runtime Composition and Resource Ownership) are unaffected:
  `ArticleCrawlService.crawl()`'s single-URL semantics and
  `ApplicationRuntime`'s resource-ownership contract are unchanged; this
  ADR only calls that existing contract repeatedly.
- ADR-017 (Metadata Portability) and ADR-019 (Future Execution Families)
  remain Deferred/Proposed respectively; this ADR does not trigger either,
  per the analysis in "Context" above.
- ADR-018 (Error-Root Taxonomy) remains Deferred; the per-iteration
  failure policy above is CLI-local, matching ADR-023/ADR-027's existing
  approach of a small, local exit-code mapping rather than a project-wide
  exception taxonomy.

## Follow-up work

- Multi-URL / batch input for the CLI (single-shot and scheduled) is
  explicitly deferred; scheduled mode as decided here still crawls exactly
  one URL per process.
- Health/liveness signaling for a long-running scheduled process (e.g. for
  an external supervisor) is not addressed here.
- Revisit ADR-017/ADR-019 only when their own named triggers occur — this
  ADR does not advance either.

## Review triggers

A requirement for concurrent multi-source scheduled crawling, sub-second
scheduling precision, or any form of distributed/multi-process
coordination.
