# Sprint 11 Completion Report

## 1. Status

Sprint 11 implementation is complete. Integration verification is
complete. Documentation alignment is complete. This completion report was
merged, local `main` was subsequently synchronized cleanly with
`origin/main`, and the final repository-wide verification (Section 8)
passed on that merged state with no Critical or Major findings.

**Sprint 11 is formally closed.**

## 2. Objective

Sprint 10's completion report explicitly deferred the second half of the
project owner's stated Sprint 10 goal — enabling a real second production
source — as its own, separate, project-owner governance decision. Sprint 11
closes that gap: the project owner chose to activate Kompas, a source
already registered (but disabled) since Sprint 4, after confirming there
was no objection to crawling it. This is a governance decision, not an
architectural change: no new parser family, no new `SourceProfile` field,
no new registry or composition behavior, and no new ADR were required,
because [ADR-020](../adr/0020-declarative-source-architecture.md) already
pre-authorizes ordinary onboarding of a structurally compatible source
("Ordinary compatible sources are added profile-first and reuse the generic
parser").

## 3. Architecture decision

No new ADR was created for Sprint 11. Kompas is a structurally ordinary
source — same `jsonld_article` parser family as CNN Indonesia, already-
declared exact hosts, no adapter — so ADR-020's existing "ordinary source
onboarding" and "Enabled and disabled governance" sections fully authorize
this change.

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

The [ADR index](../adr/README.md) is unchanged by Sprint 11: 20 Accepted, 2
Proposed, 2 Deferred, and 0 Superseded decisions.

## 4. Implementation: Kompas enabled

`src/aa_crawler/sources/profiles.py` changed `KOMPAS_PROFILE.enabled` from
`False` to `True`. No other field of `KOMPAS_PROFILE` changed:

- `source`: `kompas`
- `domains`: `www.kompas.com`, `nasional.kompas.com`, `surabaya.kompas.com`
- `parser_family`: `jsonld_article`
- `adapter_key`: `None`
- `enabled`: `True` (was `False`)

`DEFAULT_SOURCE_PROFILES` still declares exactly two profiles, in the same
order (`CNN_INDONESIA_PROFILE`, `KOMPAS_PROFILE`). The module docstring was
updated to record the Sprint 11 governance rationale in place, per this
project's existing convention of documenting *why* a production profile is
enabled directly alongside its declaration.

With this one-line change, Kompas resolves through normal (non-
`include_disabled`) `SourceRegistry` lookup and composes into a real
`JsonLdArticleParser` exactly like CNN Indonesia — the source-composition
pipeline required no code change beyond the flag itself, confirming the
declarative-source architecture (ADR-020) behaves as designed.

## 5. Test-fixture decoupling from Kompas's real-world state

Before Sprint 11, six test files used Kompas specifically because it was
disabled, to demonstrate "disabled source" mechanisms (registry exclusion,
composition rejection, CLI/application rejection before acquisition). Since
those tests were demonstrating a *mechanism*, not Kompas's specific
real-world governance state, enabling Kompas required rewriting them onto a
synthetic `SourceProfile(source="disabled_example", domains=("disabled.example",), enabled=False)`
fixture instead — preserving the exact original coverage without depending
on any real production source's governance state:

- `tests/sources/test_profiles.py` — Kompas property test now asserts
  `enabled is True`; registry-resolution test now expects normal
  resolution; a new `test_disabled_profile_lookup_mechanism_still_works_for_a_synthetic_source`
  covers `include_disabled` independently; the old disabled-composition
  test split into `test_kompas_profile_now_composes_like_any_other_enabled_source`
  and a new synthetic `test_disabled_profile_cannot_be_composed`.
- `tests/integration/test_source_composition.py` — replaced two
  Kompas-disabled tests with `test_kompas_resolves_and_composes_like_any_other_enabled_source`
  and two synthetic-profile tests covering the disabled-blocking mechanism.
- `tests/integration/test_application_article_crawl.py` — replaced
  `test_disabled_kompas_stops_before_acquisition_or_composition` with
  `test_disabled_synthetic_source_stops_before_acquisition_or_composition`.
- `tests/integration/test_cli_process_boundary.py` — rewrote the
  CLI-process-boundary disabled-source test to monkeypatch
  `runtime_module.DEFAULT_SOURCE_PROFILES` with an added synthetic disabled
  profile, then exercise that synthetic URL through the real end-to-end
  pipeline (real bootstrap, runtime, registry, and parser composition).
- `tests/cli/test_cli.py` — an unrelated unit test's placeholder URL was
  changed from a Kompas URL to a fully-synthetic `unsupported.example.test`
  URL, since that test uses a faked service and never touches the real
  registry; the Kompas URL there was incidental, not load-bearing.

This is the same "verify tests fail for the expected reason before flipping
the flag, then verify exactly those tests turn green after" sequence used
throughout this project: the rewritten tests were confirmed to fail against
the still-disabled flag (4 failures, all for the expected reason — the flag
not yet flipped, no surprises), then `KOMPAS_PROFILE.enabled` was flipped,
and the suite was re-run to confirm exactly those 4 tests turned green with
no other regression (839 passed, up from 836/835 depending on the
intermediate step).

## 6. No architectural, dependency, or credential change

Per the governance-only nature of this change: no new parser family, no new
`SourceProfile` field, no new registry or composition behavior, no new CLI
argument, no new exit code, no new sink, and no new third-party dependency
were introduced. No credential or authentication mechanism was introduced
anywhere in `http/` or `identity/`. `ArticleCrawlService` and
`ApplicationRuntime` remain fully unaware of `aa_crawler.persistence`,
unaffected by this sprint.

## 7. Testing architecture

- `tests/sources/test_profiles.py`, `tests/integration/test_source_composition.py`,
  `tests/integration/test_application_article_crawl.py`,
  `tests/integration/test_cli_process_boundary.py`, and
  `tests/cli/test_cli.py` were updated per Section 5.
- No test performs a live network acquisition of a real source or uses a
  real credential. Per the project owner's standing direction (originally
  given in Sprint 10 Task 10.1), verification fixtures mirror real observed
  markup structure with invented, non-copyrighted article content — never a
  verbatim copy of a real publisher's text. Sprint 11 introduced no new
  fixture content; it reused the existing synthetic JSON-LD shapes already
  present in the suite.

## 8. Quality gates

The repository verification strategy uses:

- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy`
- `uv run pytest`
- `uv run pytest --cov=aa_crawler`, with the configured minimum of 70%
- `uv lock --check` for lockfile consistency
- `uv --cache-dir .uv-cache run pre-commit run --all-files`

Sprint 11 implementation, integration-verification, and documentation
tasks passed their applicable focused and repository-wide gates
throughout. The verification run on the merged documentation-alignment
state (`735d016ec03d1b823ce4f3b5c39502174889e6fe`) confirmed:

- Ruff: passed
- Ruff format check: passed
- mypy: passed
- pytest: 839 passed, 0 skipped, 0 xfailed, 0 failed, 0 errors
- Coverage: 94.48%, against the configured 70% threshold
- `uv lock --check`: passed
- pre-commit: all hooks passed
- Critical findings: 0
- Major findings: 0

The final repository-wide verification, required for closure and run after
this completion report itself was merged, on
`53ad68d47a12615c489732558ea3be25d331d999`, confirmed the same result:

- Ruff: passed
- Ruff format check: passed
- mypy: passed
- pytest: 839 passed, 0 skipped, 0 xfailed, 0 failed, 0 errors
- Coverage: 94.48%, against the configured 70% threshold
- `uv lock --check`: passed
- pre-commit: all hooks passed
- Critical findings: 0
- Major findings: 0

## 9. Security and safety review

- Enabling Kompas changes only project-internal governance state
  (`enabled=True` on an already-declared, already-validated
  `SourceProfile`). It does not itself constitute legal authorization,
  publisher permission, robots authorization, rate-limit approval, or
  operational approval — see ADR-020's "Enabled and disabled governance"
  section, quoted verbatim in `profiles.py`'s own module docstring.
- No crawl request against Kompas or any other host was made by this
  sprint's implementation or test work; all test coverage uses in-memory
  fixtures and network-isolated pipelines, consistent with every prior
  sprint's testing discipline.
- Host matching for Kompas remains exact (`www.kompas.com`,
  `nasional.kompas.com`, `surabaya.kompas.com`); no wildcard, suffix, or
  implicit subdomain matching was introduced.
- No credential-handling code was added anywhere in the repository.

This report does not claim broad legal compliance, publisher authorization,
or production safety beyond these specific, implemented controls. Live
crawling of Kompas is now technically possible through the CLI, but remains
subject to the same `robots.txt`, retry, and identity policies as CNN
Indonesia; no separate operational rollout (rate limiting review, monitoring,
alerting) was performed as part of this sprint.

## 10. Production-source governance

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
- `enabled`: `True` (changed from `False` in Sprint 11)

Both current production sources are now enabled and behave identically
through registry lookup and parser composition.

## 11. Dependencies

Direct runtime dependencies, verified from `pyproject.toml`, are unchanged:

- `httpx>=0.28.1,<0.29`
- `pydantic>=2.13.4,<3`
- `pydantic-settings>=2.14.2,<2.15`

Sprint 11 added no third-party dependency.

## 12. Current limitations

- The production source set remains intentionally small (two sources); no
  third source was added or evaluated in this sprint.
- No realtime or scheduled crawling infrastructure exists; both sources are
  still crawled only via a single synchronous CLI invocation per URL.
- No second sink type, batch/multi-URL CLI input, non-HTML content
  acquisition, or credential/authentication mechanism was introduced.
- No separate operational rollout review (rate limiting, monitoring,
  alerting) was performed for Kompas specifically.
- Social media platforms remain explicitly out of scope for this project;
  they are project-owner-designated separate future projects.

## 13. Sprint 10 continuity

Sprint 10 delivered CLI-triggered persistence (ADR-027) and explicitly
deferred enabling a second production source as a separate governance
decision. Sprint 11 delivers exactly that deferred second half. This report
does not revise or reopen the Sprint 10 completion record.

## 14. Sprint 11 pull-request inventory

- PR #78 — Kompas enabled as a real second production source; disabled-
  source test coverage decoupled onto a synthetic profile
- PR #79 — README and Engineering Standards alignment
- PR #80 — Sprint 11 completion report

## 15. Sprint 11 closure checklist

- [x] Governance decision confirmed by the project owner (no ADR required
      per ADR-020)
- [x] `KOMPAS_PROFILE.enabled` flipped to `True`
- [x] Disabled-source test coverage decoupled onto a synthetic profile
      across 6 test files
- [x] Target-state-first verification: rewritten tests confirmed to fail
      for the expected reason before the flag was flipped, then confirmed
      to pass afterward with no other regression
- [x] End-to-end integration test (CLI process boundary) updated and
      passing against the real pipeline
- [x] README aligned
- [x] Engineering Standards aligned
- [x] Sprint 11 completion report created
- [x] Sprint 11 completion report merged
- [x] `main` synchronized after completion-report merge
- [x] Final repository verification passed after merge
- [x] Sprint 11 formally closed

## 16. Provisional post-Sprint-11 direction

No Sprint 12 architecture is approved by this report. Provisional future
areas already supported by current documentation include: a third
production source or platform proposal (with its own legal/acquisition/
credential review), realtime or scheduled crawling infrastructure, a
second concrete persistence sink, non-HTML content acquisition, a
credential/authentication mechanism, separately reviewed redirect
architecture, alternate execution runtimes under ADR-019, worker/queue/
scheduler concerns, and the previously-deferred CI pipeline/coverage-
reporting/structured-logging/performance/security-scanning work. Each
requires its own explicit scope and architecture approval before
implementation. Social media platforms (e.g. a separate Crawler TikTok or
Crawler Instagram project) are explicitly out of scope for `aa_crawler`
itself, per the project owner's own stated direction.

## 17. Completion statement

This report was merged, local `main` was synchronized cleanly with
`origin/main` at `53ad68d47a12615c489732558ea3be25d331d999`, and the final
repository-wide quality gate passed on that merged state with no Critical
or Major findings.

**Sprint 11 is formally closed.**
