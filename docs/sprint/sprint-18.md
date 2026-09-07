# Sprint 18 Completion Report

## 1. Status

Sprint 18 implementation is complete. Integration verification is
complete. Documentation alignment is complete. This completion report will
be merged, local `main` will subsequently be synchronized cleanly with
`origin/main`, and a final repository-wide verification will run on that
merged state before formal closure.

**Sprint 18 is pending formal closure** (see Section 15).

## 2. Objective

Sprint 18's Architecture Discovery found, for the second sprint in a row,
no crisply-fired ADR review trigger pointing to one obvious candidate.
Candidates were presented on their own merits rather than a forced
"Recommended" pick tied to a specific trigger. The project owner chose CI
security scanning: the pipeline (added Sprint 12) had never run any
security-focused check — no static security analysis, no dependency-
vulnerability audit — a gap unchanged since before Sprint 12 itself. This
was chosen over two alternatives (a fourth production source; a
speculative multi-sink persistence feature with no identified real
requirement).

## 3. Architecture decision

No new ADR was created for Sprint 18, mirroring Sprint 12's own
CI-pipeline precedent: both additions are dev-tooling, not architecture —
neither introduces a runtime dependency for `aa_crawler` itself, neither
changes module structure or a public API, and neither deviates from an
existing standard. Per the Engineering Standards' ADR-trigger criteria
(section 15.3), none of "new runtime dependency for a core component",
"logging/storage/messaging technology selected", "breaking API change",
or "standards deviation" applies.

Earlier accepted decisions remain authoritative in their existing areas;
the [ADR index](../adr/README.md) is unchanged by Sprint 18: 24 Accepted,
2 Proposed, 2 Deferred, and 0 Superseded decisions.

## 4. Implementation: reusing existing tooling wherever possible

Two independent, complementary checks were added, both deliberately
choosing the smallest change available:

**Static security analysis** reuses `ruff check` itself. Ruff's `"S"`
rule category (flake8-bandit-equivalent: hardcoded credentials, insecure
`subprocess`/`eval` usage, weak crypto, and similar patterns) was added to
`pyproject.toml`'s existing `[tool.ruff.lint]` select list — **zero new
dependency, zero new CI step**, since `ruff check` already runs in both
pre-commit and CI. Before finalizing this, a repo-wide preview
(`ruff check .` with `"S"` temporarily enabled) was run to confirm the
change was safe: 1,403 findings surfaced, all in `tests/` — 1,401 were
`S101`
(`assert`, pytest's own idiom) and 2 were `S105` (hardcoded-password
heuristic false-positives on synthetic secret/redaction test fixtures).
Zero findings existed in `src/`. A new
`[tool.ruff.lint.per-file-ignores]` entry excludes `S101` and
`S105`-`S107` for `tests/**`, since none of these reflects a real
security concern in test-only code.

**Dependency-vulnerability auditing** adds `pip-audit` as a new dev
dependency, checking the locked environment against known CVE databases.
It is wired into `.github/workflows/ci.yml` only, as a new step after the
existing test run — not a pre-commit hook — mirroring `uv lock --check`'s
existing precedent of being a CI-only safety net, since auditing depends
on an external vulnerability database rather than being a per-commit,
purely-local code-review concern the way `ruff`/`mypy`/`pytest` are.

## 5. Local verification confirms zero findings

Running the exact CI sequence locally
(`uv lock --check`, `uv sync --locked`, `pre-commit run --all-files`,
`pytest --cov`, `pip-audit`) confirmed: zero `"S"`-category findings
anywhere in the repository after
the `tests/**` exclusions, and `pip-audit` reports "No known
vulnerabilities found" for the current dependency set (`httpx`,
`pydantic`, `pydantic-settings`, and the full dev-tooling set including
the newly-added `pip-audit` itself and its own transitive dependencies).

## 6. No architectural, dependency, or credential change to `aa_crawler`

Per this sprint's explicit scope: no change to `ArticleCrawlService`,
`ApplicationRuntime`, the CLI, `aa_crawler.persistence`, or
`aa_crawler.sources`. `pip-audit` and its transitive dependencies are dev
dependencies only, never imported by `src/aa_crawler`. No credential or
authentication mechanism was introduced anywhere in `http/` or
`identity/`.

## 7. Testing architecture

This sprint adds no new `pytest` tests (it is a tooling/lint-configuration
and CI-workflow change, not application code), but does add its own
verification:

- A one-time, discarded preview run (`ruff check .` with `"S"` enabled,
  before the `per-file-ignores` entry existed) established the safety of
  the change by confirming all findings were test-only and expected.
- The final configuration was verified to produce zero findings
  repository-wide via the same `ruff check .` command already part of
  `pre-commit run --all-files`.
- `pip-audit` was run locally and observed to report no known
  vulnerabilities, both before and after the merge.
- All 927 existing tests continue to pass unmodified, confirming this
  sprint introduced no behavioral change to `aa_crawler` itself.

## 8. Quality gates

The repository verification strategy uses:

- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy`
- `uv run pytest`
- `uv run pytest --cov=aa_crawler`, with the configured minimum of 70%
- `uv lock --check` for lockfile consistency
- `uv run pip-audit` for dependency-vulnerability auditing (new this
  sprint)
- `uv --cache-dir .uv-cache run pre-commit run --all-files`

Sprint 18 implementation, integration-verification, and documentation
tasks passed their applicable focused and repository-wide gates
throughout, both locally and via the real GitHub Actions CI pipeline
(Sprint 12) — including the new `pip-audit` step itself, exercised for
the first time as part of this sprint's own pull requests. The
verification run on the merged documentation-alignment state
(`132aef3afebaf7c0dc2598c704e155f570a6748d`) confirmed:

- Ruff: passed (including the new `"S"` category)
- Ruff format check: passed
- mypy: passed
- pytest: 927 passed, 0 skipped, 0 xfailed, 0 failed, 0 errors
- Coverage: 95.05%, against the configured 70% threshold
- `uv lock --check`: passed
- `pip-audit`: no known vulnerabilities found
- pre-commit: all hooks passed
- Real GitHub Actions `pull_request`-event and `push`-event runs on this
  same merged state: both completed with a `success` conclusion
- Critical findings: 0
- Major findings: 0

The final repository-wide verification, required for closure and run
after this completion report itself is merged, will be recorded in
Section 15 below at closure time.

## 9. Security and safety review

- This sprint is itself a security-hardening change: it adds detection
  for a class of code-level security issues (via `ruff`'s `"S"` rules)
  and a class of supply-chain issues (via `pip-audit`) that previously had
  no automated coverage at all.
- No credential-handling code was added anywhere in the repository; the
  two new checks are read-only analysis tools.
- `pip-audit`'s own dependency footprint (a JSON-schema/CycloneDX-capable
  SCA tool with several transitive dependencies) is dev-only and never
  reaches `aa_crawler`'s runtime dependency set.
- No test performs a live network acquisition of a real crawl target;
  `pip-audit` does reach the network (querying a vulnerability database),
  but only in CI, matching `uv lock --check`'s existing precedent of being
  the one narrow exception to this project's otherwise network-isolated
  verification discipline.

This report does not claim the codebase is free of all possible security
issues — only that the two specific, automated checks added this sprint
currently report none, and that both now run automatically on every push
and pull request rather than depending on manual review.

## 10. Current limitations

- Ruff's `"S"` rule category is a useful but partial subset of what a
  dedicated tool like Bandit itself covers; it was chosen specifically to
  avoid a new dependency, not because it is claimed to be exhaustive.
- `pip-audit` checks only the currently locked dependency set at CI time;
  it does not continuously monitor for newly-disclosed vulnerabilities
  between CI runs (e.g., no scheduled/cron-triggered audit exists yet).
- No SBOM (software bill of materials) is published or attached to any
  release artifact.
- No secret-scanning (e.g., for accidentally committed credentials in git
  history) was added; this sprint's static analysis operates on the
  current working tree only, not commit history.

## 11. Sprint 17 continuity

Sprint 17 delivered Detik as a third production source. Sprint 18 does
not modify `aa_crawler.sources`, the CLI, or persistence at all; every
existing test continues to pass unmodified, confirming no behavioral
change. This report does not revise or reopen the Sprint 17 completion
record.

## 12. Sprint 18 pull-request inventory

- PR #110 — Security scanning implementation (ruff `"S"` rules,
  `pip-audit` CI step)
- PR #111 — README and Engineering Standards alignment
- PR #(pending) — Sprint 18 completion report (this document)

## 13. Sprint 18 closure checklist

- [x] Architecture Discovery presented evidence-backed candidates
      (no crisply-fired trigger this sprint, same as Sprint 17); project
      owner selected CI security scanning
- [x] Confirmed no ADR trigger applies (Engineering Standards Section
      15.3), mirroring Sprint 12's precedent
- [x] Ruff `"S"` rule category enabled with a safety preview beforehand
      (1,403 test-only findings confirmed safe to exclude)
- [x] `per-file-ignores` entry added for `tests/**`; `src/` confirmed at
      zero findings
- [x] `pip-audit` added as a new dev dependency and CI-only step
- [x] Local verification of the exact CI command sequence, confirming
      zero findings and no known vulnerabilities
- [x] Real GitHub Actions `pull_request`-event and `push`-event runs
      confirmed green, including the new `pip-audit` step itself
- [x] All 927 existing tests confirmed passing unmodified
- [x] README aligned
- [x] Engineering Standards aligned
- [ ] Sprint 18 completion report created (this document)
- [ ] Sprint 18 completion report merged
- [ ] `main` synchronized after completion-report merge
- [ ] Final repository verification passed after merge
- [ ] Sprint 18 formally closed

## 14. Provisional post-Sprint-18 direction

No Sprint 19 architecture is approved by this report. Provisional future
areas already supported by current documentation include: persisting to
more than one sink in a single invocation (ADR-031's own deferred
follow-up), a fourth production source or platform proposal (with its own
legal/acquisition/credential review), non-HTML content acquisition, a
credential/authentication mechanism, separately reviewed redirect
architecture, alternate execution runtimes under ADR-019, concurrent
per-URL crawling within one batch pass, a remote/dynamic URL-list source,
distributed worker/queue concerns under ADR-017, health/liveness
signaling for long-running scheduled/batch processes, and further CI
hardening not yet in scope (scheduled/periodic vulnerability re-scanning
independent of pushes, secret-scanning across git history, SBOM
publication, performance benchmarking). Each requires its own explicit
scope and architecture approval before implementation. Social media
platforms remain explicitly out of scope for `aa_crawler` itself, per the
project owner's own stated direction.

## 15. Completion statement

This report will be merged, local `main` will be synchronized cleanly
with `origin/main`, and the final repository-wide quality gate will be
recorded here at closure time.

**Sprint 18 is pending formal closure.**
