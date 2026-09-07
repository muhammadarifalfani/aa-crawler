# Sprint 10 Completion Report

## 1. Status

Sprint 10 implementation is complete. Integration verification is
complete. Documentation alignment is complete. This completion report has
been created.

Formal closure must not be declared until this report is merged, the final
repository quality gate passes on the merged state, and local `main` is
synchronized cleanly with `origin/main`.

## 2. Objective

Sprint 10 closed the gap identified by the project owner's Sprint 10 Task
10.1 discovery: the CLI printed one crawl result to stdout and exited —
nothing was ever durably saved unless a caller wrote custom Python against
`aa_crawler.persistence` directly. Sprint 10 wires the CLI to the existing
persistence port (ADR-024) through one optional, off-by-default `--output`
argument, exercising both ADR-023's and ADR-024's own long-standing named
review triggers ("persistence... CLI exposure" and "CLI-triggered
persistence is proposed"). It does not select a database, add a second
sink, add batch input, resolve idempotency, or enable any new production
source — enabling a real second news source remains a separate,
project-owner governance decision explicitly deferred out of this sprint.

## 3. Architecture decision

- [ADR-027 — CLI-Triggered Persistence](../adr/0027-cli-triggered-persistence.md)
  is **Accepted** and defines the `-o`/`--output PATH` argument, its
  off-by-default behavior, the reuse of the existing `FileCrawlResultSink`
  with no new sink type or selection mechanism, the new
  `EXIT_PERSISTENCE_FAILURE` exit code, and the deliberate, narrow
  relaxation of `tests/persistence/test_optionality.py`'s assertion for
  `aa_crawler.cli.app` only.

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

The [ADR index](../adr/README.md) records 20 Accepted, 2 Proposed, 2
Deferred, and 0 Superseded decisions. ADR-016 and ADR-019 remain Proposed;
ADR-018 remains Deferred. ADR-017 also remains Deferred: ADR-024, ADR-025,
and ADR-026 together narrowly answer its "persistence" and "multiple
parser families"/"custom parser or adapter behavior" review triggers, but
none resolves plugin, queue, or worker portability, so its status is
unchanged by this report. ADR-027 does not touch ADR-017.

## 4. Implementation: the `--output` argument

`aa_crawler.cli` gained one new optional argument, `-o`/`--output PATH`,
alongside the existing required positional `url`:

```text
aa-crawler <url>                    # unchanged: stdout only, no file write
aa-crawler <url> --output PATH      # also appends the result to PATH
```

`aa_crawler.cli.app.run_crawl()` gained a matching keyword-only
`output: Path | None = None` parameter. When `None` (the default), its
behavior is byte-for-byte unchanged from ADR-023: no filesystem write, no
`aa_crawler.persistence` reference exercised on that code path. When
supplied, it constructs `FileCrawlResultSink(destination=output)` and
calls `save(item)` with the already-produced `CrawlerItem`, strictly after
the JSON payload has already been printed to stdout.

## 5. New exit code

`EXIT_PERSISTENCE_FAILURE = 5` was added to the CLI-local exit-code table.
It is returned only when a crawl succeeds but the subsequent `save()` call
raises `PersistenceWriteError` (for example, a missing destination
directory). The stdout payload is never retracted; only the process exit
code reflects the persistence failure, and the failure is logged
conservatively (no raw exception detail).

## 6. No new sink, dependency, source, or credential mechanism

Per ADR-027's explicit scope: no new sink type or sink-selection mechanism
was introduced — the CLI constructs the one existing `FileCrawlResultSink`
directly. No new third-party dependency was added. No entry in
`DEFAULT_SOURCE_PROFILES` changed; CNN Indonesia remains the only enabled
production source, still `jsonld_article`. No credential or authentication
mechanism was introduced anywhere in `http/` or `identity/`.

## 7. Application and runtime isolation, narrowed and re-tested

`ArticleCrawlService` and `ApplicationRuntime` remain fully unaware of
`aa_crawler.persistence`, exactly as ADR-024 established. ADR-027's one
deliberate exception is `aa_crawler.cli.app`, which now imports
`aa_crawler.persistence` to support `--output`. This boundary change is
tested in both directions, not left as a silent gap:

- `tests/persistence/test_optionality.py`'s static `ast`-based check
  continues to assert `application.runtime` and `application.service`
  never import `aa_crawler.persistence`.
- A new, separate assertion in the same file positively confirms
  `aa_crawler.cli.app` now does, per ADR-027.

An independent manual `grep` across `src/aa_crawler/application/` for
`persistence` returned zero matches, confirming the narrowed boundary
holds exactly where ADR-027 intended.

## 8. Testing architecture

- `tests/cli/test_cli.py` (5 new tests): default invocation writes no
  file; `--output` durably persists the produced item; repeated
  invocations append without deduplication (matching
  `FileCrawlResultSink`'s existing, unchanged contract); a persistence
  failure after a successful crawl still prints stdout and returns
  `EXIT_PERSISTENCE_FAILURE`; that failure is logged conservatively.
- `tests/integration/test_cli_process_boundary.py` (3 new tests): the same
  three core behaviors (persist, no-file-by-default, failure-after-success)
  proven through the real end-to-end pipeline — real
  `bootstrap_application()`, real `ApplicationRuntime`, real
  `SourceRegistry`, and real `JsonLdArticleParser` — with only the
  acquisition leaf faked and
  `HttpClient` network-guarded so any real send attempt fails the test
  immediately.
- `tests/persistence/test_optionality.py`: updated per Section 7 above.

No test performs a live network acquisition of a real source or uses a
real credential. Per the project owner's explicit direction (Task 10.1),
verification fixtures mirror real observed markup structure (the existing
CNN Indonesia JSON-LD shape already used throughout the CLI integration
suite) with invented, non-copyrighted article content — never a verbatim
copy of a real publisher's text.

## 9. Quality gates

The repository verification strategy uses:

- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy`
- `uv run pytest`
- `uv run pytest --cov=aa_crawler`, with the configured minimum of 70%
- `uv lock --check` for lockfile consistency
- `uv --cache-dir .uv-cache run pre-commit run --all-files`

Sprint 10 implementation, integration-verification, and documentation
tasks passed their applicable focused and repository-wide gates
throughout. The verification run on the merged documentation-alignment
state (`d09ef815866ae0697c91ef89feb60bf301a630b8`) confirmed:

- Ruff: passed
- Ruff format check: passed
- mypy: passed
- pytest: 836 passed, 0 skipped, 0 xfailed, 0 failed, 0 errors
- Coverage: 94.48%, against the configured 70% threshold
- `uv lock --check`: passed
- pre-commit: all hooks passed
- Critical findings: 0
- Major findings: 0

## 10. Security and safety review

- `--output` is off by default; no existing CLI invocation gains a new
  side effect unless the caller explicitly opts in.
- `--output` selects only a persistence destination; it cannot override
  source, robots, retry, identity, or parser governance.
- A persistence failure never suppresses or alters the already-printed
  stdout payload, and is logged without raw exception detail, headers,
  cookies, or response content — consistent with the CLI's existing
  logging discipline.
- `FileCrawlResultSink`'s existing behavior is unchanged: append-only, no
  deduplication, no idempotency guarantee, whether invoked directly or
  through the CLI.
- No credential-handling code was added anywhere in the repository.

This report does not claim broad legal compliance, publisher
authorization, or production safety beyond these specific, implemented
controls.

## 11. Production-source governance

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

Sprint 10 did not alter this state. Enabling a second real production
source — the second half of the project owner's stated Sprint 10 goal —
remains a separate, explicitly deferred, project-owner governance decision
requiring its own legal/publisher-policy review; it is not implemented by
this ADR or this report.

## 12. Dependencies

Direct runtime dependencies, verified from `pyproject.toml`, are unchanged:

- `httpx>=0.28.1,<0.29`
- `pydantic>=2.13.4,<3`
- `pydantic-settings>=2.14.2,<2.15`

Sprint 10 added no third-party dependency.

## 13. Current limitations

- Enabling a real second production source remains unimplemented; it is
  an explicitly deferred, separate governance decision.
- `FileCrawlResultSink` remains append-only with no deduplication and no
  idempotency guarantee, whether invoked directly or via `--output`.
- No second sink type or sink-selection mechanism exists.
- No batch or multi-URL CLI input exists.
- No non-HTML content acquisition and no credential/authentication
  mechanism exist.
- `--output` accepts only a local filesystem path; no remote or streaming
  destination is supported.

## 14. Sprint 9 continuity

Sprint 9 delivered the third parser family, `microdata_article` (ADR-026).
Sprint 10 does not modify any parser family, `SourceProfile`, or
`ParserComposer` behavior; `--output` operates purely at the CLI/
persistence boundary, downstream of whichever family produced the
`CrawlerItem`. This report does not revise or reopen the Sprint 9
completion record.

## 15. Sprint 10 pull-request inventory

- PR #73 — ADR-027 CLI-triggered persistence decision
- PR #74 — `--output` implementation, new exit code, and tests (unit and
  real end-to-end integration)
- PR #75 — README, Engineering Standards, and ADR index alignment

## 16. Sprint 10 closure checklist

- [x] ADR-027 accepted
- [x] `-o`/`--output PATH` CLI argument implemented
- [x] `EXIT_PERSISTENCE_FAILURE` exit code implemented
- [x] Default CLI invocation confirmed byte-for-byte unchanged
- [x] `tests/persistence/test_optionality.py` narrowed and re-tested both
      ways
- [x] Independent manual isolation check performed (application/runtime
      still unaware of persistence)
- [x] End-to-end integration tests added and passing
- [x] No new production source enabled
- [x] README aligned
- [x] Engineering Standards aligned
- [x] ADR index implementation reference aligned
- [x] Sprint 10 completion report created
- [ ] Sprint 10 completion report merged
- [ ] `main` synchronized after completion-report merge
- [ ] Final repository verification passed after merge
- [ ] Sprint 10 formally closed

## 17. Provisional post-Sprint-10 direction

No Sprint 11 architecture is approved by this report. The project owner's
stated Sprint 10 goal had two parts; this sprint delivered the first
(CLI-triggered persistence) and explicitly deferred the second (a real
second production source) as its own governance decision. Provisional
future areas already supported by current documentation include: enabling
a real second production source (media online or social media, each with
its own legal/acquisition/credential review), a second concrete
persistence sink, non-HTML content acquisition, a credential/
authentication mechanism, separately reviewed redirect architecture,
broader reviewed news-source scaling, alternate execution runtimes under
ADR-019, worker/queue/scheduler concerns, and the previously-deferred CI
pipeline/coverage-reporting/structured-logging/performance/security-
scanning work. Each requires its own explicit scope and architecture
approval before implementation.

## 18. Completion statement

Sprint 10 is ready for completion-report review. Formal closure occurs
only after this report is merged, the full repository quality gate passes
on the merged state, and local `main` is synchronized cleanly with
`origin/main`.
