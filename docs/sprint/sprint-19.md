# Sprint 19 Completion Report

## 1. Status

Sprint 19 implementation is complete. Integration verification is
complete. Documentation alignment is complete. This completion report
was merged, local `main` was subsequently synchronized cleanly with
`origin/main`, and the final repository-wide verification (Section 6)
passed on that merged state with no Critical or Major findings.

**Sprint 19 is formally closed.**

## 2. Objective

Sprint 19 is the first of four sprints in the MVP-completion roadmap the
project owner locked this session, after asking "how many sprints are
left" and defining "done" as a minimal production-ready MVP rather than
an open-ended backlog. A repository-wide investigation (triggered by the
project owner's own follow-up question, "can this actually run for
crawling?") found that no production source had ever been empirically
verified against a real site, and that any HTTP 3xx response was a hard
failure — a concrete blocker, since Indonesian news sites commonly
redirect real article URLs via shortlinks, AMP variants, or moved
articles. Sprint 19's scope, unlike Sprint 17/18's open-ended
Architecture Discovery, was therefore pre-selected by the project owner
as part of that roadmap decision: close the redirect gap.

## 3. Architecture decision

[ADR-032](../adr/0032-bounded-redirect-following.md) (Bounded Redirect
Following) was accepted. `HtmlFetcher.fetch()` now runs a bounded, manual
redirect loop instead of delegating to httpx's own automatic redirect
chase: each hop (including the first) is independently URL-validated and
robots-checked before it is requested; a 3xx response with a `Location`
header advances to the next hop, resolved via stdlib
`urllib.parse.urljoin`; the loop is capped at 5 hops, and exceeding the
cap raises a new `TooManyRedirectsError(ResponseError)`. `HttpClient`'s
`httpx.Client` deliberately keeps `follow_redirects` unset (`False`) —
using httpx's own automatic chase was rejected because it happens beneath
`HtmlFetcher` and would skip the per-hop robots.txt check for every hop
after the first, an unacceptable regression of this project's stated
robots-compliance stance. A stricter per-hop source-registry validation
during the chase was also considered and rejected as disproportionate to
the current threat model; it is recorded as an accepted, documented
residual risk rather than an oversight.

The [ADR index](../adr/README.md) now lists 25 Accepted, 2 Proposed, 2
Deferred, and 0 Superseded decisions.

## 4. Implementation

`HtmlDocument.final_url` — an existing field, previously always equal to
`requested_url` because nothing had ever produced a genuine redirect —
now reflects a real transport-produced landing page for the first time.
`ArticleCrawlService`'s existing `SourceBoundaryError` profile-identity
check on `final_url` is unchanged; this sprint is what finally gives that
check something real to validate, confirmed by two new integration tests
driving a real `HtmlFetcher` (not a fabricated `final_url`) through
`ArticleCrawlService`: one proving a cross-profile redirect landing still
raises `SourceBoundaryError`, one proving a same-profile redirect still
succeeds.

No new runtime dependency was introduced. No change was made to
`ArticleCrawlService`, `ApplicationRuntime`, `SourceRegistry`,
`SourceProfile`, any parser family, or the CLI's argument surface,
output contract, or exit-code table — `TooManyRedirectsError` subclasses
`ResponseError`, already bucketed under ADR-023's existing
crawl-domain-failure exit code.

## 5. Testing architecture

New tests were added at two layers:

- `tests/html/test_fetcher.py` (unit level, extending the existing
  fake-`HttpClient` sequence-of-responses idiom): a single redirect hop
  resolving to a 2xx; a relative `Location` header resolving correctly
  against the current hop; a 3xx response with no `Location` header
  still raising `ResponseError`; non-redirect failure statuses (404,
  500); a chain of exactly 5 hops succeeding; a 6th hop raising
  `TooManyRedirectsError`; robots.txt disallowing an intermediate hop
  raising `HtmlDisallowedError` before that hop's page request is ever
  sent.
- `tests/crawler/test_errors.py`: `TooManyRedirectsError`'s place in the
  exception hierarchy (a `ResponseError`, therefore a `CrawlerError`).
- `tests/integration/test_application_article_crawl.py` (integration
  level, new this sprint): a real `HtmlFetcher` — backed by a fake
  `HttpClient` and a real `RobotsPolicy`, not a fabricated `final_url` —
  driven through `ArticleCrawlService`, confirming `SourceBoundaryError`
  still fires for a genuine cross-profile redirect landing, and that a
  same-profile redirect still succeeds and resolves the correct
  `source_domain`.

No test performs a live network acquisition; all HTTP responses remain
synthetic, per this project's standing no-live-network-request testing
constraint. `html/fetcher.py` reached 100% branch coverage as a direct
result of this sprint's tests.

## 6. Quality gates

The repository verification strategy uses:

- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy`
- `uv run pytest`
- `uv run pytest --cov=aa_crawler`, with the configured minimum of 70%
- `uv lock --check` for lockfile consistency
- `uv run pip-audit` for dependency-vulnerability auditing
- `uv --cache-dir .uv-cache run pre-commit run --all-files`

Sprint 19's ADR, implementation, and documentation-alignment tasks each
passed their applicable focused and repository-wide gates, both locally
and via the real GitHub Actions CI pipeline:

- Ruff: passed (including the `"S"` security category)
- Ruff format check: passed
- mypy: passed, no issues in 126 source files
- pytest: 941 passed, 0 skipped, 0 xfailed, 0 failed, 0 errors (up from
  927 at Sprint 18's close)
- Coverage: 95.09% (up from 95.05%), against the configured 70%
  threshold; `html/fetcher.py` at 100% branch coverage
- `uv lock --check`: passed (no dependency change this sprint)
- `pip-audit`: no known vulnerabilities found
- pre-commit: all hooks passed

Real GitHub Actions runs confirmed each merge independently:

- ADR-032 (`c9e7744`): `pull_request` run
  (`https://github.com/muhammadarifalfani/aa-crawler/actions/runs/34135903607`)
  and the `push` run on `main` at `79cd32f`
  (`https://github.com/muhammadarifalfani/aa-crawler/actions/runs/34136137954`)
  both completed with a `success` conclusion.
- Implementation (`a2fe4b7`): `pull_request` run
  (`https://github.com/muhammadarifalfani/aa-crawler/actions/runs/34137393911`)
  and the `push` run on `main` at `64ef27a`
  (`https://github.com/muhammadarifalfani/aa-crawler/actions/runs/34137480835`)
  both completed with a `success` conclusion.
- Documentation alignment (`dcfc000`): `pull_request` run
  (`https://github.com/muhammadarifalfani/aa-crawler/actions/runs/34138477712`)
  and the `push` run on `main` at `e07d8cf`
  (`https://github.com/muhammadarifalfani/aa-crawler/actions/runs/34138589103`)
  both completed with a `success` conclusion.
- Completion report (`2b23bac`): `pull_request` run
  (`https://github.com/muhammadarifalfani/aa-crawler/actions/runs/34139196997`)
  and the `push` run on `main` at `c9d9d1d`
  (`https://github.com/muhammadarifalfani/aa-crawler/actions/runs/34139364524`)
  both completed with a `success` conclusion.

The final repository-wide verification, required for closure and run
after this completion report itself was merged, on
`c9d9d1ddf55e77b66b5d3399db6b15cffbf3116e`, confirmed:

- `uv lock --check`: passed (no dependency change this sprint)
- `uv sync --locked`: passed
- pre-commit: all hooks passed (ruff check, ruff format, mypy, pytest)
- pytest: 941 passed, 95.09% coverage, against the configured 70%
  threshold
- `pip-audit`: no known vulnerabilities found

Critical findings: 0. Major findings: 0.

## 7. Security and safety review

- Robots.txt compliance is strengthened, not merely preserved: every
  redirect hop is now robots-checked, not only the originally requested
  URL.
- The redirect loop is bounded (5 hops), preventing an unbounded number
  of requests from a redirect loop or an unexpectedly long chain.
- `TooManyRedirectsError` is deliberately not added to the retryable
  exception set — retrying a redirect loop would only repeat the same
  loop — consistent with ADR-015's existing idempotent-retry scope.
- Accepted, documented residual risk: only the terminal `final_url` is
  validated against the requested URL's resolved `SourceProfile`
  (`ArticleCrawlService`, unchanged); intermediate hop hosts visited
  during the chase are not individually checked against the source
  registry, only against robots.txt for that host. This mirrors the
  existing trust boundary — the entry URL is already vetted as belonging
  to an approved, publisher-reviewed source — and is recorded in ADR-032
  as an explicit trade-off, not an oversight.
- No credential-handling code was added anywhere in the repository. No
  new runtime dependency was introduced.
- This sprint does not close the gap identified by the investigation
  that motivated it: rate limiting and politeness delay between
  requests remain entirely unaddressed, and are Sprint 20's own locked
  scope, not this sprint's.

## 8. Current limitations

- Redirect following is bounded at 5 hops; a legitimate chain longer
  than 5 hops (not observed in practice, but not impossible) would fail
  with `TooManyRedirectsError` rather than succeeding.
- Only the terminal landing page's host is checked against the source
  registry; an intermediate hop's host is not (see Section 7).
- No live crawl against any real site has been authorized or run in this
  sprint; ADR-032's behavior remains verified only against synthetic
  HTTP responses. The first authorized live crawl is Sprint 22's own
  locked scope.
- Rate limiting and politeness delay between requests remain entirely
  unaddressed (Sprint 20's own locked scope).

## 9. Sprint 18 continuity

Sprint 18 delivered CI security scanning (ruff `"S"`, `pip-audit`).
Sprint 19 does not modify `pyproject.toml`, `.github/workflows/ci.yml`,
or any CI configuration; every existing quality gate continues to run
and pass unmodified. This report does not revise or reopen the Sprint 18
completion record.

## 10. Sprint 19 pull-request inventory

- PR #115 — ADR-032 (Bounded Redirect Following) decision document
- PR #116 — Bounded redirect following implementation
- PR #117 — README and Engineering Standards alignment
- PR #118 — Sprint 19 completion report
- PR #119 — Sprint 19 formal closure (this patch)

## 11. Sprint 19 closure checklist

- [x] Architecture Discovery investigated the concrete redirect gap
      blocking real crawling of all three active sources
- [x] ADR-032 drafted, reviewed, and accepted
- [x] `HtmlFetcher.fetch()` implements a bounded, robots-rechecked
      redirect loop; `TooManyRedirectsError` added
- [x] No new CLI exit code required; confirmed by the existing
      exception-to-exit-code mapping
- [x] Real `HtmlFetcher`-driven integration tests confirm
      `SourceBoundaryError` still fires correctly for a genuine
      cross-profile redirect landing
- [x] All 941 tests passing, 95.09% coverage, `html/fetcher.py` at 100%
      branch coverage
- [x] Real GitHub Actions `pull_request`-event and `push`-event runs
      confirmed green for all three implementation-phase PRs
- [x] README aligned
- [x] Engineering Standards aligned
- [x] Sprint 19 completion report created
- [x] Sprint 19 completion report merged
- [x] `main` synchronized after completion-report merge
- [x] Final repository verification passed after merge
- [x] Sprint 19 formally closed

## 12. Provisional post-Sprint-19 direction

Per the MVP-completion roadmap locked this session, Sprint 20 is
**rate limiting / politeness delay** — added specifically because the
investigation that motivated Sprint 19 also found zero rate limiting
anywhere in the acquisition path, a real risk of a real site IP-blocking
the crawler once live crawling begins. Sprint 21 (health/liveness
signaling) and Sprint 22 (an authorized live crawl smoke test bundled
with scheduled CI vulnerability re-scanning) follow after. This scope is
pre-selected, not open-ended Architecture Discovery, per the locked
roadmap; each sprint's Discovery task still confirms ADR-trigger status
and drafts an ADR where warranted.

## 13. Completion statement

This report was merged, local `main` was synchronized cleanly with
`origin/main` at `c9d9d1ddf55e77b66b5d3399db6b15cffbf3116e`, and the
final repository-wide quality gate — both the local command sequence
and the real GitHub Actions pipeline itself — passed on that merged
state with no Critical or Major findings.

**Sprint 19 is formally closed.**
