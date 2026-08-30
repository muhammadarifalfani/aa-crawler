# Sprint 7 Completion Report

## 1. Status

Sprint 7 implementation is complete. Integration verification is complete.
Documentation alignment is complete. This completion report has been
created.

Formal closure must not be declared until this report is merged, the final
repository quality gate passes on the merged state, and local `main` is
synchronized cleanly with `origin/main`.

## 2. Objective

Sprint 7 provided an optional, application-level persistence boundary for
crawl results, allowing a caller that already holds a produced `CrawlerItem`
to durably persist it without any lower-layer component gaining awareness of
persistence. Sprint 7 narrowly answers ADR-017's "persistence" review
trigger; it does not resolve plugin, queue, or worker portability, does not
wire persistence into the CLI or application service, and does not select a
database or schema.

## 3. Architecture decision

- [ADR-024 — Application-Level Persistence Boundary for Crawl Results](../adr/0024-application-level-persistence-boundary.md)
  is **Accepted** and defines the persistence port's ownership (neither
  `ArticleCrawlService`, `ApplicationRuntime`, nor `aa_crawler.cli`), its
  conceptual location (`aa_crawler/persistence/`), its reuse of the CLI's
  proven JSON-safe serialization pattern, its explicit non-guarantee of
  idempotency, and its non-goals (no database/schema selection, no CLI
  wiring, no worker/queue integration, no full ADR-017 resolution).

Earlier accepted decisions remain authoritative in their existing areas:

- [ADR-014 — User-Agent Ownership](../adr/0014-user-agent-ownership.md)
- [ADR-015 — Retry Idempotency](../adr/0015-retry-idempotency.md)
- [ADR-020 — Declarative Source Architecture](../adr/0020-declarative-source-architecture.md)
- [ADR-021 — Application-Level Article Crawl Orchestration](../adr/0021-application-level-article-crawl-orchestration.md)
- [ADR-022 — Application Runtime Composition and Resource Ownership](../adr/0022-application-runtime-composition-and-resource-ownership.md)
- [ADR-023 — CLI Application Entry Point and Process Boundary](../adr/0023-cli-application-entry-point-and-process-boundary.md)

The [ADR index](../adr/README.md) records 17 Accepted, 2 Proposed, 2 Deferred,
and 0 Superseded decisions. ADR-016 and ADR-019 remain Proposed; ADR-017 and
ADR-018 remain Deferred. ADR-024 narrowly answers ADR-017's persistence
review trigger without resolving it fully, so its status is unchanged by
this report.

## 4. Persistence port and sink implementation

`aa_crawler.persistence` implements exactly the boundary approved by
ADR-024:

```text
caller
  → holds a produced CrawlerItem
  → composes a concrete BaseCrawlResultSink explicitly
  → sink.save(item)
  → dict(item.data)
  → json.dumps(...)
  → durable append write
```

The package is exactly three modules: `persistence/base.py` (the abstract
`BaseCrawlResultSink` port, declaring `save(item: CrawlerItem) -> None`),
`persistence/errors.py` (`PersistenceError`, `PersistenceWriteError`), and
`persistence/file_sink.py` (`FileCrawlResultSink`, the one concrete
implementation). No additional persistence modules were introduced.

## 5. Serialization reuse

`FileCrawlResultSink.save()` reuses the exact conversion
`aa_crawler.cli.app.run_crawl()` already performs: the immutable
`CrawlerItem.data` mapping (a `MappingProxyType`) is converted to a plain
`dict` before calling `json.dumps(dict(item.data), sort_keys=True)`, since a
`MappingProxyType` is not itself JSON-serializable. No domain-model change
was required or made for this task.

## 6. File sink behavior

`FileCrawlResultSink` appends exactly one JSON Lines record per `save()`
call to a caller-supplied `destination: Path`, opening the file in append
mode (`"a"`, UTF-8) and creating it on first write. It never deduplicates or
overwrites a prior line for the same result; repeated `save()` calls with
the same item append the same line again. The destination file's parent
directory must already exist — the sink does not create directories. The
`destination` property exposes the configured path read-only.

## 7. Error hierarchy

`PersistenceError` derives from the existing `CrawlerError` root, and
`PersistenceWriteError` derives from `PersistenceError`. `save()` wraps a
serialization failure (`TypeError`/`ValueError` from `json.dumps`) and a
durable-write failure (`OSError` from the file write) into
`PersistenceWriteError`, so callers never observe a raw standard-library
exception from this boundary. A serialization failure occurs before the
file is opened, so a failed `save()` call never creates an empty destination
file.

## 8. Optionality guarantee

`ArticleCrawlService`, `ApplicationRuntime`, and `aa_crawler.cli` never
import `aa_crawler.persistence`. This is verified two ways:

- a static test (`tests/persistence/test_optionality.py`) parses
  `aa_crawler.application.runtime`, `aa_crawler.application.service`, and
  `aa_crawler.cli.app` with `ast` and asserts none of their imports
  reference `aa_crawler.persistence`, proving the absence of any reference
  rather than exercising runtime behavior; and
- an independent manual verification (`grep -rn "persistence"` across
  `src/aa_crawler/application/`, `src/aa_crawler/cli/`,
  `src/aa_crawler/crawler/`, and `src/aa_crawler/__init__.py`) confirmed
  zero matches, and the `pyproject.toml` console-script declaration
  (`aa-crawler = "aa_crawler:main"`) is unchanged.

## 9. Public API discipline

The `aa_crawler.persistence` package intentionally exports exactly
`BaseCrawlResultSink`, `FileCrawlResultSink`, `PersistenceError`, and
`PersistenceWriteError` via `__all__`. No compatibility alias, mutable
global registry, service locator, or convenience orchestration method was
introduced.

## 10. Integration verification

Integration verification (Task 7.4) was a read-only repository-wide gate run
against the merged Task 7.3 state, with no file changes. It confirmed:

- Ruff, Ruff format, and mypy all passed with no findings;
- the full test suite (724 tests) passed, including the 9 new
  persistence-boundary tests;
- coverage remained at 95.08%, unaffected by the new optional package;
- `uv lock --check` confirmed the lockfile stayed consistent, since no new
  dependency was introduced; and
- pre-commit's full hook set passed against the merged state.

No separate pull request was required for Task 7.4, since it made no file
changes; its evidence is preserved in this report.

## 11. Quality gates

The repository verification strategy uses:

- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy`
- `uv run pytest`
- `uv run pytest --cov=aa_crawler`, with the configured minimum of 70%
- `uv lock --check` for lockfile consistency
- `uv --cache-dir .uv-cache run pre-commit run --all-files`

Sprint 7 implementation, integration-verification, and documentation tasks
passed their applicable focused and repository-wide gates throughout. The
verification run on the merged documentation-alignment state
(`523cda730cf9e30341cb1b166447156fec22349b`) confirmed:

- Ruff: passed
- Ruff format check: passed
- mypy: passed
- pytest: 724 passed, 0 skipped, 0 xfailed, 0 failed, 0 errors
- Coverage: 95.08%, against the configured 70% threshold
- `uv lock --check`: passed
- pre-commit: all hooks passed
- Critical findings: 0
- Major findings: 0

## 12. Security and safety properties

Sprint 7 added one narrow, optional boundary without claiming comprehensive
security or legal compliance:

- persistence remains entirely opt-in: no crawl invocation persists a
  result unless a caller explicitly constructs a sink and calls `save()`;
- the file sink writes only the same JSON-safe article fields already
  produced by `ArticleCrawlService`/the CLI; it introduces no new data
  collection;
- `save()` never leaks a raw `TypeError`/`ValueError`/`OSError` to the
  caller; both failure modes are wrapped in `PersistenceWriteError`;
- a serialization failure never creates or partially writes the
  destination file;
- the sink performs no path validation, sandboxing, or traversal
  protection beyond what the caller-supplied `Path` already encodes — the
  caller remains responsible for the destination it chooses; and
- all persistence tests remain fully isolated (`tmp_path`), performing no
  writes outside the pytest-managed temporary directory.

This report does not claim broad legal compliance, publisher authorization,
or production safety beyond these specific, implemented controls.

## 13. Production-source governance

### CNN Indonesia

- `source`: `cnn_indonesia`
- `domains`: `www.cnnindonesia.com`
- `parser_family`: `jsonld_article`
- `adapter_key`: `None`
- `enabled`: `True`

### Kompas

- `source`: `kompas`
- `domains`:
  - `www.kompas.com`
  - `nasional.kompas.com`
  - `surabaya.kompas.com`
- `parser_family`: `jsonld_article`
- `adapter_key`: `None`
- `enabled`: `False`

Sprint 7 did not alter this state. Enablement remains project governance
state only; it does not establish legal authorization, publisher permission,
robots authorization, rate-limit approval, or operational approval.

## 14. Dependencies

Direct runtime dependencies, verified from `pyproject.toml`, are unchanged:

- `httpx>=0.28.1,<0.29`
- `pydantic>=2.13.4,<3`
- `pydantic-settings>=2.14.2,<2.15`

Sprint 7 added no third-party dependency. `FileCrawlResultSink` uses only
the standard library (`json`, `pathlib`).

## 15. Current limitations

- No CLI flag or application-service parameter triggers persistence; a
  caller must compose a sink and call `save()` explicitly.
- `FileCrawlResultSink` is the only concrete sink; no database, search
  index, or message-queue sink exists.
- The file sink provides no deduplication and no idempotency guarantee.
- The file sink does not create its destination's parent directory.
- No batch, streaming, or asynchronous persistence path exists.
- No worker, queue, or scheduler consumes persisted results.
- ADR-017 (metadata portability) remains Deferred; plugin, queue, and
  worker portability remain unresolved.

## 16. Sprint 6 continuity

Sprint 6 delivered the operational CLI process boundary (`aa_crawler.cli`,
ADR-023). Sprint 7 does not modify, wrap, or extend the CLI: the persistence
port is a separate, optional package that the CLI does not import, call, or
depend on in any way (Section 8). This report does not revise or reopen the
Sprint 6 completion record.

## 17. Sprint 7 pull-request inventory

- PR #57 — ADR-024 application-level persistence boundary decision
- PR #58 — `aa_crawler.persistence` implementation (port, file sink, errors,
  and tests, including the static optionality guard)
- PR #59 — README, Engineering Standards, and ADR index alignment

## 18. Sprint 7 closure checklist

- [x] ADR-024 accepted
- [x] Persistence port (`BaseCrawlResultSink`) implemented
- [x] Concrete file sink (`FileCrawlResultSink`) implemented
- [x] Persistence error hierarchy implemented
- [x] Static optionality guard implemented and verified
- [x] Independent manual isolation check performed
- [x] Integration verification passed on the merged implementation
- [x] README aligned
- [x] Engineering Standards aligned
- [x] ADR index implementation reference aligned
- [x] Sprint 7 completion report created
- [ ] Sprint 7 completion report merged
- [ ] `main` synchronized after completion-report merge
- [ ] Final repository verification passed after merge
- [ ] Sprint 7 formally closed

## 19. Provisional post-Sprint-7 direction

No Sprint 8 architecture is approved by this report. Provisional future
areas already supported by current documentation include CLI-triggered
persistence, a database or search-index sink, separately reviewed redirect
architecture, broader reviewed source scaling, alternate execution runtimes
under ADR-019, worker/queue/scheduler concerns, and observability
hardening. Each requires its own explicit scope and architecture approval
before implementation.

## 20. Completion statement

Sprint 7 is ready for completion-report review. Formal closure occurs only
after this report is merged, the full repository quality gate passes on the
merged state, and local `main` is synchronized cleanly with `origin/main`.
