# Sprint 16 Completion Report

## 1. Status

Sprint 16 implementation is complete. Integration verification is
complete. Documentation alignment is complete. This completion report will
be merged, local `main` will subsequently be synchronized cleanly with
`origin/main`, and a final repository-wide verification will run on that
merged state before formal closure.

**Sprint 16 is pending formal closure** (see Section 16).

## 2. Objective

Sprint 16's Architecture Discovery evaluated ADR-030's own named review
trigger — "CLI wiring for sink selection is proposed" — and found it
directly actionable: `SqliteCrawlResultSink`'s idempotency, added in
Sprint 15, was reachable only through direct Python composition, leaving
CLI users with no way to benefit from it at all. The project owner chose
to resolve this over two alternatives (a third production source; CI
security-scanning enhancements), completing the ADR-024-then-ADR-027
precedent a second time: the port and sink existed first, CLI exposure
follows as its own separately-approved step.

## 3. Architecture decision

- [ADR-031 — CLI Sink Selection](../adr/0031-cli-sink-selection.md) is
  **Accepted** and defines an optional `--sink {file,sqlite}` argument,
  valid only together with `--output`, resolved once in `main()` to a
  concrete sink class and threaded through all four crawl entry
  functions as an injectable `sink_factory` parameter defaulting to
  `FileCrawlResultSink`. It explicitly rejects file-extension inference
  (implicit behavior this project has consistently avoided) and
  persisting to more than one sink at once (unneeded complexity) as
  considered alternatives.

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
- [ADR-029 — CLI Batch/Multi-URL Input](../adr/0029-cli-batch-url-input.md)
- [ADR-030 — SQLite Crawl Result Sink](../adr/0030-sqlite-crawl-result-sink.md)

The [ADR index](../adr/README.md) now records 24 Accepted, 2 Proposed, 2
Deferred, and 0 Superseded decisions. ADR-030's own named review trigger
is now answered.

## 4. Implementation: `--sink` and the injectable `sink_factory`

The CLI gained one new optional argument, valid only with `--output`:

```text
aa-crawler <url> -o results.jsonl                 # unchanged: file sink (default)
aa-crawler <url> -o results.jsonl --sink file      # equivalent, explicit
aa-crawler <url> -o results.db --sink sqlite       # NEW: SQLite sink
```

A new `SinkFactory` `Protocol` in
[`src/aa_crawler/cli/app.py`](../../src/aa_crawler/cli/app.py) describes
the shared `__call__(self, *, destination: Path) -> BaseCrawlResultSink`
shape both `FileCrawlResultSink` and `SqliteCrawlResultSink` already
satisfy, with no explicit registration required. `cli/__init__.py`'s
`main()` resolves `--sink`'s choice to the corresponding class once, via
a small `_SINK_FACTORIES` mapping, and passes it down as a new
`sink_factory` keyword parameter to `run_crawl()`, `run_scheduled_crawl()`
(`cli/scheduler.py`), and `run_batch_crawl()`/`run_scheduled_batch_crawl()`
(`cli/batch.py`) — each function's internals changed from constructing
`FileCrawlResultSink(destination=output)` directly to
`sink_factory(destination=output)`. Every function defaults
`sink_factory` to `FileCrawlResultSink`, so omitting `--sink` (or passing
`--sink file` explicitly) preserves ADR-027/028/029's exact original
behavior.

## 5. No new exit code, no change to failure policy

Per ADR-031's explicit scope: `PersistenceWriteError` from either sink
still maps to `EXIT_PERSISTENCE_FAILURE`, unchanged — both sinks already
raise this same exception type per ADR-030's design. Scheduled mode's and
batch mode's per-iteration/per-URL recoverable-vs-terminal failure
policies (ADR-028, ADR-029) are entirely unaffected; `--sink` only
changes which class constructs the sink, not how failures are handled
after that.

## 6. Argument validation

`--sink` without `--output` is rejected by argument parsing
(`--sink requires --output`), since there is then no destination for it
to target — mirroring `--max-runs`'s existing dependency on `--interval`.
An invalid `--sink` value is rejected by `argparse`'s own `choices`
validation. Supplying both `url` and `--urls-file`, or neither, continues
to be rejected exactly as before; `--sink` does not interact with that
validation.

## 7. No architectural change beyond the CLI-layer wiring

`FileCrawlResultSink`, `SqliteCrawlResultSink`, `ArticleCrawlService`, and
`ApplicationRuntime` are completely unmodified. No new third-party
dependency was introduced. No credential or authentication mechanism was
introduced anywhere in `http/` or `identity/`. This is entirely a
CLI-layer wiring change reusing sinks that already existed.

## 8. Testing architecture

- `tests/cli/test_cli.py` (8 new tests): `--sink` without `--output` is
  rejected; an invalid `--sink` value is rejected; omitting `--sink` (or
  passing `--sink file` explicitly) resolves to `FileCrawlResultSink`;
  `--sink sqlite` resolves to `SqliteCrawlResultSink` for each of the
  four dispatch paths — single-shot, scheduled, batch, and scheduled
  batch. Additionally, 8 existing fake-function signatures across earlier
  ADR-028/ADR-029 dispatch tests were updated to accept the new
  `sink_factory` keyword, since `main()` now always passes it explicitly;
  no test's assertions or scenario changed, only the fake signatures.
- `tests/integration/test_cli_process_boundary.py` (2 new tests): the
  real end-to-end pipeline reached through `--sink sqlite --output <path>`,
  confirmed against a real SQLite database via the real `sqlite3` module
  (not a fake), and a companion test confirming `--sink` omitted still
  produces the unchanged file-sink output through the same real pipeline.

No test performs a live network acquisition or a real wall-clock sleep,
consistent with prior sprints' precedent.

## 9. Quality gates

The repository verification strategy uses:

- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy`
- `uv run pytest`
- `uv run pytest --cov=aa_crawler`, with the configured minimum of 70%
- `uv lock --check` for lockfile consistency
- `uv --cache-dir .uv-cache run pre-commit run --all-files`

Sprint 16 implementation, integration-verification, and documentation
tasks passed their applicable focused and repository-wide gates
throughout, both locally and via the real GitHub Actions CI pipeline
(Sprint 12). The verification run on the merged documentation-alignment
state (`b767899aa44fe558c6866269ff82af0a9e110dc3`) confirmed:

- Ruff: passed
- Ruff format check: passed
- mypy: passed
- pytest: 924 passed, 0 skipped, 0 xfailed, 0 failed, 0 errors
- Coverage: 95.05%, against the configured 70% threshold
- `uv lock --check`: passed
- pre-commit: all hooks passed
- Real GitHub Actions `pull_request`-event and `push`-event runs on this
  same merged state: both completed with a `success` conclusion
- Critical findings: 0
- Major findings: 0

An independent manual smoke test against the real CLI process (not
through pytest) confirmed the full `--sink` behavior end-to-end:
`--sink sqlite` without `--output` was rejected (exit `2`, clear
message); an invalid `--sink` value was rejected by `argparse`'s own
validation (exit `2`); and `--sink sqlite --output <path>` with an
unsupported URL correctly passed argument validation and reached the
real crawl pipeline, failing at the expected point (exit `2`,
`unsupported_source`) rather than at argument parsing — confirming
`--sink` does not interfere with the existing pipeline when the sink
itself is never reached.

The final repository-wide verification, required for closure and run
after this completion report itself is merged, will be recorded in
Section 16 below at closure time.

## 10. Security and safety review

- `--sink` is off by default (implicitly `file`, unchanged) and requires
  `--output` to have any effect; no existing invocation gains a new side
  effect.
- `--sink` selects only which concrete sink class persists a result; it
  cannot override source, robots, retry, identity, or parser governance.
- No test or implementation code performs a live network acquisition of a
  real source or uses a real credential.
- No credential-handling code was added anywhere in the repository.

This report does not claim broad legal compliance, publisher
authorization, or production safety beyond these specific, implemented
controls. `--sink sqlite` makes `SqliteCrawlResultSink`'s idempotency
reachable from the CLI; it does not itself change what is crawled or how.

## 11. Current limitations

- Persisting to more than one sink in a single invocation is not
  supported (a considered-and-rejected option in ADR-031); each
  invocation targets exactly one destination and one sink.
- `--sink`'s only two choices are `file` and `sqlite`; a third sink type,
  if ever proposed, would extend the same pattern without needing to
  revisit ADR-031's core design.
- All of `SqliteCrawlResultSink`'s own limitations (Sprint 15) remain:
  upsert-by-`requested_url` keeps only the latest crawl per URL, and
  concurrent writers from separate processes are not addressed.

## 12. Sprint 15 continuity

Sprint 15 delivered `SqliteCrawlResultSink` itself, deliberately without
CLI wiring. Sprint 16 delivers exactly that deferred wiring; it does not
modify `SqliteCrawlResultSink`'s implementation, schema, or upsert
behavior at all. This report does not revise or reopen the Sprint 15
completion record.

## 13. Sprint 16 pull-request inventory

- PR #101 — ADR-031 CLI sink selection decision
- PR #102 — `--sink` implementation and tests (unit and real end-to-end
  integration)
- PR #103 — README and Engineering Standards alignment
- PR #(pending) — Sprint 16 completion report (this document)

## 14. Sprint 16 closure checklist

- [x] Architecture Discovery presented evidence-backed candidates; project
      owner selected CLI sink selection
- [x] ADR-031 accepted, resolving ADR-030's own named review trigger
- [x] `--sink {file,sqlite}` CLI argument implemented, valid only with
      `--output`
- [x] `SinkFactory` Protocol added; `sink_factory` threaded through all
      four crawl entry functions, defaulting to `FileCrawlResultSink`
- [x] Every existing invocation confirmed unchanged when `--sink` is
      omitted (all prior tests pass with only fake-signature updates,
      no scenario or assertion changes)
- [x] No new exit code; existing failure policies unaffected
- [x] End-to-end integration tests added and passing, proving a real
      SQLite database via the real `sqlite3` module
- [x] Real GitHub Actions verification (pull_request and push events) on
      the merged implementation and documentation states
- [x] Independent manual real-process smoke test performed
- [x] README aligned
- [x] Engineering Standards aligned
- [ ] Sprint 16 completion report created (this document)
- [ ] Sprint 16 completion report merged
- [ ] `main` synchronized after completion-report merge
- [ ] Final repository verification passed after merge
- [ ] Sprint 16 formally closed

## 15. Provisional post-Sprint-16 direction

No Sprint 17 architecture is approved by this report. Provisional future
areas already supported by current documentation include: persisting to
more than one sink in a single invocation (ADR-031's own deferred
follow-up), a third production source or platform proposal (with its own
legal/acquisition/credential review), non-HTML content acquisition, a
credential/authentication mechanism, separately reviewed redirect
architecture, alternate execution runtimes under ADR-019, concurrent
per-URL crawling within one batch pass, a remote/dynamic URL-list source,
distributed worker/queue concerns under ADR-017, and CI enhancements not
yet in scope (security scanning, dependency-audit automation, performance
benchmarking). Each requires its own explicit scope and architecture
approval before implementation. Social media platforms remain explicitly
out of scope for `aa_crawler` itself, per the project owner's own stated
direction.

## 16. Completion statement

This report will be merged, local `main` will be synchronized cleanly
with `origin/main`, and the final repository-wide quality gate will be
recorded here at closure time.

**Sprint 16 is pending formal closure.**
