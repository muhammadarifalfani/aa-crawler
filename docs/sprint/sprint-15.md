# Sprint 15 Completion Report

## 1. Status

Sprint 15 implementation is complete. Integration verification is
complete. Documentation alignment is complete. This completion report was
merged, local `main` was subsequently synchronized cleanly with
`origin/main`, and the final repository-wide verification (Section 7)
passed on that merged state with no Critical or Major findings.

**Sprint 15 is formally closed.**

## 2. Objective

Sprint 15's Architecture Discovery evaluated ADR-024's own named review
triggers — "a database or schema technology needs selecting for real
deployment" and "worker, queue, or scheduler work is scheduled and needs
durable state" — against the current architecture, and found both newly
concrete now that Sprint 13 (ADR-028, scheduled mode) and Sprint 14
(ADR-029, batch mode) exist: running either against the existing
append-only `FileCrawlResultSink` for real means the same URL is
re-appended, unbounded, on every interval or pass, with no
deduplication. The project owner chose to resolve this over two
alternatives (a third production source; CI security-scanning
enhancements), reusing the project's small-core-dependency philosophy
rather than adopting a database driver dependency.

## 3. Architecture decision

- [ADR-030 — SQLite Crawl Result Sink](../adr/0030-sqlite-crawl-result-sink.md)
  is **Accepted** and defines `SqliteCrawlResultSink`, a second concrete
  `BaseCrawlResultSink` implementation using only the standard-library
  `sqlite3` module (no new runtime dependency), upserting by
  `item.data["requested_url"]` into one `crawl_results` table for real
  idempotency. CLI wiring (a flag to select this sink) is explicitly
  deferred, mirroring the ADR-024-then-ADR-027 precedent: this ADR adds
  the sink itself, exactly as ADR-024 added the first one without CLI
  exposure.

Earlier accepted decisions remain authoritative in their existing areas:

- [ADR-013 — Pydantic Dependency Classification](../adr/0013-pydantic-dependency-classification.md)
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

The [ADR index](../adr/README.md) now records 23 Accepted, 2 Proposed, 2
Deferred, and 0 Superseded decisions. ADR-024's two review triggers named
above are now answered; ADR-017 (metadata portability) remains Deferred —
this sink still stores `item.data` as an opaque JSON payload, not a
typed/portable schema, so its trigger conditions remain unmet.

## 4. Implementation: `SqliteCrawlResultSink`

[`src/aa_crawler/persistence/sqlite_sink.py`](../../src/aa_crawler/persistence/sqlite_sink.py)
(new) implements the ADR-030 decision:

```python
from pathlib import Path

from aa_crawler.persistence import SqliteCrawlResultSink

sink = SqliteCrawlResultSink(destination=Path("data/processed/results.db"))
for item in items:
    sink.save(item)
```

`save(item)` upserts by `item.data["requested_url"]` into one
`crawl_results` table
(`requested_url TEXT PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT NOT NULL`),
created automatically on first use via `CREATE TABLE IF NOT EXISTS`.
Re-saving the same `requested_url` replaces
`payload` and `updated_at` (an ISO 8601 UTC timestamp) instead of
duplicating a row. `PersistenceWriteError` is raised when: serialization
fails (matching `FileCrawlResultSink`'s existing precedent), the item's
`requested_url` is missing, empty, or not a string, or the database write
itself fails (an invalid destination or non-database file, for example).
`FileCrawlResultSink` is completely unmodified.

## 5. No CLI wiring, no architectural change beyond the persistence layer

Per ADR-030's explicit scope: `SqliteCrawlResultSink` is not referenced
anywhere in `aa_crawler.cli`. `aa_crawler.cli.app`'s existing `--output`
argument still constructs only `FileCrawlResultSink`, unchanged.
`ArticleCrawlService` and `ApplicationRuntime` remain fully unaware of
persistence, as before. No new third-party dependency was introduced;
`sqlite3` ships with every supported Python version. No credential or
authentication mechanism was introduced anywhere in `http/` or
`identity/`.

## 6. Testing architecture

- `tests/persistence/test_sqlite_sink.py` (new, 12 tests, 100% coverage
  of the new module): the database and table are created automatically
  on first `save()`; a repeated `save()` for the same `requested_url`
  upserts (one row, latest payload) rather than duplicating; distinct
  URLs produce distinct rows; `updated_at` is written on every upsert;
  the `destination` property exposes the configured path; a
  serialization failure raises `PersistenceWriteError` before any
  database file is created; a missing, empty, `None`, or non-string
  `requested_url` is each rejected (parametrized); a missing parent
  directory raises `PersistenceWriteError` at connection time; and a
  destination that is not a valid SQLite database raises
  `PersistenceWriteError` at the first `execute()` call — a distinct
  failure path from the connection-time failure, both explicitly
  exercised to reach full branch coverage.
- No test performs a live network acquisition; all tests exercise
  `SqliteCrawlResultSink` directly against `tmp_path`-based database
  files, consistent with `FileCrawlResultSink`'s existing test
  discipline.

## 7. Quality gates

The repository verification strategy uses:

- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy`
- `uv run pytest`
- `uv run pytest --cov=aa_crawler`, with the configured minimum of 70%
- `uv lock --check` for lockfile consistency
- `uv --cache-dir .uv-cache run pre-commit run --all-files`

Sprint 15 implementation, integration-verification, and documentation
tasks passed their applicable focused and repository-wide gates
throughout, both locally and via the real GitHub Actions CI pipeline
(Sprint 12). The verification run on the merged documentation-alignment
state (`59f8ec292f162692e5208d7e83bc9e8cfd9fbd69`) confirmed:

- Ruff: passed
- Ruff format check: passed
- mypy: passed
- pytest: 914 passed, 0 skipped, 0 xfailed, 0 failed, 0 errors
- Coverage: 95.04%, against the configured 70% threshold
- `uv lock --check`: passed
- pre-commit: all hooks passed
- Real GitHub Actions `pull_request`-event and `push`-event runs on this
  same merged state: both completed with a `success` conclusion
- Critical findings: 0
- Major findings: 0

An independent manual smoke test against the real `sqlite3` module (not
through pytest, and not via the CLI, since ADR-030 has no CLI surface)
confirmed the idempotency claim concretely: four `save()` calls — three
for the same `requested_url` with different headlines, one for a
different `requested_url` — produced exactly two rows, each holding the
latest payload for its URL, not four rows.

The final repository-wide verification, required for closure and run
after this completion report itself was merged, on
`f8e3f64f47abdd77cd16eecefbaac66b42057c82`, confirmed the same result:

- Ruff: passed
- Ruff format check: passed
- mypy: passed
- pytest: 914 passed, 0 skipped, 0 xfailed, 0 failed, 0 errors
- Coverage: 95.04%, against the configured 70% threshold
- `uv lock --check`: passed
- pre-commit: all hooks passed
- Critical findings: 0
- Major findings: 0

The real GitHub Actions pipeline confirmed the same merged state
independently: both the `pull_request`-event run for this completion
report's own PR
(`https://github.com/muhammadarifalfani/aa-crawler/actions/runs/34112253831`)
and the subsequent `push`-event run on `main`
(`https://github.com/muhammadarifalfani/aa-crawler/actions/runs/34112347204`)
completed with a `success` conclusion.

## 8. Security and safety review

- No credential-handling code was added anywhere in the repository.
- `SqliteCrawlResultSink` performs only local file I/O against a
  caller-supplied path; it makes no network request and has no CLI
  surface to be reached from an untrusted invocation.
- Serialization and write failures are wrapped in `PersistenceWriteError`
  without leaking raw `sqlite3.Error`/`OSError` detail beyond what the
  existing `FileCrawlResultSink` precedent already exposes.
- No new runtime dependency was introduced; the standard-library
  `sqlite3` module's own security posture is unchanged by this ADR.

This report does not claim broad legal compliance, publisher
authorization, or production safety beyond these specific, implemented
controls. `SqliteCrawlResultSink` is not yet reachable from the CLI, so
this sprint introduces no new caller-facing attack surface.

## 9. Current limitations

- `SqliteCrawlResultSink` is not CLI-selectable; a caller must compose it
  directly in Python. No CLI flag exists to choose between it and
  `FileCrawlResultSink`.
- Upsert-by-`requested_url` keeps only the latest successful crawl per
  URL; no history of prior crawls for that URL is retained by this sink.
- Concurrent writers from separate processes are not addressed.
- The stored payload remains an opaque JSON blob, not a typed or
  queryable-by-field schema beyond `requested_url` itself.

## 10. Sprint 14 continuity

Sprint 14 delivered CLI batch/multi-URL input (ADR-029). Sprint 15 does
not modify `aa_crawler.cli` at all — `cli/batch.py`, `cli/scheduler.py`,
and `cli/app.py` are untouched, verified by the fact that every existing
CLI test continues to pass without modification. This report does not
revise or reopen the Sprint 14 completion record.

## 11. Sprint 15 pull-request inventory

- PR #96 — ADR-030 SQLite crawl result sink decision
- PR #97 — `SqliteCrawlResultSink` implementation and tests
- PR #98 — README and Engineering Standards alignment
- PR #99 — Sprint 15 completion report

## 12. Sprint 15 closure checklist

- [x] Architecture Discovery presented evidence-backed candidates; project
      owner selected a second persistence sink
- [x] ADR-030 accepted, resolving ADR-024's two named review triggers
- [x] `SqliteCrawlResultSink` implemented with upsert-by-`requested_url`
      idempotency
- [x] `FileCrawlResultSink` confirmed unchanged (every existing test
      passes without modification)
- [x] No CLI wiring introduced, per ADR-030's explicit deferral
- [x] `persistence/sqlite_sink.py` reaches 100% test coverage, including
      both connect-time and execute-time failure paths
- [x] Real GitHub Actions verification (pull_request and push events) on
      the merged implementation and documentation states
- [x] Independent manual smoke test performed, confirming idempotent
      upsert against the real `sqlite3` module
- [x] README aligned
- [x] Engineering Standards aligned
- [x] Sprint 15 completion report created
- [x] Sprint 15 completion report merged
- [x] `main` synchronized after completion-report merge
- [x] Final repository verification passed after merge
- [x] Sprint 15 formally closed

## 13. Provisional post-Sprint-15 direction

No Sprint 16 architecture is approved by this report. Provisional future
areas already supported by current documentation include: CLI wiring for
sink selection (ADR-030's own deferred follow-up), a third production
source or platform proposal (with its own legal/acquisition/credential
review), non-HTML content acquisition, a credential/authentication
mechanism, separately reviewed redirect architecture, alternate execution
runtimes under ADR-019, concurrent per-URL crawling within one batch
pass, a remote/dynamic URL-list source, distributed worker/queue concerns
under ADR-017, and CI enhancements not yet in scope (security scanning,
dependency-audit automation, performance benchmarking). Each requires its
own explicit scope and architecture approval before implementation.
Social media platforms remain explicitly out of scope for `aa_crawler`
itself, per the project owner's own stated direction.

## 14. Completion statement

This report was merged, local `main` was synchronized cleanly with
`origin/main` at `f8e3f64f47abdd77cd16eecefbaac66b42057c82`, and the final
repository-wide quality gate — both the local command sequence and the
real GitHub Actions pipeline itself — passed on that merged state with no
Critical or Major findings.

**Sprint 15 is formally closed.**
