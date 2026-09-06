# Sprint 9 Completion Report

## 1. Status

Sprint 9 implementation is complete. Integration verification is complete.
Documentation alignment is complete. This completion report was merged,
local `main` was subsequently synchronized cleanly with `origin/main`, and
the final repository-wide verification (Section 13) passed on that merged
state with no Critical or Major findings.

**Sprint 9 is formally closed.**

## 2. Objective

Sprint 9 proved that Sprint 8's parser-family composition architecture
(ADR-025) genuinely supports more than a purely synthetic second format, by
adding a third parser family, `microdata_article`, parsing `schema.org`
Microdata directly from real HTML. The objective was explicitly not to add
publisher coverage or social-media ingestion: it was to demonstrate the
multi-format seam with a representation that is both meaningfully different
from `jsonld_article` and structurally reachable through the existing,
unmodified acquisition boundary — something `generic_json_article` (Sprint
8) could not do, since its JSON payload shape is not an accepted content
type at all.

## 3. Architecture decision

- [ADR-026 — Microdata Article Parser Family](../adr/0026-microdata-article-parser-family.md)
  is **Accepted** and defines the third parser family: its scope
  (`schema.org` `NewsArticle`/`Article` Microdata via `itemscope`/
  `itemtype`/`itemprop`), its required shared output shape with the other
  two families, the unchanged acquisition and credential boundaries, and
  its explicit non-goals (no production source, no format-detection layer,
  no acquisition-layer change, no credential mechanism).

Earlier accepted decisions remain authoritative in their existing areas:

- [ADR-014 — User-Agent Ownership](../adr/0014-user-agent-ownership.md)
- [ADR-015 — Retry Idempotency](../adr/0015-retry-idempotency.md)
- [ADR-020 — Declarative Source Architecture](../adr/0020-declarative-source-architecture.md)
- [ADR-021 — Application-Level Article Crawl Orchestration](../adr/0021-application-level-article-crawl-orchestration.md)
- [ADR-022 — Application Runtime Composition and Resource Ownership](../adr/0022-application-runtime-composition-and-resource-ownership.md)
- [ADR-023 — CLI Application Entry Point and Process Boundary](../adr/0023-cli-application-entry-point-and-process-boundary.md)
- [ADR-024 — Application-Level Persistence Boundary for Crawl Results](../adr/0024-application-level-persistence-boundary.md)
- [ADR-025 — Extensible Parser-Family Composition Seam](../adr/0025-extensible-parser-family-composition.md)

The [ADR index](../adr/README.md) records 19 Accepted, 2 Proposed, 2
Deferred, and 0 Superseded decisions. ADR-016 and ADR-019 remain Proposed;
ADR-018 remains Deferred. ADR-017 also remains Deferred: ADR-024, ADR-025,
and ADR-026 together narrowly answer its "persistence" and "multiple parser
families"/"custom parser or adapter behavior" review triggers, but none
resolves plugin, queue, or worker portability, so its status is unchanged
by this report.

## 4. Implemented format: Microdata article parsing

`MicrodataArticleParser` parses `schema.org` `NewsArticle`/`Article`
Microdata directly from `HtmlDocument.content` via a stack-based
`html.parser.HTMLParser` subclass. It supports:

- required fields: `headline`, `datePublished` → `published_at`, and
  canonical-identity resolution via `mainEntityOfPage`/`url`, validated
  against the profile's approved exact hosts;
- optional fields: `dateModified` → `modified_at`, `description`,
  `articleSection` → `section`;
- `author` and `image`, each resolved either as a plain attribute/text
  value or as one level of nested Microdata (`author` as a nested
  `Person`'s `name`; `image` as a nested `ImageObject`'s `url`/
  `contentUrl`, or an `<img>`/`<meta>` attribute); and
- `og:title`/`og:description`/`og:image`/meta-description fallbacks,
  mirroring `JsonLdArticleParser`'s existing tolerance model.

It produces the exact same JSON-safe `ArticleItem`/`CrawlerItem` output
shape as the other two families, so ADR-023's CLI stdout contract and
ADR-024's persistence serialization remain valid without any change to
either.

## 5. Format-selection mechanism

Format selection remains exactly as ADR-025 established:
`SourceProfile.parser_family` is a declarative, per-source string field,
resolved before any acquisition happens. `SourceProfile.supported_parser_families` now
lists three literal values (`jsonld_article`, `generic_json_article`,
`microdata_article`); `ParserComposer.create()` dispatches through one
additional explicit `elif` branch. Selection is deterministic and
ambiguity-free by construction: one profile declares exactly one family,
chosen by a human reviewer at declaration time, never inferred from
content at runtime. No format-detection or auto-selection layer was added,
since Task 9.1 confirmed none was needed.

## 6. Acquisition and credential boundaries unchanged

`HtmlFetcher._content_type()` still accepts only `text/html` and
`application/xhtml+xml`. `microdata_article` remains `text/html` and is
therefore structurally reachable through this existing boundary — unlike
`generic_json_article`, whose JSON payload is not an accepted content type
at all — but Sprint 9's implementation and tests remain fully synthetic
and network-isolated; no code or test performs a live acquisition of it.
No API-key, bearer-token, or OAuth mechanism was added anywhere in `http/`
or `identity/`. No entry in `DEFAULT_SOURCE_PROFILES` uses
`microdata_article`; selecting a real publisher remains a separate,
project-owner governance decision.

## 7. Application, runtime, CLI, and persistence compatibility

Verified two ways, not just asserted:

- **Static isolation**: an independent `grep` across
  `src/aa_crawler/application/`, `src/aa_crawler/cli/`, and
  `src/aa_crawler/persistence/` for `microdata_article`/
  `MicrodataArticleParser` returned zero matches.
- **Behavioral isolation**:
  `tests/integration/test_multi_format_composition.py` proves the real
  `SourceRegistry` → `ParserComposer` → parser → `ArticleItem` →
  `CrawlerItem` flow for all three families side
  by side, that the existing production `jsonld_article` flow (CNN
  Indonesia) is unaffected, and that `FileCrawlResultSink` (ADR-024)
  durably stores a result from any of the three families identically,
  without any family-specific knowledge.

`ArticleCrawlService`, `ApplicationRuntime`, and `aa_crawler.cli` were not
modified by this sprint.

## 8. Source governance

No change to production source governance. `DEFAULT_SOURCE_PROFILES` still
contains exactly CNN Indonesia (enabled, `jsonld_article`) and Kompas
(disabled, `jsonld_article`); neither uses `generic_json_article` or
`microdata_article`. Enablement remains project governance state only; it
does not establish legal authorization, publisher permission, robots
authorization, rate-limit approval, or operational approval.

## 9. Testing architecture

- `tests/parser/test_microdata_article.py` (40 tests): constructor
  validation, the shared JSON-safe output shape, `NewsArticle`/`Article`
  type acceptance, unrelated-itemscope tolerance, nested-versus-plain
  author/image resolution, `og:*`/meta-description fallbacks, ambiguous or
  mismatched candidate identity, and malformed/missing required fields.
- `tests/composition/test_parser.py` and `tests/sources/test_models.py`:
  extended to prove the two existing dispatch paths remain unaffected and
  `supported_parser_families` lists exactly the three shipped families.
- `tests/integration/test_multi_format_composition.py` (8 tests, new):
  end-to-end proof across `SourceRegistry`, `ParserComposer`, all three
  parsers, and the persistence boundary, with an explicit check that no
  acquisition component (`HttpClient`, `RobotsPolicy`, `HtmlFetcher`) is
  ever instantiated.

No test contacts a real network, a real credential, or a real publisher.
Every fixture is synthetic.

## 10. Security and safety review

- Persistence remains entirely opt-in and format-agnostic; it never
  branches on which parser family produced a result.
- `MicrodataArticleParser.parse_document()` never leaks a raw parsing
  exception; failures are wrapped in the existing `ArticleParserError`.
- Required-field validation (`headline`, `published_at`, canonical
  identity) fails closed; optional-field validation (image, language,
  author) fails open — omitted, never fatal — matching
  `JsonLdArticleParser`'s existing tolerance model.
- `adapter_key` remains unconditionally rejected for all three families,
  including the new one.
- No credential, API-key, or token-handling code exists anywhere in the
  repository.
- `HtmlFetcher`'s HTML-only content-type gate remains fully enforced.

This report does not claim broad legal compliance, publisher
authorization, or production safety beyond these specific, implemented
controls.

## 11. Explicit social-media deferral

Sprint 9 implements no social-media support of any kind. No social-media
profile, credential, API integration, pagination system, parser, or CLI
flag was added. Social-media ingestion (Twitter/X, Instagram, TikTok,
Facebook, YouTube, Threads) remains a future architecture track requiring
its own separate review of authentication, platform-specific API
semantics, pagination, rate limits, platform identity, media types, policy
constraints, and ingestion contracts fundamentally different from the
HTML/Microdata/JSON-LD article model this sprint extends.

## 12. Dependencies

Direct runtime dependencies, verified from `pyproject.toml`, are unchanged:

- `httpx>=0.28.1,<0.29`
- `pydantic>=2.13.4,<3`
- `pydantic-settings>=2.14.2,<2.15`

Sprint 9 added no third-party dependency. `MicrodataArticleParser` uses
only the standard library (`re`, `dataclasses`, `datetime`,
`html.parser.HTMLParser`, `urllib.parse`) — the same approach
`JsonLdArticleParser` already uses.

## 13. Quality gates

The repository verification strategy uses:

- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy`
- `uv run pytest`
- `uv run pytest --cov=aa_crawler`, with the configured minimum of 70%
- `uv lock --check` for lockfile consistency
- `uv --cache-dir .uv-cache run pre-commit run --all-files`

Sprint 9 implementation, integration-verification, and documentation tasks
passed their applicable focused and repository-wide gates throughout. The
verification run on the merged documentation-alignment state
(`90a5dd7db986849ebeb133570a41d114ff7c25e3`) confirmed:

- Ruff: passed
- Ruff format check: passed
- mypy: passed
- pytest: 826 passed, 0 skipped, 0 xfailed, 0 failed, 0 errors
- Coverage: 94.45%, against the configured 70% threshold
- `uv lock --check`: passed
- pre-commit: all hooks passed
- Critical findings: 0
- Major findings: 0

The final repository-wide verification, required for closure and run after
this completion report itself was merged, on
`34c2bd6a05eda81495dfecc971ad28147c0566f6`, confirmed the same result, plus
the additional checks Sprint 9's own workflow required:

- Ruff: passed
- Ruff format check: passed
- mypy: passed
- pytest: 826 passed, 0 skipped, 0 xfailed, 0 failed, 0 errors
- Coverage: 94.45%, against the configured 70% threshold
- `uv lock --check`: passed; dependencies unchanged (`httpx`, `pydantic`,
  `pydantic-settings` only)
- pre-commit: all hooks passed
- All five Sprint 9 commits (ADR-026, implementation, integration test,
  documentation alignment, this completion report) confirmed as ancestors
  of the merged `main`
- ADR index totals confirmed consistent (19 Accepted, 2 Proposed, 2
  Deferred, 0 Superseded) across README, Engineering Standards, and the ADR
  index itself
- Source governance confirmed unchanged: `DEFAULT_SOURCE_PROFILES` still
  contains exactly CNN Indonesia (enabled) and Kompas (disabled), both
  `jsonld_article`; neither newer family is used by any production profile
- `SourceProfile.supported_parser_families` confirmed to list exactly
  `jsonld_article`, `generic_json_article`, `microdata_article`
- An independent `grep` across `application/`, `cli/`, and `persistence/`
  for `microdata_article`/`MicrodataArticleParser` returned zero matches
- An independent search for social-media-related code confirmed zero new
  matches; the only hits were pre-existing, unrelated code (User-Agent
  impersonation rejection listing `facebookexternalhit`/`twitterbot`, and
  the pre-existing log-redaction patterns for `api_key`/`Bearer`)
- Critical findings: 0
- Major findings: 0

**Sprint 9 verification PASSED — ready for formal closure.**

## 14. Current limitations

- `microdata_article` is a proof-of-concept family only; no production
  `SourceProfile` uses it.
- Nested-Microdata handling supports exactly one level of nesting (for
  example `author`/`Person`, `image`/`ImageObject`); deeper nesting,
  `itemref`, and multi-valued `itemprop` attributes are not implemented.
- No non-HTML content acquisition exists; `HtmlFetcher` still accepts only
  `text/html`/`application/xhtml+xml`.
- No credential or authentication mechanism exists for outbound requests.
- Each new parser family still requires three hand-synchronized code
  changes (the supported-families constant, the parser class, the
  dispatch branch).
- `adapter_key` remains reserved and inert.
- No real external source, platform, or API — media online or social
  media — is selected, authorized, or implemented by this sprint.

## 15. Sprint 8 continuity

Sprint 8 delivered the parser-family composition seam and its first
proof-of-concept family, `generic_json_article` (ADR-025). Sprint 9 extends
that same seam with a third family without modifying `SourceProfile`'s or
`ParserComposer`'s existing behavior for either prior family, as verified
in Sections 7 and 9. This report does not revise or reopen the Sprint 8
completion record.

## 16. Sprint 9 pull-request inventory

- PR #67 — ADR-026 Microdata article parser family decision
- PR #68 — `MicrodataArticleParser` implementation and composition wiring
- PR #69 — Multi-format end-to-end integration verification
- PR #70 — README, Engineering Standards, and ADR index alignment
- PR #71 — Sprint 9 completion report

## 17. Sprint 9 closure checklist

- [x] ADR-026 accepted
- [x] `SourceProfile.supported_parser_families` supports three families
- [x] `ParserComposer` dispatches to all three families statically
- [x] `MicrodataArticleParser` implemented and tested
- [x] `adapter_key` confirmed still unconditionally rejected
- [x] Existing `jsonld_article`/`generic_json_article` paths confirmed
      unaffected
- [x] Independent manual isolation check performed (CLI/application/
      persistence unaware of the new family)
- [x] End-to-end integration test added and passing
- [x] README aligned
- [x] Engineering Standards aligned
- [x] ADR index implementation reference aligned
- [x] Sprint 9 completion report created
- [x] Sprint 9 completion report merged
- [x] `main` synchronized after completion-report merge
- [x] Final repository verification passed after merge
- [x] No social-media implementation confirmed present
- [x] Sprint 9 formally closed

## 18. Provisional post-Sprint-9 direction

No Sprint 10 architecture is approved by this report. Provisional future
areas already supported by current documentation include a real external
source or platform proposal (media online or social media, each with its
own legal/acquisition/credential review), non-HTML content acquisition, a
credential/authentication mechanism, separately reviewed redirect
architecture, broader reviewed news-source scaling, alternate execution
runtimes under ADR-019, CLI-triggered persistence, worker/queue/scheduler
concerns, and the previously-deferred CI pipeline/coverage-reporting/
structured-logging and performance/security-scanning work now folded into
a single future Sprint 10 candidate. Each requires its own explicit scope
and architecture approval before implementation.

## 19. Completion statement

This report was merged, local `main` was synchronized cleanly with
`origin/main` at `34c2bd6a05eda81495dfecc971ad28147c0566f6`, and the final
repository-wide quality gate passed on that merged state with no Critical
or Major findings.

**Sprint 9 verification PASSED — ready for formal closure.**

**Sprint 9 is formally closed.**
