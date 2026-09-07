# Sprint 17 Completion Report

## 1. Status

Sprint 17 implementation is complete. Integration verification is
complete. Documentation alignment is complete. This completion report will
be merged, local `main` will subsequently be synchronized cleanly with
`origin/main`, and a final repository-wide verification will run on that
merged state before formal closure.

**Sprint 17 is pending formal closure** (see Section 17).

## 2. Objective

Sprint 17's Architecture Discovery found that six sprints in a row
(Sprint 12 through Sprint 16) had focused entirely on CLI and persistence
infrastructure, while the project owner's original "many sources" goal
had not been touched since Sprint 11's Kompas activation. Unlike several
recent sprints, no ADR's own named review trigger had crisply fired for
any single candidate this time; candidates were presented on their own
evidence rather than a forced "Recommended" pick. The project owner chose
to activate a third real production source — Detik — over two
alternatives (CI security-scanning enhancements; a speculative
multi-sink persistence feature with no identified real requirement).
Unlike Kompas (already registered, disabled, since Sprint 4), Detik had
never been declared anywhere in the codebase, so this sprint's discovery
also included asking the project owner directly which source and which
exact host(s) to approve — a business/legal decision only they can make.

## 3. Architecture decision

No new ADR was created for Sprint 17, mirroring Sprint 11's precedent
exactly. Detik is a structurally ordinary source — same `jsonld_article`
parser family as CNN Indonesia and Kompas, one exact host, no adapter —
so ADR-020's existing "ordinary source onboarding" section fully
authorizes this change without a new decision record.

Earlier accepted decisions remain authoritative in their existing areas;
the [ADR index](../adr/README.md) is unchanged by Sprint 17: 24 Accepted,
2 Proposed, 2 Deferred, and 0 Superseded decisions.

## 4. Implementation: Detik enabled

[`src/aa_crawler/sources/profiles.py`](../../src/aa_crawler/sources/profiles.py)
gained a new `DETIK_PROFILE`:

- `source`: `detik`
- `domains`: `news.detik.com` (only — Detik's other verticals, e.g.
  `finance.detik.com`, `health.detik.com`, were deliberately not
  approved)
- `parser_family`: `jsonld_article`
- `adapter_key`: `None`
- `enabled`: `True`

`DEFAULT_SOURCE_PROFILES` now declares three profiles, in order:
`CNN_INDONESIA_PROFILE`, `KOMPAS_PROFILE`, `DETIK_PROFILE`. The module
docstring records the Sprint 17 governance rationale in place, following
this project's existing convention (established for Kompas in Sprint 11)
of documenting *why* a production profile is enabled directly alongside
its declaration — including the explicit note that Detik's
`jsonld_article` compatibility is an assumption following the existing
convention, not yet confirmed against a live fetch.

With this one new declaration, Detik resolves through normal (non-
`include_disabled`) `SourceRegistry` lookup and composes into a real
`JsonLdArticleParser` exactly like CNN Indonesia and Kompas — the
source-composition pipeline required no code change beyond the new
profile itself, again confirming the declarative-source architecture
(ADR-020) behaves as designed for a third source.

## 5. Exact-host boundary, not a wildcard

Per the project owner's explicit choice, only `news.detik.com` is
approved. `SourceProfile`'s existing exact-host matching (no wildcard,
suffix, or implicit subdomain support) means `finance.detik.com`,
`www.detik.com`, and every other Detik subdomain remain entirely outside
this project's source governance — they do not resolve, and no code
change would be needed to add them later as their own explicit,
separately-approved hosts.

## 6. Test coverage updated for a third profile

Adding a third profile to `DEFAULT_SOURCE_PROFILES` required updating
every existing test that asserted an exact tuple or count against it
(`DEFAULT_SOURCE_PROFILES == (CNN_INDONESIA_PROFILE, KOMPAS_PROFILE)` and
similar), across `tests/sources/test_profiles.py`,
`tests/sources/test_models.py`, `tests/sources/test_registry.py`,
`tests/integration/test_application_article_crawl.py`, and
`tests/integration/test_source_composition.py`. New per-profile and
composition tests for Detik mirror the existing CNN/Kompas coverage
exactly: profile field validation, exact-host acceptance/rejection
(including the two rejected verticals above), registry resolution, and
parser composition.

## 7. No architectural, dependency, or credential change

Per ADR-020's governance-only nature: no new parser family, no new
`SourceProfile` field, no new registry or composition behavior, no CLI
change, and no new third-party dependency were introduced. No credential
or authentication mechanism was introduced anywhere in `http/` or
`identity/`. `ArticleCrawlService` and `ApplicationRuntime` remain fully
unaware of this change; it is entirely a declarative-source-layer
addition.

## 8. Testing architecture

- `tests/sources/test_profiles.py` (2 new tests, several existing tests
  updated): Detik's profile fields and exact-host boundary
  (`test_detik_profile_is_enabled_with_only_validated_exact_host`), and
  its composition into a real `JsonLdArticleParser`
  (`test_detik_profile_composes_like_any_other_enabled_source`).
- `tests/integration/test_source_composition.py` (1 new test):
  `test_detik_resolves_and_composes_like_any_other_enabled_source`,
  mirroring Kompas's existing equivalent.
- `tests/sources/test_models.py`, `tests/sources/test_registry.py`,
  `tests/integration/test_application_article_crawl.py`: existing
  exact-`__all__`/exact-tuple assertions updated to include
  `DETIK_PROFILE`, with no scenario or assertion logic otherwise changed.
- No test performs a live network acquisition of a real source or uses a
  real credential, consistent with this project's standing testing
  discipline. Detik's compatibility with the `jsonld_article` family is
  therefore proven only structurally (registry resolution, composition),
  not against real Detik content.

## 9. Quality gates

The repository verification strategy uses:

- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy`
- `uv run pytest`
- `uv run pytest --cov=aa_crawler`, with the configured minimum of 70%
- `uv lock --check` for lockfile consistency
- `uv --cache-dir .uv-cache run pre-commit run --all-files`

Sprint 17 implementation, integration-verification, and documentation
tasks passed their applicable focused and repository-wide gates
throughout, both locally and via the real GitHub Actions CI pipeline
(Sprint 12). The verification run on the merged documentation-alignment
state (`1cde0fdc2b538fa695dbb9d651ce9ad31ca3ce3f`) confirmed:

- Ruff: passed
- Ruff format check: passed
- mypy: passed
- pytest: 927 passed, 0 skipped, 0 xfailed, 0 failed, 0 errors
- Coverage: 95.05%, against the configured 70% threshold
- `uv lock --check`: passed
- pre-commit: all hooks passed
- Real GitHub Actions `pull_request`-event and `push`-event runs on this
  same merged state: both completed with a `success` conclusion
- Critical findings: 0
- Major findings: 0

An independent manual smoke test against the real, merged code (not
through pytest) confirmed the source-composition chain concretely: Detik
resolves via `SourceRegistry.get_by_url()`/`get_by_host()`/`get_by_source()`,
`finance.detik.com` and `www.detik.com` both correctly return `None`
(not wildcard-matched), and `ParserComposer().create(DETIK_PROFILE)`
produces a real `JsonLdArticleParser` instance.

The final repository-wide verification, required for closure and run
after this completion report itself is merged, will be recorded in
Section 17 below at closure time.

## 10. Security and safety review

- Enabling Detik changes only project-internal governance state
  (`enabled=True` on a newly-declared, validated `SourceProfile`). It
  does not itself constitute legal authorization, publisher permission,
  robots authorization, rate-limit approval, or operational approval —
  see ADR-020's "Enabled and disabled governance" section.
- No crawl request against Detik or any other host was made by this
  sprint's implementation or test work; all test coverage uses in-memory
  fixtures and network-isolated pipelines, consistent with every prior
  sprint's testing discipline.
- Host matching for Detik remains exact (`news.detik.com` only); no
  wildcard, suffix, or implicit subdomain matching was introduced, and
  this was independently verified (Section 9).
- No credential-handling code was added anywhere in the repository.

This report does not claim broad legal compliance, publisher
authorization, or production safety beyond these specific, implemented
controls. Live crawling of Detik is now technically possible through the
CLI, but remains subject to the same `robots.txt`, retry, and identity
policies as CNN Indonesia and Kompas; no separate operational rollout
(rate limiting review, monitoring, alerting) was performed as part of
this sprint, and `jsonld_article` compatibility with Detik's real markup
has not been confirmed against a live fetch.

## 11. Production-source governance

### CNN Indonesia

- `source`: `cnn_indonesia`
- `domains`: `www.cnnindonesia.com`
- `parser_family`: `jsonld_article`
- `adapter_key`: `None`
- `enabled`: `True`

### Kompas

- `source`: `kompas`
- `domains`: `www.kompas.com`, `nasional.kompas.com`, `surabaya.kompas.com`
- `parser_family`: `jsonld_article`
- `adapter_key`: `None`
- `enabled`: `True`

### Detik

- `source`: `detik`
- `domains`: `news.detik.com`
- `parser_family`: `jsonld_article`
- `adapter_key`: `None`
- `enabled`: `True` (new in Sprint 17)

All three current production sources are now enabled and behave
identically through registry lookup and parser composition.

## 12. Current limitations

- Detik's `jsonld_article` compatibility is assumed by convention (like
  CNN Indonesia and Kompas), not confirmed against a live fetch;
  real-world content-shape verification remains pending until live
  crawling is separately authorized.
- Only `news.detik.com` is approved; Detik's other verticals remain
  entirely unregistered, requiring their own future, separately-approved
  exact-host declarations if ever wanted.
- The production source set remains intentionally small (three sources);
  no fourth source was added or evaluated in this sprint.
- No realtime or scheduled crawling infrastructure change was made; the
  existing `--interval`/`--urls-file` CLI modes (ADR-028/ADR-029) apply
  to Detik exactly as they already do to CNN Indonesia and Kompas.

## 13. Sprint 16 continuity

Sprint 16 delivered CLI sink selection (ADR-031). Sprint 17 does not
modify `aa_crawler.cli` at all — no CLI code was touched, verified by the
fact that every existing CLI test continues to pass without
modification. This report does not revise or reopen the Sprint 16
completion record.

## 14. Sprint 17 pull-request inventory

- PR #106 — Detik enabled as a real third production source; test
  coverage updated for a third profile across the source and integration
  test suites
- PR #107 — README and Engineering Standards alignment
- PR #(pending) — Sprint 17 completion report (this document)

## 15. Sprint 17 closure checklist

- [x] Governance decision confirmed by the project owner: which source
      (Detik) and which exact host (`news.detik.com` only, no ADR
      required per ADR-020)
- [x] `DETIK_PROFILE` declared and added to `DEFAULT_SOURCE_PROFILES`
- [x] Exact-host boundary confirmed (rejected verticals do not resolve)
- [x] Per-profile and composition test coverage added, mirroring
      CNN/Kompas
- [x] Every existing exact-tuple/exact-`__all__` assertion across the
      source and integration test suites updated for a third profile
- [x] End-to-end registry/composition verification passed against the
      real merged code
- [x] Real GitHub Actions verification (pull_request and push events) on
      the merged implementation and documentation states
- [x] Independent manual smoke test performed, confirming resolution,
      exact-host rejection, and composition
- [x] README aligned
- [x] Engineering Standards aligned
- [ ] Sprint 17 completion report created (this document)
- [ ] Sprint 17 completion report merged
- [ ] `main` synchronized after completion-report merge
- [ ] Final repository verification passed after merge
- [ ] Sprint 17 formally closed

## 16. Provisional post-Sprint-17 direction

No Sprint 18 architecture is approved by this report. Provisional future
areas already supported by current documentation include: persisting to
more than one sink in a single invocation (ADR-031's own deferred
follow-up), a fourth production source or platform proposal (with its own
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

## 17. Completion statement

This report will be merged, local `main` will be synchronized cleanly
with `origin/main`, and the final repository-wide quality gate will be
recorded here at closure time.

**Sprint 17 is pending formal closure.**
