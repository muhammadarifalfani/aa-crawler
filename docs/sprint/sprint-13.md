# Sprint 13 Completion Report

## 1. Status

Sprint 13 implementation is complete. Integration verification is
complete. Documentation alignment is complete. This completion report was
merged, local `main` was subsequently synchronized cleanly with
`origin/main`, and the final repository-wide verification (Section 9)
passed on that merged state with no Critical or Major findings.

**Sprint 13 is formally closed.**

## 2. Objective

Sprint 13's Architecture Discovery evaluated the project owner's stated
long-term goal — a realtime engine usable across many online news sources
— against the current architecture, and found that "realtime" does not
require jumping straight to an asynchronous or queue/worker-based design:
ADR-019's own review trigger is "JavaScript-rendered targets, async
throughput requirements, or public plugins", and ADR-017's is "queues,
workers" — a scheduler that periodically repeats the existing synchronous
crawl does not, by itself, trigger either. The project owner chose this
candidate (an in-process scheduled crawl mode) over two alternatives
(multi-URL/batch CLI input; documenting external OS-level scheduling
only) as Sprint 13's sole scope — the project's first concrete step toward
its realtime goal.

## 3. Architecture decision

- [ADR-028 — CLI Scheduled Crawl Mode](../adr/0028-cli-scheduled-crawl-mode.md)
  is **Accepted** and defines the optional `-i`/`--interval SECONDS`
  argument, the optional `--max-runs N` bound, one reused
  `ApplicationRuntime` for the whole scheduled run, an injectable sleep
  callable for deterministic testing, and the documented
  recoverable-vs-terminal per-iteration failure policy. It explicitly
  rejects an async/browser architecture and a queue/worker architecture
  for this step, since neither ADR-019's nor ADR-017's own review trigger
  is met by periodic re-crawling alone.

Earlier accepted decisions remain authoritative in their existing areas:

- [ADR-014 — User-Agent Ownership](../adr/0014-user-agent-ownership.md)
- [ADR-015 — Retry Idempotency](../adr/0015-retry-idempotency.md)
- [ADR-020 — Declarative Source Architecture](../adr/0020-declarative-source-architecture.md)
- [ADR-021 — Application-Level Article Crawl Orchestration](../adr/0021-application-level-article-crawl-orchestration.md)
- [ADR-022 — Application Runtime Composition and Resource Ownership](../adr/0022-application-runtime-composition-and-resource-ownership.md)
- [ADR-023 — CLI Application Entry Point and Process Boundary](../adr/0023-cli-application-entry-point-and-process-boundary.md)
- [ADR-024 — Application-Level Persistence Boundary for Crawl Results](../adr/0024-application-level-persistence-boundary.md)
- [ADR-025 — Extensible Parser-Family Composition Seam](../adr/0025-extensible-parser-family-composition.md)
- [ADR-026 — Microdata Article Parser Family](../adr/0026-microdata-article-parser-family.md)
- [ADR-027 — CLI-Triggered Persistence](../adr/0027-cli-triggered-persistence.md)

The [ADR index](../adr/README.md) now records 21 Accepted, 2 Proposed, 2
Deferred, and 0 Superseded decisions. ADR-016 and ADR-019 remain Proposed;
ADR-018 remains Deferred. ADR-017 remains Deferred: its review trigger
("queues, workers") is not met by an in-process, single-URL,
single-runtime repeat loop, so its status is unchanged by this sprint.

## 4. Implementation: `run_scheduled_crawl()`

[`src/aa_crawler/cli/scheduler.py`](../../src/aa_crawler/cli/scheduler.py)
(new) implements the ADR-028 decision. The CLI (`src/aa_crawler/cli/__init__.py`)
gained two new optional arguments alongside the existing `url` and
`--output`:

```text
aa-crawler <url>                                  # unchanged: single-shot mode
aa-crawler <url> --interval 300                   # scheduled mode: crawl every 5 minutes
aa-crawler <url> --interval 300 --max-runs 10      # scheduled mode: bounded to 10 iterations
```

`--max-runs` is rejected by argument parsing unless `--interval` is also
supplied; both are validated as positive (`--interval 0`, a negative
value, or `--max-runs 0` are all rejected with a clear argparse error).
`main()` dispatches to the existing single-shot `run_crawl()` when
`--interval` is omitted (byte-for-byte unchanged from ADR-023/ADR-027) or
to the new `run_scheduled_crawl()` when it is supplied.

`run_scheduled_crawl()` bootstraps the application and opens exactly one
`ApplicationRuntime` for the entire scheduled run — not one per iteration
— then crawls the same URL immediately, waits `interval` seconds, and
repeats. The interval wait is an injected
`sleep: Callable[[float], None] = time.sleep` parameter, never hardcoded,
so tests substitute a deterministic double instead of a real wall-clock
wait.

## 5. Per-iteration failure policy

Each iteration applies a documented recoverable-vs-terminal policy:

| Condition | Policy | Exit code |
|---|---|---|
| `CrawlerError` | Recoverable: logged, no output that iteration, loop continues after the usual wait | (loop continues) |
| `UnsupportedSourceError` | Terminal | `2` |
| A post-crawl `PersistenceWriteError` | Terminal | `5` |
| Any other unexpected `Exception` | Terminal | `1` |
| Reaching `--max-runs`, or a keyboard interrupt | Clean shutdown | `0` |

No new exit code was introduced; scheduled mode reuses exactly the
CLI-local exit codes ADR-023 and ADR-027 already define. A terminal
condition's cleanup is identical to single-shot mode's: the runtime's
context-manager `__exit__` always runs, including when a keyboard
interrupt propagates out of the `with` block.

## 6. Output contract

Single-shot mode's "exactly one JSON object on stdout" contract (ADR-023)
is unchanged when `--interval` is omitted. In scheduled mode, stdout
instead carries one JSON object per line per successful iteration — JSON
Lines, matching the `--output` file's existing format (ADR-027) — since a
repeating process cannot honestly promise "exactly one" object. `--output`,
when supplied together with `--interval`, still appends via the same
`FileCrawlResultSink` (ADR-024/ADR-027), once per successful iteration
only — a recoverable-failure iteration produces no output and persists
nothing.

## 7. No architectural, dependency, or credential change

Per ADR-028's explicit scope: no new parser family, no new `SourceProfile`
field, no new registry or composition behavior, no new sink type, and no
new third-party dependency were introduced. No credential or
authentication mechanism was introduced anywhere in `http/` or `identity/`.
`ArticleCrawlService` and `ApplicationRuntime` remain fully unaware of
persistence and of scheduling; this is entirely a CLI-layer addition, and
`ArticleCrawlService.crawl()`'s single-URL semantics are unchanged and
simply called repeatedly.

## 8. Testing architecture

- `tests/cli/test_scheduler.py` (new, 20 tests, 100% coverage of the new
  module): immediate first crawl with no initial wait, interval waiting
  between but not after the last iteration via an injected fake sleep,
  `--max-runs` bounding the iteration count (including the `max_runs=0`
  edge case), one runtime reused across all iterations, the recoverable
  `CrawlerError` path (including that it is logged), each terminal
  condition (`UnsupportedSourceError`, unexpected failure, unexpected item
  cardinality, persistence failure) stopping the loop immediately with its
  documented exit code, `--output` persisting once per successful
  iteration only, the JSON Lines stdout contract, a keyboard interrupt
  during a crawl and during a wait both exiting cleanly, bootstrap failure
  (both the startup-specific and unexpected-failure branches), and
  correlation-ID behavior (reset after the run, and distinct per
  iteration).
- `tests/cli/test_cli.py` (7 new tests): default invocation still
  dispatches to single-shot `run_crawl()` and never touches scheduled
  mode; `--interval` dispatches to `run_scheduled_crawl()` and never
  touches single-shot mode; `--interval`/`--output`/`--max-runs` are all
  forwarded together correctly; `--max-runs` without `--interval` is
  rejected; non-positive `--interval` and non-positive `--max-runs` are
  each rejected.
- `tests/integration/test_cli_process_boundary.py` (2 new tests): the real
  end-to-end pipeline (real `bootstrap_application()`, real
  `ApplicationRuntime`, real `SourceRegistry`, real `JsonLdArticleParser`)
  reached through scheduled mode, using `--max-runs 1` so the loop returns
  before ever calling `sleep` — proving the real wiring works without any
  real wall-clock wait — for both the base case and combined with
  `--output`.

No test performs a live network acquisition or a real wall-clock sleep,
consistent with the project's existing testing discipline.

## 9. Quality gates

The repository verification strategy uses:

- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy`
- `uv run pytest`
- `uv run pytest --cov=aa_crawler`, with the configured minimum of 70%
- `uv lock --check` for lockfile consistency
- `uv --cache-dir .uv-cache run pre-commit run --all-files`

Sprint 13 implementation, integration-verification, and documentation
tasks passed their applicable focused and repository-wide gates
throughout, both locally and via the real GitHub Actions CI pipeline
(Sprint 12). The verification run on the merged documentation-alignment
state (`b7c17770ba1022d7274e11b286148ea8d73aad65`) confirmed:

- Ruff: passed
- Ruff format check: passed
- mypy: passed
- pytest: 870 passed, 0 skipped, 0 xfailed, 0 failed, 0 errors
- Coverage: 94.70%, against the configured 70% threshold
- `uv lock --check`: passed
- pre-commit: all hooks passed
- Real GitHub Actions `pull_request`-event and `push`-event runs on this
  same merged state: both completed with a `success` conclusion
- Critical findings: 0
- Major findings: 0

An independent manual smoke test against the real CLI process (not
through pytest) confirmed the scheduled-mode argument path end-to-end:
`aa-crawler <unsupported-url> --interval 5 --max-runs 1` returned exit
code `2` (`EXIT_UNSUPPORTED_SOURCE`) without any network access (the
source gate rejects before acquisition), and both `--max-runs` without
`--interval` and `--interval 0` were rejected with clear argparse errors
at the real process boundary.

The final repository-wide verification, required for closure and run
after this completion report itself was merged, on
`d8c7bd234a1ed83a9e40283d6a04ca62ba868703`, confirmed the same result:

- Ruff: passed
- Ruff format check: passed
- mypy: passed
- pytest: 870 passed, 0 skipped, 0 xfailed, 0 failed, 0 errors
- Coverage: 94.70%, against the configured 70% threshold
- `uv lock --check`: passed
- pre-commit: all hooks passed
- Critical findings: 0
- Major findings: 0

The real GitHub Actions pipeline confirmed the same merged state
independently: both the `pull_request`-event run for this completion
report's own PR
(`https://github.com/muhammadarifalfani/aa-crawler/actions/runs/34104497406`)
and the subsequent `push`-event run on `main`
(`https://github.com/muhammadarifalfani/aa-crawler/actions/runs/34104699065`)
completed with a `success` conclusion.

## 10. Security and safety review

- `--interval` is off by default; no existing CLI invocation gains a new
  side effect unless the caller explicitly opts in.
- Scheduled mode selects only how often the same crawl repeats; it cannot
  override source, robots, retry, identity, or parser governance, and
  crawls only the one URL the caller supplied.
- No test or implementation code performs a live network acquisition of a
  real source or uses a real credential.
- A recoverable `CrawlerError` is logged without raw exception detail,
  headers, cookies, or response content, consistent with the CLI's
  existing logging discipline.
- No credential-handling code was added anywhere in the repository.

This report does not claim broad legal compliance, publisher
authorization, or production safety beyond these specific, implemented
controls. Scheduled mode makes repeated crawling of an already-enabled
source technically easier to leave running unattended; it does not itself
change robots.txt, retry, or identity policy, and an operator remains
responsible for how long a scheduled process is left running.

## 11. Current limitations

- Scheduled mode crawls only one URL per process; multi-URL/batch
  scheduled crawling remains separate, deferred future work.
- No health/liveness signaling exists for a long-running scheduled
  process; an external supervisor (if used) must infer liveness from the
  process's own exit.
- No distributed, multi-process, or queue/worker coordination exists;
  ADR-017 and ADR-019 remain exactly as Deferred/Proposed as before this
  sprint.
- Sub-second scheduling precision is not supported or tested.

## 12. Sprint 12 continuity

Sprint 12 delivered the GitHub Actions CI pipeline. Sprint 13 does not
modify `.github/workflows/ci.yml`; the same pipeline verified this
sprint's own pull requests (Section 9). This report does not revise or
reopen the Sprint 12 completion record.

## 13. Sprint 13 pull-request inventory

- PR #86 — ADR-028 CLI scheduled crawl mode decision
- PR #87 — `--interval`/`--max-runs` implementation and tests (unit and
  real end-to-end integration)
- PR #88 — README and Engineering Standards alignment
- PR #89 — Sprint 13 completion report

## 14. Sprint 13 closure checklist

- [x] Architecture Discovery presented evidence-backed candidates; project
      owner selected scheduled crawl mode
- [x] ADR-028 accepted
- [x] `-i`/`--interval SECONDS` and `--max-runs N` CLI arguments
      implemented
- [x] Default single-shot CLI invocation confirmed unchanged
- [x] Recoverable-vs-terminal per-iteration failure policy implemented and
      tested in both directions
- [x] One runtime reused across all scheduled iterations (not one per
      iteration)
- [x] `scheduler.py` reaches 100% test coverage
- [x] End-to-end integration tests added and passing, with no real
      wall-clock wait
- [x] Real GitHub Actions verification (pull_request and push events) on
      the merged implementation and documentation states
- [x] Independent manual real-process smoke test performed
- [x] README aligned
- [x] Engineering Standards aligned
- [x] Sprint 13 completion report created
- [x] Sprint 13 completion report merged
- [x] `main` synchronized after completion-report merge
- [x] Final repository verification passed after merge
- [x] Sprint 13 formally closed

## 15. Provisional post-Sprint-13 direction

No Sprint 14 architecture is approved by this report. Provisional future
areas already supported by current documentation include: multi-URL/batch
scheduled crawling, a third production source or platform proposal (with
its own legal/acquisition/credential review), a second concrete
persistence sink, non-HTML content acquisition, a credential/
authentication mechanism, separately reviewed redirect architecture,
alternate execution runtimes under ADR-019, distributed worker/queue
concerns under ADR-017, health/liveness signaling for long-running
processes, and CI enhancements not yet in scope (security scanning,
dependency-audit automation, performance benchmarking). Each requires its
own explicit scope and architecture approval before implementation.
Social media platforms remain explicitly out of scope for `aa_crawler`
itself, per the project owner's own stated direction.

## 16. Completion statement

This report was merged, local `main` was synchronized cleanly with
`origin/main` at `d8c7bd234a1ed83a9e40283d6a04ca62ba868703`, and the final
repository-wide quality gate — both the local command sequence and the
real GitHub Actions pipeline itself — passed on that merged state with no
Critical or Major findings.

**Sprint 13 is formally closed.**
