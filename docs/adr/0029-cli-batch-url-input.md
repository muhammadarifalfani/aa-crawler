# ADR-029 — CLI Batch/Multi-URL Input

- Status: Accepted
- Date: 2026-09-07
- Decision owners: CLI owner, Application owner, Tech Lead
- Related ADRs: ADR-017, ADR-018, ADR-019, ADR-021, ADR-022, ADR-023, ADR-024, ADR-027, ADR-028

## Context

ADR-023 approved a deliberately single-URL CLI and explicitly rejected
multi-URL batch input for its initial scope, naming it as its own future
review trigger: "Multi-URL batch input or JSON Lines output is proposed."
Sprint 13 (ADR-028) already satisfied half of that trigger — JSON Lines
stdout output now exists for scheduled mode — without needing to change
ADR-023's single-shot contract at all. This ADR resolves the other half:
letting the CLI crawl more than one URL, reusing the recoverable-vs-
terminal per-iteration pattern ADR-028 already established, while keeping
every existing single-URL invocation (single-shot and scheduled)
byte-for-byte unchanged.

## Decision drivers

- Resolve ADR-023's own named review trigger without reopening or
  weakening its single-URL, single-shot guarantees.
- Move further toward the project owner's stated "many sources" goal,
  building on ADR-028's scheduled-mode foundation rather than starting a
  parallel design.
- Give batch crawling a partial-failure policy that is actually useful:
  one bad URL among many should not by itself abort the whole batch,
  unlike ADR-028's single-URL scheduled mode, where retrying the *same*
  unsupported URL forever would be pointless.
- Avoid a large, risky refactor of the already-tested `run_crawl()` and
  `run_scheduled_crawl()` single-URL code paths.
- Keep the feature deterministically testable, consistent with ADR-028's
  injectable-sleep precedent.

## Considered options

1. Change the existing positional `url` argument to accept multiple values
   (`nargs='+'`) directly.
2. Add a new `--urls-file PATH` argument (one URL per line), mutually
   exclusive with the positional `url`, dispatching to new batch-aware
   functions while leaving `run_crawl()`/`run_scheduled_crawl()` untouched.
3. Accept URLs from stdin only (`-`), with no file-based option.
4. Refactor `run_crawl()`/`run_scheduled_crawl()` internally to always
   operate on a list of URLs (a list of one, for existing callers),
   unifying single- and multi-URL code paths.

## Decision

Adopt Option 2. Add an optional `--urls-file PATH` argument, mutually
exclusive with the positional `url` — exactly one of the two must be
supplied, validated by argument parsing. The file contains one absolute
HTTPS URL per line; blank lines and lines starting with `#` are skipped as
comments. `--urls-file` combines with the existing `--output`,
`--interval`, and `--max-runs` arguments exactly as the single positional
`url` already does:

```text
aa-crawler --urls-file sources.txt                       # one pass over the list, then exit
aa-crawler --urls-file sources.txt --output results.jsonl # also persists each successful result
aa-crawler --urls-file sources.txt --interval 300         # re-crawl the whole list every 5 minutes
aa-crawler --urls-file sources.txt --interval 300 --max-runs 10  # bounded to 10 full passes
```

In scheduled batch mode, one "iteration"/"run" (and therefore what
`--max-runs` counts) is one full pass over the entire URL list, not one
URL.

Options 1 and 3 are rejected as narrower on their own merits (a large URL
count is unwieldy as shell arguments; stdin alone is harder to reuse for a
saved, durable source list) but may still be added later as additional
input mechanisms without revisiting this decision's core batch semantics.
Option 4 is rejected for this sprint: unifying the single- and multi-URL
code paths is a larger, riskier refactor of already-tested code than a
new, additive module delivers; it remains a candidate for future cleanup
once batch behavior has proven itself in production use.

### Per-URL failure policy within one pass

Batch mode's policy deliberately differs from ADR-028's single-URL
scheduled-mode policy for one condition:

| Condition | Policy | Rationale |
|---|---|---|
| `UnsupportedSourceError` for one URL | **Recoverable** here (differs from ADR-028): logged, skip to the next URL in the list | One bad URL among many should not abort a batch; unlike single-URL scheduled mode, this is not the *same* URL being retried forever — it is one item among many, most of which may well succeed. |
| `CrawlerError` for one URL | Recoverable: logged, skip to the next URL | Same reasoning as ADR-028: plausibly transient, worth trying other URLs regardless. |
| A persistence failure (`PersistenceWriteError`) after a successful crawl | Terminal: the batch/run stops immediately | Matches ADR-028: a persistence failure is likely systemic (bad destination, disk full) and will keep failing for every subsequent URL; stopping loudly is better than silently dropping results batch after batch. |
| Any other unexpected `Exception` | Terminal: the batch/run stops immediately | Conservative default, matching ADR-028: an unreasoned-about failure mode is not assumed safe to keep going past. |

### Exit code semantics for partial failure

Exit code `0` is returned when a full pass (single-shot) or the whole
scheduled run (until `--max-runs` or an interrupt) completes, **even when
some URLs were skipped** due to a recoverable per-URL failure. Partial
success is still success at the process level: each successful URL prints
its own JSON line, and each skipped URL logs its own error, so the
operator can distinguish full success from partial success from the
output and logs without a new exit-code category. Introducing a distinct
"completed with some failures" exit code was considered and rejected: it
would need its own definition of "how many/which failures count," adding
a small taxonomy this project has consistently avoided (ADR-018 remains
Deferred) for a distinction the existing stdout/log output already makes
visible. No new exit code is introduced; batch mode reuses exactly the
CLI-local exit codes ADR-023, ADR-027, and ADR-028 already define.

### Output contract

Batch mode's stdout is JSON Lines — one JSON object per line per
successful URL — for both single-shot and scheduled batch mode, matching
the convention ADR-028 already established for scheduled single-URL mode.
`--output`, when supplied, still appends via the same
`FileCrawlResultSink` (ADR-024/ADR-027), once per successful URL.

## Rationale

This resolves ADR-023's long-standing named review trigger with the
smallest change that reuses, rather than duplicates, ADR-028's proven
recoverable-vs-terminal pattern and injectable-sleep testability — while
keeping every existing single-URL code path completely untouched, so the
risk of this change is isolated to new, additive code.

## Consequences

### Positive

- Directly answers the project owner's "many sources" goal: one CLI
  invocation (optionally scheduled) can now crawl an entire list of
  sources.
- `run_crawl()` and `run_scheduled_crawl()` remain byte-for-byte unchanged;
  every existing test for single-URL mode continues to hold without
  modification.
- One bad or newly-disabled URL in a large list no longer aborts crawling
  the rest of the list.

### Negative

- Two more CLI-layer modules/functions (batch single-shot, batch
  scheduled) partially duplicate the shape of `run_crawl()`/
  `run_scheduled_crawl()`, accepted as the cost of not refactoring
  already-tested code (Option 4, rejected above).
- No new exit-code category means an operator must read stdout/log output
  to know whether a batch run was fully or only partially successful; a
  purely-exit-code-driven caller cannot distinguish the two.
- `--urls-file` supports only a local filesystem path; no remote list
  source (URL, database query, message topic) is supported.

### Neutral

- No change to `ArticleCrawlService`, `ApplicationRuntime`,
  `SourceRegistry`, or any parser family; this remains entirely a
  CLI-layer addition, exactly like ADR-028.

## Compatibility implications

Default CLI behavior (the positional `url`, single-shot or scheduled) is
completely unchanged. `--urls-file` is new, off by default, and mutually
exclusive with the positional `url`; no existing invocation's behavior
changes.

## Testing implications

- New unit tests exercise: the file-parsing contract (comments and blank
  lines skipped), mutual exclusivity with the positional `url` (both
  supplied, or neither, is rejected by argument parsing), one full pass
  crawling every URL in order, a recoverable `UnsupportedSourceError` and
  `CrawlerError` each skipping only their own URL and continuing, a
  terminal persistence failure and unexpected failure each stopping the
  batch immediately, `--output` persisting once per successful URL only,
  the JSON Lines output contract, and scheduled batch mode's `--max-runs`
  counting full passes rather than individual URLs.
- No test performs a live network acquisition or a real wall-clock sleep,
  consistent with ADR-028's precedent.

## Relationship to existing decisions

- ADR-023 (CLI Application Entry Point and Process Boundary) remains
  authoritative for its single-URL, single-shot mode; this ADR resolves
  its "Multi-URL batch input... is proposed" review trigger without
  reopening or altering that mode.
- ADR-028 (CLI Scheduled Crawl Mode) remains authoritative for its
  single-URL scheduled mode; this ADR reuses its injectable-sleep and
  reused-runtime patterns for the new scheduled batch mode, while
  deliberately diverging on `UnsupportedSourceError`'s recoverable-vs-
  terminal classification, justified above.
- ADR-024 (Application-Level Persistence Boundary) and ADR-027
  (CLI-Triggered Persistence) are reused unchanged: the same
  `FileCrawlResultSink`, now called once per successful URL across a
  batch instead of once per process or once per scheduled iteration.
- ADR-021 (Application-Level Article Crawl Orchestration) and ADR-022
  (Application Runtime Composition and Resource Ownership) are unaffected:
  `ArticleCrawlService.crawl()`'s single-URL semantics are unchanged; this
  ADR only calls that existing contract once per URL in a list.
- ADR-017 (Metadata Portability) and ADR-019 (Future Execution Families)
  remain Deferred/Proposed respectively; sequential, synchronous crawling
  of a list of URLs does not trigger either — no queue, worker, async
  runtime, or browser automation is introduced.
- ADR-018 (Error-Root Taxonomy) remains Deferred; the exit-code decision
  above deliberately avoids introducing a partial-failure taxonomy for the
  same reason ADR-023/ADR-027/ADR-028 kept their exit-code mappings
  CLI-local and small.

## Follow-up work

- Additional input mechanisms (stdin, repeated positional arguments) are
  explicitly deferred; `--urls-file` is the only mechanism this ADR
  approves.
- Unifying the single- and multi-URL code paths (Option 4) remains a
  candidate future cleanup, not undertaken here.
- Per-URL concurrency within one pass is not addressed; URLs are crawled
  strictly sequentially, reusing one `ApplicationRuntime`.

## Review triggers

A requirement for concurrent per-URL crawling within one pass, a remote or
dynamic URL-list source, or a caller-visible distinction between "fully
successful" and "partially successful" batch runs.
