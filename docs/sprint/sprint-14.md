# Sprint 14 Completion Report

## 1. Status

Sprint 14 implementation is complete. Integration verification is
complete. Documentation alignment is complete. This completion report was
merged, local `main` was subsequently synchronized cleanly with
`origin/main`, and the final repository-wide verification (Section 9)
passed on that merged state with no Critical or Major findings.

**Sprint 14 is formally closed.**

## 2. Objective

Sprint 14's Architecture Discovery evaluated ADR-023's own long-standing
named review trigger — "Multi-URL batch input or JSON Lines output is
proposed" — and found that Sprint 13 had already satisfied half of it
(JSON Lines stdout, via scheduled mode) without needing to change
ADR-023's single-shot contract at all. The project owner chose to resolve
the remaining half this sprint: letting the CLI crawl more than one URL,
over two alternatives (a second concrete persistence sink; activating a
third production source). This directly advances the project owner's
stated "many sources" goal, reusing ADR-028's proven recoverable-vs-
terminal pattern rather than starting a parallel design.

## 3. Architecture decision

- [ADR-029 — CLI Batch/Multi-URL Input](../adr/0029-cli-batch-url-input.md)
  is **Accepted** and defines the optional `--urls-file PATH` argument
  (mutually exclusive with the positional `url`), one reused
  `ApplicationRuntime` for the whole run, reuse of ADR-028's injectable
  sleep for scheduled batch mode, and a per-URL failure policy that
  deliberately diverges from ADR-028: `UnsupportedSourceError` is
  recoverable within a batch (skip that URL, continue) rather than
  terminal, since one bad URL among many should not abort the rest of the
  list. No new exit code is introduced; partial success remains process
  exit `0`, distinguishable via stdout/log output only.

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
- [ADR-028 — CLI Scheduled Crawl Mode](../adr/0028-cli-scheduled-crawl-mode.md)

The [ADR index](../adr/README.md) now records 22 Accepted, 2 Proposed, 2
Deferred, and 0 Superseded decisions. ADR-023's "Multi-URL batch input or
JSON Lines output is proposed" review trigger is now fully resolved
(JSON Lines by Sprint 13, batch input by this sprint) without ADR-023
itself needing to change. ADR-017 and ADR-019 remain Deferred/Proposed:
sequential, synchronous crawling of a list of URLs triggers neither.

## 4. Implementation: `run_batch_crawl()` and `run_scheduled_batch_crawl()`

[`src/aa_crawler/cli/batch.py`](../../src/aa_crawler/cli/batch.py) (new)
implements the ADR-029 decision. The CLI gained one new optional argument:

```text
aa-crawler --urls-file sources.txt                       # one pass, then exit
aa-crawler --urls-file sources.txt -o results.jsonl       # also persists
aa-crawler --urls-file sources.txt --interval 300         # re-crawl the list every 5 minutes
```

`--urls-file` is mutually exclusive with the positional `url`; argument
parsing rejects supplying both or neither. The file format is one
absolute HTTPS URL per line; blank lines and lines starting with `#` are
skipped as comments, and an empty result is rejected with a clear error.
`run_crawl()` and `run_scheduled_crawl()` (ADR-023/ADR-028) are completely
unmodified — every existing single-URL test continues to hold without
change.

## 5. Per-URL failure policy (diverging from ADR-028)

| Condition | Policy | Rationale |
|---|---|---|
| `UnsupportedSourceError` for one URL | **Recoverable** (differs from ADR-028) | One bad URL among many should not abort a batch; unlike single-URL scheduled mode, this is not the *same* URL being retried forever. |
| `CrawlerError` for one URL | Recoverable | Same reasoning as ADR-028: plausibly transient. |
| A post-crawl `PersistenceWriteError` | Terminal | Likely systemic; stopping loudly beats silently dropping results for every remaining URL. |
| Any other unexpected `Exception` | Terminal | Conservative default, matching ADR-028. |
| Reaching `--max-runs`, or a keyboard interrupt | Clean shutdown (`EXIT_SUCCESS`) | Same as ADR-028. |

In scheduled batch mode, `--max-runs` bounds the number of full passes
over the URL list, not the number of individual URLs. No new exit code
was introduced; batch mode reuses exactly the CLI-local exit codes
ADR-023, ADR-027, and ADR-028 already define.

## 6. Output contract

Batch mode's stdout is JSON Lines — one JSON object per line per
successful URL — for both single-shot and scheduled batch mode, matching
the convention ADR-028 already established. `--output`, when supplied,
still appends via the same `FileCrawlResultSink` (ADR-024/ADR-027), once
per successful URL only.

## 7. No architectural, dependency, or credential change

Per ADR-029's explicit scope: no new parser family, no new `SourceProfile`
field, no new registry or composition behavior, no new sink type, and no
new third-party dependency were introduced. No credential or
authentication mechanism was introduced anywhere in `http/` or `identity/`.
`ArticleCrawlService` and `ApplicationRuntime` remain fully unaware of
persistence, scheduling, and batching; this is entirely a CLI-layer
addition, and `ArticleCrawlService.crawl()`'s single-URL semantics are
unchanged and simply called once per URL in a list.

## 8. Testing architecture

- `tests/cli/test_batch.py` (new, 22 tests, 100% coverage of the new
  module): every URL crawled in order, one runtime reused across the
  whole pass, `UnsupportedSourceError` and `CrawlerError` each skipping
  only their own URL and continuing (the key divergence from ADR-028,
  explicitly tested and logged), each terminal condition stopping the
  batch immediately with its documented exit code, `--output` persisting
  once per successful URL only, the JSON Lines stdout contract, scheduled
  batch mode's immediate first pass and interval waiting between passes,
  `--max-runs` bounding pass count (not URL count) including the
  `max_runs=0` edge case, one runtime reused across all passes, a
  keyboard interrupt during a crawl and during a wait both exiting
  cleanly, and bootstrap failure (both branches).
- `tests/cli/test_cli.py` (11 new tests): supplying neither or both of
  `url`/`--urls-file` is rejected; `--urls-file` dispatches to
  `run_batch_crawl()` and never touches single-shot or scheduled
  single-URL mode; `--urls-file` with `--interval` dispatches to
  `run_scheduled_batch_crawl()`; URL-file parsing skips comments and
  blank lines correctly; a missing or empty URLs file is rejected with a
  clear error; `--max-runs` without `--interval` is rejected even with
  `--urls-file`.
- `tests/integration/test_cli_process_boundary.py` (2 new tests): the
  real end-to-end pipeline reached through `--urls-file` batch mode (two
  URLs, both real registry/parser composition, real fetcher called
  twice) and through scheduled batch mode with `--max-runs 1` (bounding
  the loop so `sleep` is never called, keeping the test fully
  deterministic).

No test performs a live network acquisition or a real wall-clock sleep,
consistent with ADR-028's precedent.

## 9. Quality gates

The repository verification strategy uses:

- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy`
- `uv run pytest`
- `uv run pytest --cov=aa_crawler`, with the configured minimum of 70%
- `uv lock --check` for lockfile consistency
- `uv --cache-dir .uv-cache run pre-commit run --all-files`

Sprint 14 implementation, integration-verification, and documentation
tasks passed their applicable focused and repository-wide gates
throughout, both locally and via the real GitHub Actions CI pipeline
(Sprint 12). The verification run on the merged documentation-alignment
state (`12f4c79840f923aa1ced0d8d2b42c1ab01641c3c`) confirmed:

- Ruff: passed
- Ruff format check: passed
- mypy: passed
- pytest: 902 passed, 0 skipped, 0 xfailed, 0 failed, 0 errors
- Coverage: 94.97%, against the configured 70% threshold
- `uv lock --check`: passed
- pre-commit: all hooks passed
- Real GitHub Actions `pull_request`-event and `push`-event runs on this
  same merged state: both completed with a `success` conclusion
- Critical findings: 0
- Major findings: 0

An independent manual smoke test against the real CLI process (not
through pytest) confirmed the batch-mode argument path and its diverging
failure policy end-to-end: a `--urls-file` containing two unsupported URLs
returned exit code `0` (both were logged and skipped as recoverable —
confirming the ADR-029 divergence from ADR-028's terminal treatment of
the same condition) without any network access; both `url --urls-file`
supplied together and neither supplied were rejected with clear argparse
errors (exit `2`) at the real process boundary.

The final repository-wide verification, required for closure and run
after this completion report itself was merged, on
`e3560496fbed616d489831a28922ad9e495e04a8`, confirmed the same result:

- Ruff: passed
- Ruff format check: passed
- mypy: passed
- pytest: 902 passed, 0 skipped, 0 xfailed, 0 failed, 0 errors
- Coverage: 94.97%, against the configured 70% threshold
- `uv lock --check`: passed
- pre-commit: all hooks passed
- Critical findings: 0
- Major findings: 0

The real GitHub Actions pipeline confirmed the same merged state
independently: both the `pull_request`-event run for this completion
report's own PR
(`https://github.com/muhammadarifalfani/aa-crawler/actions/runs/34108733505`)
and the subsequent `push`-event run on `main`
(`https://github.com/muhammadarifalfani/aa-crawler/actions/runs/34108835694`)
completed with a `success` conclusion.

## 10. Security and safety review

- `--urls-file` is off by default (mutually exclusive with, not additive
  to, the positional `url`); no existing single-URL invocation gains any
  new behavior.
- Batch mode selects only how many URLs are crawled and how; it cannot
  override source, robots, retry, identity, or parser governance for any
  URL in the list.
- No test or implementation code performs a live network acquisition of a
  real source or uses a real credential.
- A recoverable per-URL failure is logged without raw exception detail,
  headers, cookies, or response content, consistent with the CLI's
  existing logging discipline.
- No credential-handling code was added anywhere in the repository.

This report does not claim broad legal compliance, publisher
authorization, or production safety beyond these specific, implemented
controls. Batch mode makes crawling many already-enabled sources in one
invocation easier; it does not itself change robots.txt, retry, or
identity policy for any of them, and an operator remains responsible for
the contents of any `--urls-file` they supply.

## 11. Current limitations

- `--urls-file` supports only a local filesystem path; no remote list
  source (URL, database query, message topic) is supported.
- URLs within one pass are crawled strictly sequentially; no per-URL
  concurrency exists.
- No caller-visible distinction between "fully successful" and "partially
  successful" batch runs beyond stdout/log output; no new exit-code
  category was introduced (a deliberate ADR-029 decision).
- No health/liveness signaling exists for a long-running scheduled batch
  process, same limitation as ADR-028's scheduled single-URL mode.

## 12. Sprint 13 continuity

Sprint 13 delivered single-URL scheduled crawl mode (ADR-028). Sprint 14
does not modify `aa_crawler.cli.scheduler` or `aa_crawler.cli.app` at all;
`run_crawl()` and `run_scheduled_crawl()` remain byte-for-byte unchanged,
verified by the fact that every existing test for both continues to pass
without modification. This report does not revise or reopen the Sprint 13
completion record.

## 13. Sprint 14 pull-request inventory

- PR #91 — ADR-029 CLI batch/multi-URL input decision
- PR #92 — `--urls-file` implementation and tests (unit and real
  end-to-end integration)
- PR #93 — README and Engineering Standards alignment
- PR #94 — Sprint 14 completion report

## 14. Sprint 14 closure checklist

- [x] Architecture Discovery presented evidence-backed candidates; project
      owner selected batch/multi-URL input
- [x] ADR-029 accepted, resolving ADR-023's long-standing review trigger
- [x] `--urls-file PATH` CLI argument implemented, mutually exclusive with
      the positional `url`
- [x] `run_crawl()` and `run_scheduled_crawl()` confirmed unchanged (every
      existing single-URL test passes without modification)
- [x] Per-URL recoverable-vs-terminal failure policy implemented and
      tested, including the deliberate `UnsupportedSourceError` divergence
      from ADR-028
- [x] `cli/batch.py` reaches 100% test coverage
- [x] End-to-end integration tests added and passing, with no real
      wall-clock wait
- [x] Real GitHub Actions verification (pull_request and push events) on
      the merged implementation and documentation states
- [x] Independent manual real-process smoke test performed, confirming
      the ADR-029/ADR-028 divergence
- [x] README aligned
- [x] Engineering Standards aligned
- [x] Sprint 14 completion report created
- [x] Sprint 14 completion report merged
- [x] `main` synchronized after completion-report merge
- [x] Final repository verification passed after merge
- [x] Sprint 14 formally closed

## 15. Provisional post-Sprint-14 direction

No Sprint 15 architecture is approved by this report. Provisional future
areas already supported by current documentation include: a second
concrete persistence sink, a third production source or platform proposal
(with its own legal/acquisition/credential review), non-HTML content
acquisition, a credential/authentication mechanism, separately reviewed
redirect architecture, alternate execution runtimes under ADR-019,
concurrent per-URL crawling within one pass, a remote/dynamic URL-list
source, distributed worker/queue concerns under ADR-017, health/liveness
signaling for long-running processes, and CI enhancements not yet in
scope (security scanning, dependency-audit automation, performance
benchmarking). Each requires its own explicit scope and architecture
approval before implementation. Social media platforms remain explicitly
out of scope for `aa_crawler` itself, per the project owner's own stated
direction.

## 16. Completion statement

This report was merged, local `main` was synchronized cleanly with
`origin/main` at `e3560496fbed616d489831a28922ad9e495e04a8`, and the final
repository-wide quality gate — both the local command sequence and the
real GitHub Actions pipeline itself — passed on that merged state with no
Critical or Major findings.

**Sprint 14 is formally closed.**
