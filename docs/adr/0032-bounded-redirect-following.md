# ADR-032 — Bounded Redirect Following

- Status: Accepted
- Date: 2026-09-07
- Decision owners: HTTP/HTML owner, Application owner, Tech Lead
- Related ADRs: ADR-003, ADR-005, ADR-014, ADR-015, ADR-020, ADR-021, ADR-023

## Context

The project owner defined "done" for `aa_crawler` as a minimal
production-ready MVP and, after an investigation into whether the
crawler can actually run against real sites, locked redirect handling as
Sprint 19's scope — the first of four remaining MVP sprints. Today,
`HtmlFetcher.fetch()` treats any non-2xx response, including every 3xx
redirect, as a hard `ResponseError`
(`src/aa_crawler/html/fetcher.py:96-98`); `HttpClient` never passes
`follow_redirects` to `httpx.Client`, so httpx's own default
(`follow_redirects=False`) applies
(`src/aa_crawler/http/client.py:46-49`). README.md documents this
explicitly as a current limitation. Indonesian news sites commonly
redirect real article URLs — shortlinks, AMP variants, or articles moved
to a new path — so this is a concrete blocker to real production
crawling of all three active sources (`cnn_indonesia`, `kompas`,
`detik`), not a hypothetical one.

ADR-023 already anticipated this gap and deliberately deferred it: its
scope boundaries explicitly exclude "redirect traversal", and its review
triggers name "redirect... is approved and needs CLI-surfaced behavior"
as a condition for revisiting the CLI's exit-code table. This ADR is
that follow-up decision.

Two pieces of supporting architecture already exist, unused until now:
`HtmlDocument` already carries both `requested_url` and `final_url`
(`src/aa_crawler/html/models.py`), and `ArticleCrawlService.crawl()`
already re-resolves a `SourceProfile` from `final_url` and raises
`SourceBoundaryError` unless it is the exact same profile instance
resolved for the requested URL (`src/aa_crawler/application/service.py`).
Both are already exercised by tests
(`tests/integration/test_application_article_crawl.py`,
`tests/integration/test_cli_process_boundary.py`) using a fake fetcher
that fabricates a `final_url` directly — because nothing has ever
actually produced a *different* `final_url` in production. This ADR's
job is narrower than it might first appear: make `final_url` genuinely
reflect a redirect chain's landing point, and let the existing
profile-identity check keep doing exactly what it already does.

## Decision drivers

- Close the concrete redirect gap blocking real crawling of all three
  active sources, without reopening scope ADR-023 deliberately deferred
  (persistence, alternate execution, batch input, worker/queue
  architecture — all unaffected here).
- Preserve robots.txt compliance for every hop a redirect chain visits,
  not only the originally requested URL — this project has a dedicated
  `robots/` module specifically because robots compliance is a stated
  governance requirement (ADR-005), and silently bypassing it for
  redirect targets would quietly regress that guarantee.
- Preserve ADR-020's exact-host governance model: a redirect must never
  let the crawler treat an unapproved or unrelated host as though it
  were part of the requested source, and the existing
  `ArticleCrawlService` profile-identity check on `final_url` must
  remain the sole authority for that boundary — this ADR must not
  duplicate or weaken it.
- Bound worst-case cost: a redirect loop or an unexpectedly long chain
  must fail predictably rather than loop indefinitely or make an
  unbounded number of requests.
- No new runtime dependency, no change to `ArticleCrawlService`,
  `SourceRegistry`, or any parser family — reuse existing components
  (`HttpClient.send()`, `RobotsPolicy.allowed()`, stdlib `urllib.parse`)
  exactly as ADR-030's SQLite sink reused stdlib `sqlite3` instead of
  adding a dependency.
- Stay inside the existing exit-code bucket ADR-023 already reserved for
  crawl-domain failures rather than inventing a new CLI-visible category,
  unless the exception hierarchy genuinely requires one.

## Considered options

1. Flip `follow_redirects=True` on `HttpClient`'s underlying
   `httpx.Client`, relying entirely on httpx's own redirect machinery and
   the existing post-hoc `ArticleCrawlService` profile check on the final
   response.
2. Implement a bounded, manual redirect loop inside `HtmlFetcher.fetch()`
   that re-validates robots.txt and resolves each hop itself, using only
   existing `HttpClient`/`RobotsPolicy` primitives — httpx's own
   `follow_redirects` stays `False`.
3. Push per-hop source/domain validation down into `HtmlFetcher` itself
   (giving it a `SourceRegistry` dependency), rejecting any hop whose host
   is not a known profile before continuing the chase.

## Decision

Adopt Option 2. `HttpClient` keeps `follow_redirects=False` unchanged —
httpx never auto-chases a redirect. Instead, `HtmlFetcher.fetch()` runs
its own bounded loop: on each iteration it validates the current URL
(reusing the existing `_validate_url` check), re-checks
`RobotsPolicy.allowed(target_url=...)` for that URL, and sends the
request. A 2xx response ends the loop as it does today. A 3xx response
with a `Location` header resolves the next URL via stdlib
`urllib.parse.urljoin` (correctly handling a relative `Location`) and
continues the loop; a 3xx response with no `Location` header, or any
other non-2xx response, raises `ResponseError` exactly as it does today.
The loop is capped at 5 hops (a new module-level constant); exceeding
the cap raises a new `TooManyRedirectsError(ResponseError)` defined in
`src/aa_crawler/crawler/errors.py`. `HtmlDocument.final_url` is set to
whichever URL actually returned the 2xx response — genuinely different
from `requested_url` for the first time, using a field that already
exists and is already consumed downstream. Option 1 is rejected because
httpx's own redirect chase happens beneath `HtmlFetcher`, so it would
skip the per-hop robots.txt check entirely for every hop after the
first — an unacceptable, silent regression of this project's stated
robots.txt compliance stance. Option 3 is rejected because it would push
a `SourceProfile`/`SourceRegistry` dependency into `html/`, a layer
ADR-020 deliberately keeps source-agnostic; the existing
`ArticleCrawlService` check on `final_url` already provides that
boundary at the correct layer, and duplicating it lower down would be
redundant governance surface for no added safety.

### Scope

This crawler only ever issues GET requests, so httpx's own
redirect-driven method-rewriting rules (for example, downgrading a POST
to a GET on a 301/302/303) are not relevant here and are not
replicated. The 5-hop cap is a fixed constant, not a new CLI argument —
real news-site redirect chains observed in the wild are typically one or
two hops (a shortlink or AMP page to its canonical article); 5 leaves
comfortable headroom while keeping the worst case for a misconfigured or
malicious chain far below httpx's own default of 20.

### Residual risk, accepted

Only the *terminal* `final_url` is validated against the requested
URL's resolved `SourceProfile` (by `ArticleCrawlService`, unchanged);
intermediate hop hosts visited during the chase are not individually
checked against the source registry, only against robots.txt for that
host. This mirrors the project's existing trust boundary: the entry URL
is already vetted as belonging to an approved, publisher-reviewed
source (ADR-020), and this project does not defend against a
compromised or maliciously authored redirect target on an already-
approved site — the same trust assumption ADR-014 already makes about
page content generally. A stricter per-hop domain allowlist was
considered (Option 3) and rejected as disproportionate to the current
threat model; it can be revisited if a real requirement emerges (for
example, if a future remote/dynamic URL-list source removes the
assumption that every entry URL was reviewed before being supplied).

## Rationale

This is the smallest change that makes the existing, already-tested
`final_url`/`SourceBoundaryError` mechanism actually do something in
production, without weakening this project's robots.txt compliance
posture or its exact-host governance model. It reuses every primitive
already in place — `HttpClient.send()`, `RobotsPolicy.allowed()`,
`HtmlDocument.final_url`, `ArticleCrawlService`'s profile check — and
adds only a bounded loop and one narrow exception type.

## Consequences

### Positive

- Closes a concrete blocker to real production crawling of all three
  active sources; shortlinks, AMP pages, and moved articles now resolve
  instead of hard-failing.
- Robots.txt is honored for every hop a redirect chain visits, not only
  the first — a strengthening of this project's compliance posture, not
  merely a preservation of it.
- No new runtime dependency; reuses stdlib `urllib.parse.urljoin` and
  every existing HTTP/robots/application primitive unchanged.
- `ArticleCrawlService`'s existing profile-identity boundary check is
  finally exercised against a real, transport-produced `final_url`
  rather than only a fabricated one in tests.
- No new CLI exit code: `TooManyRedirectsError` subclasses `ResponseError`,
  already bucketed under ADR-023's existing crawl-domain-failure exit
  code, and `SourceBoundaryError` already maps there too.

### Negative

- A redirect chain now costs up to 5 sequential requests (and 5 robots
  checks, though `RobotsPolicy` already caches per origin) instead of
  one; a page behind a long redirect chain is slower to fetch than one
  that isn't.
- Intermediate hop hosts are not validated against the source registry
  (see "Residual risk, accepted" above) — an accepted trade-off, not an
  oversight, but a real one.
- `TooManyRedirectsError` is deliberately **not** added to
  `_RETRYABLE_EXCEPTIONS` (`src/aa_crawler/http/client.py`) — retrying a
  redirect loop would only repeat the same loop — so a genuine redirect
  loop always surfaces as a single terminal failure per crawl attempt,
  consistent with ADR-015's existing idempotent-retry scope.

### Neutral

- No change to `ArticleCrawlService`, `ApplicationRuntime`,
  `SourceRegistry`, `SourceProfile`, or any parser family.
- No change to the CLI's argument surface, output contract, or exit-code
  table; `ResponseError`/`TooManyRedirectsError` were already named
  examples of ADR-023's existing crawl-domain-failure bucket.
- `HttpClient`'s `httpx.Client` construction is unchanged
  (`follow_redirects` stays unset, i.e. `False`); all redirect logic
  lives in `HtmlFetcher`, not in the transport layer.

## Compatibility implications

Default behavior for a URL that never redirects is unchanged: one
request, one response, `final_url == requested_url`, identical
output. A URL that does redirect previously raised `ResponseError`
unconditionally; it now either resolves to its landing page (if within
the 5-hop cap and robots-allowed at every hop) or still raises an
error — `ResponseError` (no `Location` header, or non-3xx failure),
`TooManyRedirectsError` (cap exceeded), `HtmlDisallowedError` (robots
disallows an intermediate hop), or `SourceBoundaryError` (the final
profile differs from the requested one, raised one layer up in
`ArticleCrawlService`, unchanged). No existing passing invocation
changes behavior.

## Testing implications

- New `HtmlFetcher` unit tests (extending the existing fake-`HttpClient`
  sequence-of-responses idiom already used in
  `tests/html/test_fetcher.py`) covering: a single redirect hop
  resolving to a 2xx and producing the expected `final_url`; a relative
  `Location` header resolving correctly against the current hop's URL;
  a chain of exactly 5 hops succeeding; a 6th hop raising
  `TooManyRedirectsError`; a 3xx response with no `Location` header
  raising `ResponseError` as before; robots.txt disallowing an
  intermediate hop raising `HtmlDisallowedError` before that hop's
  request is even sent.
- Extend `tests/integration/test_application_article_crawl.py` and
  `tests/integration/test_cli_process_boundary.py` with at least one
  scenario driven through a real multi-hop `HtmlFetcher` chain (not only
  a fabricated `final_url`), confirming `SourceBoundaryError` still
  fires correctly when a redirect's real landing profile differs from
  the requested one.
- No test performs a live network acquisition; all HTTP responses remain
  synthetic, per this project's standing no-live-network-request testing
  constraint.

## Relationship to existing decisions

- ADR-023 (CLI Application Entry Point and Process Boundary): this is
  the follow-up ADR-023 itself named as a review trigger. Its exit-code
  table needs no new category — `ResponseError`, `TooManyRedirectsError`,
  and `SourceBoundaryError` all remain inside the existing
  crawl-domain-failure bucket it already documents.
- ADR-021 (Application-Level Article Crawl Orchestration): its own
  review trigger names "redirects" explicitly. `ArticleCrawlService`'s
  profile-identity check on `final_url` is unchanged; this ADR is what
  finally gives that check a real, transport-produced value to check.
- ADR-005 (Robots-Aware HTML Acquisition): this ADR extends, rather than
  weakens, that decision's robots-compliance guarantee to every redirect
  hop, not only the originally requested URL.
- ADR-003 (HTTPX as the Synchronous Transport Boundary) and ADR-015
  (Retry Idempotency): `HttpClient`'s `httpx.Client` construction and
  retry-eligible exception set are both unchanged; redirect handling
  lives entirely in `HtmlFetcher`, one layer above the transport.
- ADR-014 (User-Agent Ownership): unaffected — the same single, honest,
  non-rotating identity is used for every hop's request, since every
  request still flows through the same `HtmlFetcher`/`HttpClient`
  instances.
- ADR-020 (Declarative Source Architecture): the exact-host,
  no-wildcard governance model is preserved; this ADR does not give
  `html/` any awareness of `SourceProfile` or `SourceRegistry`, keeping
  that authority exactly where ADR-020 already placed it.

## Follow-up work

- Rate limiting and politeness delay between requests (Sprint 20, next
  in the locked MVP roadmap) is not addressed here; this ADR does not
  add any delay between redirect hops within a single fetch.
- Per-hop domain/source-registry validation during the chase (the
  rejected Option 3) is not adopted; revisit only if a future
  requirement genuinely needs it (see "Residual risk, accepted").
- The 5-hop cap is a fixed constant; making it configurable is not
  addressed here and is not currently motivated by any known
  requirement.
- The authorized live crawl smoke test (Sprint 22) is the first point
  at which this ADR's behavior will be exercised against a real
  redirecting site.

## Review triggers

A non-GET request method is ever introduced (requiring httpx's
redirect-driven method-rewriting semantics to be considered); a real
requirement emerges for per-hop domain validation during the chase
(for example, a remote/dynamic URL-list source removing the assumption
that entry URLs are pre-reviewed); or the 5-hop cap proves too small or
too generous against real observed redirect chains once live crawling
is authorized.
