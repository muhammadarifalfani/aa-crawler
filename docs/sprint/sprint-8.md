# Sprint 8 Completion Report

## 1. Status

Sprint 8 implementation is complete. Integration verification is complete.
Documentation alignment is complete. This completion report was merged,
local `main` was subsequently synchronized cleanly with `origin/main`, and
the final repository-wide verification (Section 10) passed on that merged
state with no Critical or Major findings.

**Sprint 8 is formally closed.**

## 2. Objective

Sprint 8 built the internal mechanism that lets `SourceProfile` and
`ParserComposer` support more than one closed, statically-dispatched parser
family, answering two long-standing ADR-020 review triggers ("multiple
parser families are implemented" and "a real publisher requires custom
parser or adapter behavior") fired by the project owner's stated long-term
goal of ingesting online news alongside several social-media platforms.
Sprint 8 builds only the composition seam; it selects, authorizes, or
implements no specific external source, platform, or API, and it does not
resolve the two larger prerequisites (non-HTML acquisition, credentialed
API access) that real platform onboarding would separately require.

## 3. Architecture decision

- [ADR-025 — Extensible Parser-Family Composition Seam](../adr/0025-extensible-parser-family-composition.md)
  is **Accepted** and defines how `SourceProfile.supported_parser_families`
  and `ParserComposer.create()` support more than one parser family through
  a small, static, explicit dispatch; keeps `adapter_key` reserved and
  inert, conceptually distinct from parser-family selection; requires any
  family introduced under this decision to keep `ArticleItem`/`CrawlerItem`'s
  existing JSON-safe output shape; and leaves `HtmlFetcher`'s HTML-only
  acquisition boundary and the absence of any credential mechanism
  unchanged.

Earlier accepted decisions remain authoritative in their existing areas:

- [ADR-014 — User-Agent Ownership](../adr/0014-user-agent-ownership.md)
- [ADR-015 — Retry Idempotency](../adr/0015-retry-idempotency.md)
- [ADR-020 — Declarative Source Architecture](../adr/0020-declarative-source-architecture.md)
- [ADR-021 — Application-Level Article Crawl Orchestration](../adr/0021-application-level-article-crawl-orchestration.md)
- [ADR-022 — Application Runtime Composition and Resource Ownership](../adr/0022-application-runtime-composition-and-resource-ownership.md)
- [ADR-023 — CLI Application Entry Point and Process Boundary](../adr/0023-cli-application-entry-point-and-process-boundary.md)
- [ADR-024 — Application-Level Persistence Boundary for Crawl Results](../adr/0024-application-level-persistence-boundary.md)

The [ADR index](../adr/README.md) records 18 Accepted, 2 Proposed, 2
Deferred, and 0 Superseded decisions. ADR-016 and ADR-019 remain Proposed;
ADR-018 remains Deferred. ADR-017 also remains Deferred: ADR-024 and
ADR-025 together narrowly answer its "persistence" and "multiple parser
families"/"custom parser or adapter behavior" review triggers, but neither
resolves plugin, queue, or worker portability, so its status is unchanged
by this report.

## 4. Parser-family composition implementation

`SourceProfile`/`ParserComposer` implement exactly the mechanism approved by
ADR-025:

```text
SourceProfile.parser_family
  → must be in SourceProfile.supported_parser_families
    ({"jsonld_article", "generic_json_article"})
  → ParserComposer.create()
  → static, explicit if/elif dispatch
  → JsonLdArticleParser  or  GenericJsonArticleParser
```

`SourceProfile.supported_parser_families` grew from a single-value
`ClassVar[frozenset[str]]` to list both literal family names.
`ParserComposer.create()`'s existing `jsonld_article` branch and its
`ParserCompositionError` messages are byte-for-byte unchanged; one new
`elif` branch was added for `generic_json_article`. `adapter_key` continues
to be unconditionally rejected regardless of `parser_family`.

## 5. Second parser family: `GenericJsonArticleParser`

`GenericJsonArticleParser` is a synthetic, non-network proof-of-concept
second family. It parses a flat JSON object directly from
`HtmlDocument.content` — never JSON-LD, never HTML — validating a required
`url` (HTTPS, exact-host-bound), `headline`, and `published_at`, with
lenient (non-fatal) handling of optional `description`, `authors`,
`modified_at`, `section`, `lead_image_url`, and `language` fields. It
produces the exact same `ArticleItem`/`CrawlerItem` JSON-safe output shape
as `JsonLdArticleParser`, so ADR-023's CLI stdout contract and ADR-024's
persistence serialization remain valid without any change to either.

## 6. Acquisition and credential boundaries unchanged

Per ADR-025's explicit scope: `HtmlFetcher._content_type()` still accepts
only `text/html` and `application/xhtml+xml`; `generic_json_article` is
reachable only through synthetic, in-test `HtmlDocument` fixtures, never
real network acquisition. No API-key, bearer-token, or OAuth mechanism was
added anywhere in `http/` or `identity/`. No production `SourceProfile` uses
`generic_json_article`, and no external source, platform, or API is
selected, authorized, or implemented by this work.

## 7. Isolation from CLI and persistence

`aa_crawler.cli` and `aa_crawler.persistence` are untouched by this sprint
and remain unaware of `generic_json_article`'s existence. This was verified
two ways:

- the full test suite exercises both parser families independently and
  proves the `jsonld_article` composition path is unaffected; and
- an independent manual check (`grep -rn "generic_json_article\|
  GenericJsonArticleParser" src/aa_crawler/application/ src/aa_crawler/cli/
  src/aa_crawler/persistence/`) returned zero matches.

## 8. Public API discipline

The `aa_crawler.parser` package now exports `GenericJsonArticleParser`
alongside `JsonLdArticleParser`, `BaseParser`, `ArticleParserError`,
`ParserContractError`, `ParserError`, and `ParserExecutionError`. Both
concrete parsers derive from `BaseParser`. No compatibility alias, mutable
global registry, service locator, or convenience orchestration method was
introduced.

## 9. Integration verification

Integration verification (Task 8.4) was a read-only repository-wide gate run
against the merged Task 8.3 state, with no file changes. It confirmed:

- Ruff, Ruff format, and mypy all passed with no findings;
- the full test suite (775 tests) passed, including the 51 new/changed
  tests for the second parser family and its composition dispatch;
- coverage remained at 94.84%, well above the 70% threshold;
- `uv lock --check` confirmed the lockfile stayed consistent, since no new
  dependency was introduced;
- pre-commit's full hook set passed against the merged state; and
- independent manual checks confirmed `HtmlFetcher`'s content-type gate is
  unchanged, no credential mechanism exists, `adapter_key` remains
  unconditionally rejected (including for the new family), and
  `supported_parser_families` lists exactly the two shipped families.

No separate pull request was required for Task 8.1 (chat-only discovery) or
Task 8.4, since neither made file changes; their evidence is preserved in
this report and the session record.

## 10. Quality gates

The repository verification strategy uses:

- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy`
- `uv run pytest`
- `uv run pytest --cov=aa_crawler`, with the configured minimum of 70%
- `uv lock --check` for lockfile consistency
- `uv --cache-dir .uv-cache run pre-commit run --all-files`

Sprint 8 implementation, integration-verification, and documentation tasks
passed their applicable focused and repository-wide gates throughout. The
verification run on the merged documentation-alignment state
(`3dd25ed1e1e2b70e4e0c9c9bc8a7e6dac1224c20`) confirmed:

- Ruff: passed
- Ruff format check: passed
- mypy: passed
- pytest: 775 passed, 0 skipped, 0 xfailed, 0 failed, 0 errors
- Coverage: 94.84%, against the configured 70% threshold
- `uv lock --check`: passed
- pre-commit: all hooks passed
- Critical findings: 0
- Major findings: 0

The final repository-wide verification, required for closure and run after
this completion report itself was merged, on
`7e167b0d56683f01a039e8ba385a2ab62af57933`, confirmed the same result:

- Ruff: passed
- Ruff format check: passed
- mypy: passed
- pytest: 775 passed, 0 skipped, 0 xfailed, 0 failed, 0 errors
- Coverage: 94.84%, against the configured 70% threshold
- `uv lock --check`: passed
- pre-commit: all hooks passed
- Critical findings: 0
- Major findings: 0

## 11. Security and safety properties

Sprint 8 added one narrow, internal composition mechanism without claiming
comprehensive security or legal compliance:

- no real external source, platform, or API is reachable through this
  work; `generic_json_article` is exercised only through synthetic,
  in-test fixtures;
- `HtmlFetcher`'s HTML-only content-type gate remains fully enforced,
  preventing any accidental non-HTML acquisition;
- no credential, API-key, or token-handling code was introduced anywhere;
- `GenericJsonArticleParser.parse_document()` never leaks a raw
  `json.JSONDecodeError`, `TypeError`, or `ValueError`; all failures are
  wrapped in `ArticleParserError`;
- required-field validation (`url`, `headline`, `published_at`) fails
  closed, while optional-field validation (image URL, language, authors)
  fails open (omitted, never fatal) — matching `JsonLdArticleParser`'s
  existing tolerance model;
- `adapter_key` remains unconditionally rejected for both parser families;
  and
- all new tests remain fully synthetic and network-isolated.

This report does not claim broad legal compliance, publisher authorization,
or production safety beyond these specific, implemented controls.

## 12. Production-source governance

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

Sprint 8 did not alter this state. No production profile uses
`generic_json_article`. Enablement remains project governance state only;
it does not establish legal authorization, publisher permission, robots
authorization, rate-limit approval, or operational approval.

## 13. Dependencies

Direct runtime dependencies, verified from `pyproject.toml`, are unchanged:

- `httpx>=0.28.1,<0.29`
- `pydantic>=2.13.4,<3`
- `pydantic-settings>=2.14.2,<2.15`

Sprint 8 added no third-party dependency. `GenericJsonArticleParser` uses
only the standard library (`json`, `re`, `datetime`, `urllib.parse`).

## 14. Current limitations

- `generic_json_article` is a synthetic proof-of-concept family only; no
  production `SourceProfile` uses it.
- It is not reachable through real network acquisition: `HtmlFetcher`
  still accepts only `text/html`/`application/xhtml+xml`.
- No credential or authentication mechanism (API key, bearer token, OAuth)
  exists for outbound requests.
- Each new parser family still requires three hand-synchronized code
  changes (the supported-families constant, the parser class, the
  dispatch branch); this does not scale to many families without further
  review.
- `adapter_key` remains reserved and inert; per-publisher customization
  within one family is still unimplemented.
- No real external source, platform, or API is selected, authorized, or
  implemented by this sprint.

## 15. Sprint 7 continuity

Sprint 7 delivered the application-level persistence boundary
(`aa_crawler.persistence`, ADR-024). Sprint 8 does not modify, wrap, or
extend persistence: the parser-family composition seam is independent, and
`aa_crawler.persistence` remains unaware of `generic_json_article`'s
existence, as verified in Section 7. This report does not revise or reopen
the Sprint 7 completion record.

## 16. Sprint 8 pull-request inventory

- PR #62 — ADR-025 extensible parser-family composition decision
- PR #63 — `SourceProfile`/`ParserComposer`/`GenericJsonArticleParser`
  implementation and tests
- PR #64 — README, Engineering Standards, and ADR index alignment
- PR #65 — Sprint 8 completion report

## 17. Sprint 8 closure checklist

- [x] ADR-025 accepted
- [x] `SourceProfile.supported_parser_families` supports two families
- [x] `ParserComposer` dispatches to both families statically
- [x] `GenericJsonArticleParser` implemented and tested
- [x] `adapter_key` confirmed still unconditionally rejected
- [x] Existing `jsonld_article` path confirmed unaffected
- [x] Independent manual isolation check performed (CLI/application/
      persistence unaware of the new family)
- [x] Integration verification passed on the merged implementation
- [x] README aligned
- [x] Engineering Standards aligned
- [x] ADR index implementation reference aligned
- [x] Sprint 8 completion report created
- [x] Sprint 8 completion report merged
- [x] `main` synchronized after completion-report merge
- [x] Final repository verification passed after merge
- [x] Sprint 8 formally closed

## 18. Provisional post-Sprint-8 direction

No Sprint 9 architecture is approved by this report. Provisional future
areas already supported by current documentation include a real external
source or platform proposal (with its own legal, acquisition, and
credential review), non-HTML content acquisition, a credential/
authentication mechanism, separately reviewed redirect architecture,
broader reviewed news-source scaling, alternate execution runtimes under
ADR-019, CLI-triggered persistence, worker/queue/scheduler concerns, and
observability hardening. Each requires its own explicit scope and
architecture approval before implementation.

## 19. Completion statement

This report was merged, local `main` was synchronized cleanly with
`origin/main` at `7e167b0d56683f01a039e8ba385a2ab62af57933`, and the final
repository-wide quality gate passed on that merged state with no Critical or
Major findings.

**Sprint 8 is formally closed.**
