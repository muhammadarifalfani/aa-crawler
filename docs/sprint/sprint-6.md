# Sprint 6 Completion Report

## 1. Status

Sprint 6 implementation is complete. Process-boundary integration verification
is complete. Documentation alignment is complete. This completion report was
merged, local `main` was subsequently synchronized cleanly with
`origin/main`, and the final repository-wide verification (Section 17) passed
on that merged state with no Critical or Major findings.

**Sprint 6 is formally closed.**

## 2. Objective

Sprint 6 provided a real operational process boundary for the application and
runtime architecture completed in Sprint 5, allowing one article URL to be
executed through the crawler via a deterministic synchronous command-line
interface. Sprint 6 operationalizes existing architecture; it does not
replace, relocate, or duplicate any lower-layer ownership established by
Sprints 1–5.

## 3. Architecture decision

- [ADR-023 — CLI Application Entry Point and Process Boundary](../adr/0023-cli-application-entry-point-and-process-boundary.md)
  is **Accepted** and defines CLI package ownership, entry-point delegation,
  argument parsing, the bootstrap/runtime sequence, the output contract, the
  CLI-local exit-code translation, and the logging/correlation policy for the
  operational process boundary.

Earlier accepted decisions remain authoritative in their existing areas:

- [ADR-014 — User-Agent Ownership](../adr/0014-user-agent-ownership.md)
- [ADR-015 — Retry Idempotency](../adr/0015-retry-idempotency.md)
- [ADR-020 — Declarative Source Architecture](../adr/0020-declarative-source-architecture.md)
- [ADR-021 — Application-Level Article Crawl Orchestration](../adr/0021-application-level-article-crawl-orchestration.md)
- [ADR-022 — Application Runtime Composition and Resource Ownership](../adr/0022-application-runtime-composition-and-resource-ownership.md)

The [ADR index](../adr/README.md) records 16 Accepted, 2 Proposed, 2 Deferred,
and 0 Superseded decisions. ADR-016 and ADR-019 remain Proposed; ADR-017 and
ADR-018 remain Deferred. This report does not change those statuses.

## 4. Operational CLI implementation

`aa_crawler.cli` implements exactly the sequence approved by ADR-023:

```text
process
  → aa_crawler:main
  → aa_crawler.cli
  → argparse
  → bootstrap_application()
  → create_application_runtime()
  → ApplicationRuntime
  → ArticleCrawlService.crawl(url)
  → CrawlerItem
  → JSON serialization
  → stdout / exit code
```

The package is exactly two modules: `cli/__init__.py` (argument parsing and
the public `main()` entry point) and `cli/app.py` (`run_crawl()`, which
performs the bootstrap → runtime → crawl → serialize → exit-code sequence).
No additional CLI modules were introduced.

## 5. Entry-point compatibility

The `pyproject.toml` console-script declaration is unchanged:
`aa-crawler = "aa_crawler:main"`. Top-level `aa_crawler.main` is a direct
re-export of `aa_crawler.cli.main` (`from aa_crawler.cli import main`), so it
delegates immediately and contains no argument-parsing, runtime-construction,
orchestration, exception-taxonomy, or serialization logic of its own. No
`pyproject.toml` change was required, and no new CLI runtime dependency was
added.

## 6. CLI argument contract

`aa_crawler.cli` uses standard-library `argparse` exclusively. The parser
accepts exactly one required positional `url` argument. There are no
subcommands, no batch mode, no file or stdin batch input, and no flag that
overrides source, robots, retry, identity, or parser behavior.

## 7. Successful output contract

A successful invocation prints exactly one JSON object to stdout, containing
the current shipped article fields:

`source`, `source_domain`, `requested_url`, `canonical_url`, `headline`,
`published_at`, `description`, `author_names`, `modified_at`, `section`,
`lead_image_url`, `language`.

`requested_url` preserves the exact URL supplied to the CLI; `canonical_url`
preserves the parser-derived canonical URL independently. This output
contract reflects the currently shipped `jsonld_article` parser family only;
it does not promise a stable serialization for hypothetical future parser
families.

## 8. Serialization boundary

`CrawlerItem.data` remains the existing immutable `Mapping` (a
`MappingProxyType`) defined by the crawler contracts; it was not modified to
support CLI serialization. `run_crawl()` converts this mapping to a plain
`dict` immediately before calling `json.dumps(...)`, since `MappingProxyType`
is not itself JSON-serializable. No domain-model change was required or made
for this task.

## 9. CLI-local exit semantics

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | Unexpected or unmapped failure |
| `2` | Unsupported or disabled source |
| `3` | Other crawl-domain failure |
| `4` | Configuration or startup failure |

These are CLI-local process-boundary semantics only. The internal exception
hierarchy is unchanged, and ADR-018 (error-root taxonomy) remains Deferred.

## 10. Error mapping

The exit-code translation is a conceptual mapping from existing exception
roots to a process result, implemented entirely inside `aa_crawler.cli.app`:

```text
UnsupportedSourceError        → unsupported-source process result
other CrawlerError subtypes   → crawl-domain process result
AACrawlerError/ConfigurationError
  (bootstrap or runtime construction) → startup process result
any other exception           → generic fallback process result
```

This mapping introduces no universal project error taxonomy and does not
change the existing exception hierarchy or its inheritance.

## 11. Bootstrap/runtime separation

`bootstrap_application()` continues to own startup, configuration, and
logging initialization exactly as defined by prior sprints. Separately,
`create_application_runtime()` continues to own runtime dependency
composition and resource lifecycle. The CLI coordinates both boundaries
sequentially — bootstrap first, runtime second — without merging their
responsibilities or extending either function's signature.

## 12. Runtime lifecycle

The CLI uses `create_application_runtime()` only as a context manager
(`with create_application_runtime() as runtime: ...`). It never owns or
constructs `HttpClient` directly and never closes any lower-layer resource
itself. Cleanup on success, on a known governance rejection, and on an
unexpected failure after runtime creation is owned entirely by
`ApplicationRuntime` under ADR-022; runtime partial-construction cleanup
remains exclusively ADR-022's responsibility, unmodified by Sprint 6.

## 13. Application orchestration boundary

For crawling, the CLI calls only `runtime.article_crawl_service.crawl(url)`.
It does not call `HttpClient`, `HtmlFetcher`, `SourceRegistry`,
`ParserComposer`, or any parser class directly. This preserves ADR-021's
application-orchestration ownership unchanged.

## 14. Governance boundaries

The CLI introduces no bypass for HTTPS validation, source enablement,
exact-host matching, robots evaluation, retry eligibility, identity, or
parser selection. No flag exists for force, ignore-robots, source override,
user-agent override, retry override, parser override, or HTTP allowance.

## 15. Logging, stdout, and correlation context

Successful, machine-readable crawl result data is written to stdout only.
Lifecycle and failure logging goes through the existing `aa_crawler` logger
hierarchy, which defaults to stderr. The CLI is not required to log the raw
requested URL, and it does not log request/response headers, cookies,
response bodies, or raw metadata. ADR-016 (logging redaction scope) remains
Proposed; this report does not claim a repository-wide redaction guarantee.

One correlation context, from the existing `observability.correlation_context`
API, scopes each CLI invocation. Reset and non-leakage across consecutive
invocations were verified. The internal correlation-identifier shape is not a
public contract.

## 16. Integration verification

Process-boundary integration uses the real top-level `aa_crawler.main()`
delegator, real `bootstrap_application()`, and the real cross-package runtime
graph — `ApplicationRuntime`, `SourceRegistry`, `ParserComposer`,
`JsonLdArticleParser`, and crawler/article contracts — behind synthetic or
network-guarded acquisition only. Durable coverage includes:

- the successful CNN Indonesia flow, with exact single-JSON-object output
  containing every current article field;
- the requested/canonical URL distinction;
- disabled-source (Kompas), unknown-host, and non-HTTPS rejection before
  acquisition;
- cross-profile final-URL rejection before parser composition;
- a foreign JSON-LD canonical URL producing a parser-owned failure, distinct
  from the pre-parser source-boundary gate;
- robots denial through the real `HtmlFetcher`, with no transport attempt;
- bootstrap/configuration failure, with the runtime never constructed;
- runtime-construction failure, with the already-acquired transport closed;
- an unexpected failure during acquisition, with cleanup preserved;
- correlation-context isolation across consecutive invocations;
- runtime cleanup across success and failure paths;
- stdout/log channel separation; and
- no external network, DNS-dependent behavior, or browser runtime anywhere
  in the suite.

Every CLI-local exit-code category was exercised through this evidence.

## 17. Quality gates

The repository verification strategy uses:

- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy`
- `uv run pytest`
- `uv run pytest --cov=aa_crawler`, with the configured minimum of 70%
- `uv lock --check` for lockfile consistency
- `uv --cache-dir .uv-cache run pre-commit run --all-files`

Sprint 6 implementation, integration-verification, and documentation tasks
passed their applicable focused and repository-wide gates throughout. The
final repository-wide verification, run on the merged completion state
(`8597e7c645dd7a4c08052701641dfb48a4a0193f`), confirmed:

- Ruff: passed
- Ruff format check: passed
- mypy: passed
- pytest: 715 passed, 0 skipped, 0 xfailed, 0 failed, 0 errors
- Coverage: 94.99%, against the configured 70% threshold
- `uv lock --check`: passed
- pre-commit: all hooks passed
- Critical findings: 0
- Major findings: 0

## 18. Security and safety properties

Sprint 6 added focused controls without claiming comprehensive security or
legal compliance:

- the pre- and post-acquisition exact-profile source gates remain fully
  enforced through the CLI, unmodified;
- normal HTTPS/exact-host `SourceRegistry` lookup remains the only path; no
  wildcard host authorization exists;
- no CLI flag bypasses source, robots, retry, identity, or parser governance;
- no raw exception payload, traceback, or Python `repr` is ever written to
  stdout;
- machine-readable stdout output remains isolated from lifecycle/error
  logging;
- the CLI does not log headers, cookies, response bodies, or raw metadata;
- runtime resource ownership remains explicit and single-owner via
  `ApplicationRuntime`; and
- all CLI tests remain network-isolated.

This report does not claim broad legal compliance, publisher authorization,
or production safety beyond these specific, implemented controls.

## 19. Production-source governance

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

Sprint 6 did not alter this state. Enablement remains project governance
state only; it does not establish legal authorization, publisher permission,
robots authorization, rate-limit approval, or operational approval.

## 20. Dependencies

Direct runtime dependencies, verified from `pyproject.toml`, are unchanged:

- `httpx>=0.28.1,<0.29`
- `pydantic>=2.13.4,<3`
- `pydantic-settings>=2.14.2,<2.15`

The CLI added no third-party dependency. Argument parsing, serialization, and
correlation-ID generation use only the standard library (`argparse`, `json`,
`uuid`).

## 21. Current limitations

- The CLI accepts exactly one URL per invocation; execution is synchronous.
- No batch mode, file/stdin batch input, or JSON Lines output exists.
- Automatic redirect following remains disabled.
- No asynchronous or browser runtime exists.
- No persistence or storage pipeline exists.
- No worker, queue, scheduler, or distributed execution architecture exists.
- No dynamic adapter or plugin runtime exists.
- Runtime source-profile reload is not implemented.
- The synchronous runtime has no thread-safety guarantee.
- Production source coverage remains intentionally narrow (one enabled
  source).
- `jsonld_article` remains the only supported parser family.

## 22. Sprint 5 continuity

Sprint 5 delivered application orchestration (`ArticleCrawlService`, ADR-021)
and runtime composition (`ApplicationRuntime`, `create_application_runtime()`,
ADR-022). Sprint 6 builds directly on those two layers rather than
re-implementing or relocating them: the CLI is a thin process boundary placed
on top of the already-accepted application and runtime architecture. This
report does not revise or reopen the Sprint 5 completion record.

## 23. Sprint 6 pull-request inventory

- PR #51 — ADR-023 CLI application entry point decision
- PR #52 — `aa_crawler.cli` implementation and top-level delegation
- PR #53 — CLI process-boundary integration verification
- PR #54 — README, Engineering Standards, and ADR index alignment
- PR #55 — Sprint 6 completion report

## 24. Sprint 6 closure checklist

- [x] ADR-023 accepted
- [x] Operational CLI implemented
- [x] CLI process boundary integrated with the existing application runtime
- [x] CLI-local exit semantics implemented
- [x] JSON stdout contract implemented
- [x] Logging/stdout separation implemented
- [x] Correlation context integrated
- [x] Runtime cleanup verified through the CLI
- [x] Integration verification added
- [x] README aligned
- [x] Engineering Standards aligned
- [x] ADR index implementation reference aligned
- [x] Sprint 6 completion report created
- [x] Sprint 6 completion report merged
- [x] `main` synchronized after completion-report merge
- [x] Final repository verification passed after merge
- [x] Sprint 6 formally closed

## 25. Provisional post-Sprint-6 direction

No Sprint 7 architecture is approved by this report. Provisional future areas
already supported by current documentation include persistence, separately
reviewed redirect architecture, broader reviewed source scaling, alternate
execution runtimes under ADR-019, worker/queue/scheduler concerns, and
observability hardening. Each requires its own explicit scope and
architecture approval before implementation.

## 26. Completion statement

This report was merged, local `main` was synchronized cleanly with
`origin/main` at `8597e7c645dd7a4c08052701641dfb48a4a0193f`, and the final
repository-wide quality gate passed on that merged state with no Critical or
Major findings.

**Sprint 6 is formally closed.**
