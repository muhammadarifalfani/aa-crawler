# ADR-033 — Per-Host Politeness Delay

- Status: Accepted
- Date: 2026-10-10
- Decision owners: HTTP owner, Application owner, Tech Lead
- Related ADRs: ADR-003, ADR-005, ADR-014, ADR-015, ADR-020, ADR-022, ADR-029, ADR-032

## Context

Sprint 20 is the second of four sprints in the locked MVP-completion
roadmap. The investigation that motivated Sprint 19 found that nothing in
the acquisition path limits how fast requests are sent to a real site.
Reading the code confirms it:

- `HttpClient.send()` (`src/aa_crawler/http/client.py`) sleeps only for
  retry backoff (`RetryPolicy.backoff_seconds`, 0.5 seconds base), which
  applies only after a failed attempt and never between two normal
  successful requests.
- `cli/batch.py` (`_run_one_pass`) crawls every URL in a list back to
  back; its only wait (`sleep(interval)`) happens between full passes.
  `cli/scheduler.py` has the same shape for a single URL.
- A retry on HTTP 429 ("too many requests") is currently delayed by only
  0.5 seconds, which is the opposite of what a site sending that signal
  is asking for. `Retry-After` is not read (ADR-015 lists it, together
  with rate limiting, as a deliberately unaddressed future review area).
- ADR-020 and the engineering standards both state that enabling a
  source does not replace operational rate limits, and README.md lists
  "no rate limiting" as the first of the two gaps that make the MVP
  not yet safe to run against a real site.

Every real network request already flows through one place:
`HttpClient.send()`. That includes article pages, `robots.txt` fetches
made by `RobotsPolicy`, every redirect hop added by ADR-032, and retry
attempts. A delay placed anywhere above that point (the CLI loops, for
example) would miss at least some of those paths.

## Decision drivers

- Prevent a real publisher from seeing a burst of requests from this
  crawler, for the single-URL, batch, and scheduled modes alike, without
  each mode having to remember to add its own delay.
- Cover every kind of physical request: pages, `robots.txt`, redirect
  hops, and retries, since a site cannot tell them apart.
- Keep `html/`, `robots/`, and `sources/` unaware of rate limiting, so
  ADR-020's source-agnostic layering and ADR-022's explicit composition
  ownership are preserved.
- Keep tests fast, deterministic, and free of real waiting and real
  network access, reusing the existing `_sleep` monkeypatch idiom.
- Introduce no new runtime dependency, no new CLI argument, and no new
  exit code.
- Avoid a circular dependency: `RobotsPolicy` already depends on
  `HttpClient`, so `HttpClient` must not depend on `RobotsPolicy`.

## Considered options

1. Add a per-URL delay inside the CLI loops (`cli/batch.py`,
   `cli/scheduler.py`).
2. Add a per-host minimum interval inside `HttpClient.send()`, driven by
   a new immutable `RateLimitPolicy`, with an injectable clock and the
   existing `_sleep` seam.
3. Add a per-source delay declared on `SourceProfile` and enforced above
   `HttpClient`, optionally honoring `Crawl-delay` from `robots.txt`.

## Decision

Adopt Option 2.

A new frozen dataclass `RateLimitPolicy` is added to
`src/aa_crawler/http/policies.py`, alongside `TimeoutPolicy` and
`RetryPolicy`, with one field, `min_interval_seconds`. It is validated
the same way the existing policies are (a number, not a boolean, and
non-negative). A value of `0` means no limiting.

`HttpClient` gains an optional `rate_limit_policy` argument and an
optional injectable `clock` argument, defaulting to `time.monotonic`.
Inside `send()`, before every physical attempt (the first attempt and
each retry), the client resolves the request URL's lowercase hostname and
waits until at least `min_interval_seconds` have passed since the last
request to that same host finished. The wait uses the existing module
level `_sleep` function, so tests substitute it exactly as they already
do for retry backoff. The client records the host's timestamp after each
attempt ends, whether it returned a response or raised, so a failed
attempt still counts as having touched the host. A request whose URL has
no resolvable hostname is not limited; URL validity remains the
responsibility of the layers above, as it is today.

The wait is measured from the end of the previous request to that host
to the start of the next one, and it is computed from the clock rather
than added on top of retry backoff. When a retry backoff has already
consumed part of the interval, only the remainder is waited, so the total
delay before a retry is the larger of the two values and not their sum.

The default value of `RateLimitPolicy` is `0` (no limiting), so an
`HttpClient` constructed directly keeps its exact current behavior. The
production value is supplied by composition:
`create_application_runtime()` in `application/runtime.py` passes
`RateLimitPolicy(min_interval_seconds=2.0)`, mirroring how that function
already constructs and passes the timeout and retry policies. This 2.0
second figure is an immutable, ADR-documented policy default, which the
engineering standards allow in source code when an ADR records its
ownership; it is not environment configuration and no CLI argument or
configuration field is added.

Option 1 is rejected because it would cover only the CLI batch and
scheduler paths, would miss `robots.txt` fetches, redirect hops, and any
future caller of `ArticleCrawlService` that is not the CLI, and would
put a transport-safety control in the layer that owns process
orchestration. Option 3 is rejected for this sprint because per-source
delay on `SourceProfile` pushes rate awareness into the declarative
source layer, and honoring `Crawl-delay` would need `HttpClient` to know
about robots rules, which inverts the existing dependency direction
(`RobotsPolicy` depends on `HttpClient`). Both remain possible later as
additive refinements (see Follow-up work).

### Scope

Limiting is keyed by exact hostname, mirroring ADR-020's exact-host
model. The client is synchronous and single-threaded (ADR-003), so the
per-host timestamp table needs no locking. The table lives on the
`HttpClient` instance, so it is shared by every pass of a scheduled run
(ADR-028, ADR-029), which reuses one `ApplicationRuntime` for the whole
process. A new process starts with an empty table, so the first request
to a host is never delayed.

### Residual risks, accepted

- Different hostnames are limited independently. Two subdomains of one
  publisher (for example, two `detik.com` hosts) do not share a delay.
  Because the crawler is sequential and each request takes real time, the
  practical effect is small, and grouping hosts by registrable domain
  would need a public-suffix dataset, which is a new dependency.
- `Crawl-delay` from `robots.txt` is not honored, so a site that asks for
  a delay longer than 2.0 seconds would still see 2.0 seconds. Real
  `robots.txt` values for the three active sources are unknown until the
  authorized live smoke test in Sprint 22.
- `Retry-After` is still ignored. The 2.0 second floor makes a 429 retry
  at least that slow, but a site requesting a longer pause is not obeyed.
- There is no circuit breaker: a site that keeps returning errors is
  still retried up to `RetryPolicy.max_attempts` per request.
- The interval is not user-adjustable at runtime. Changing it means
  changing the composed default in code until a configuration surface is
  separately approved.

## Rationale

`HttpClient.send()` is the one choke point every physical request must
pass through, so a delay enforced there cannot be bypassed by a new code
path, a redirect hop, or a `robots.txt` fetch. Making the policy an
immutable dataclass with a disabled default, and giving composition the
responsibility of choosing the production value, keeps every existing
direct `HttpClient` user and test untouched while making the real
application polite by default. Injecting the clock and reusing `_sleep`
keeps tests deterministic and fast with no real waiting.

## Consequences

### Positive

- The crawler can no longer send a burst of back-to-back requests to one
  host in single-URL, batch, or scheduled mode.
- `robots.txt` fetches, redirect hops, and retries are covered
  automatically, with no change to `HtmlFetcher`, `RobotsPolicy`, or the
  CLI loops.
- No new runtime dependency, no new CLI argument, no new exit code, and
  no change to `ArticleCrawlService`, `SourceRegistry`, or any parser.
- Retries after a 429 or 5xx response are now slowed to at least the
  politeness interval, instead of 0.5 seconds.

### Negative

- Throughput is capped at roughly one request per two seconds per host.
  A first fetch of an unseen origin takes at least two `HttpClient`
  requests (`robots.txt`, then the page), so at least two seconds pass
  between them. A redirect chain of N hops takes correspondingly longer.
  This is intended, and acceptable at MVP scale.
- The clock and sleep functions are one more seam inside `HttpClient`
  that must stay deterministic in tests.
- The production interval lives in code, not configuration, so changing
  it is a code change.

### Neutral

- Direct `HttpClient()` construction, every existing test double, and
  every existing integration test keep their current behavior because the
  policy default is `0`.
- `HttpClient`'s `follow_redirects` setting, retry eligibility, and
  exception translation are unchanged.
- The interval waits between passes in `cli/batch.py` and
  `cli/scheduler.py` are unchanged and independent of this delay.

## Compatibility implications

An `HttpClient` constructed without a `rate_limit_policy` behaves exactly
as before. Through the CLI and `create_application_runtime()`, the
observable change is wall-clock time only: successive requests to the
same host are spaced by at least 2.0 seconds. Request contents, response
handling, output, persistence, logging contract, and exit codes are all
unchanged. No existing passing invocation changes its result.

## Testing implications

- New `RateLimitPolicy` unit tests in the existing policies test module:
  default is `0`, accepts `0` and positive numbers (integers and floats),
  rejects negative values, booleans, and non-numbers.
- New `HttpClient` unit tests in `tests/http/test_client.py`, using the
  existing `httpx.MockTransport` idiom, a fake clock, and a monkeypatched
  `_sleep`: no wait on the first request to a host; a wait equal to the
  remaining interval on a second request to the same host; no wait once
  the interval has already elapsed; independent timing for two different
  hosts; a failed attempt still updating the host's timestamp; a retry
  waiting only for the remainder after backoff (the larger of the two,
  not their sum); a disabled policy (`0`) never sleeping; a URL without a
  hostname not being limited.
- A composition test in `tests/application/test_runtime.py` confirming
  `create_application_runtime()` wires the 2.0 second production policy
  into its `HttpClient`.
- No test performs real waiting or any live network acquisition; all
  clocks, sleeps, and HTTP responses are synthetic, per this project's
  standing no-live-network-request testing constraint.

## Relationship to existing decisions

- ADR-003 (HTTPX as the Synchronous Transport Boundary): the delay lives
  inside the transport boundary this ADR defines and relies on its
  synchronous, single-threaded model.
- ADR-015 (Retry Idempotency): this ADR addresses the "rate limiting"
  item that ADR-015 listed as a future review area. Jitter,
  `Retry-After`, circuit breaking, and an overall logical-operation
  deadline remain unaddressed.
- ADR-005 (Robots-Aware HTML Acquisition) and ADR-032 (Bounded Redirect
  Following): `robots.txt` fetches and redirect hops are physical
  requests and are throttled by the same mechanism without either layer
  changing.
- ADR-014 (User-Agent Ownership): unaffected; politeness is orthogonal to
  identity.
- ADR-020 (Declarative Source Architecture) and ADR-022 (Application
  Runtime Composition): `html/`, `robots/`, and `sources/` stay
  rate-agnostic, and the production value is chosen in composition, the
  layer ADR-022 designates for wiring policies.
- ADR-028 and ADR-029 (scheduled and batch CLI modes): both reuse one
  runtime, so the per-host table persists across passes without any CLI
  change.

## Follow-up work

- Honoring `Crawl-delay` from `robots.txt`, `Retry-After` support, and a
  circuit breaker are not addressed here. The authorized live smoke test
  (Sprint 22) is the first opportunity to observe what the three active
  sources actually publish.
- A per-source delay override on `SourceProfile`, if real sources need
  different intervals, would be a separate decision.
- A configuration or CLI surface for adjusting the interval is not
  addressed here and is not currently motivated by a known requirement.
- Health and liveness signaling (Sprint 21) and the authorized live crawl
  smoke test (Sprint 22) follow in the locked roadmap.

## Review triggers

A source's `robots.txt` publishes a `Crawl-delay` longer than the
configured interval; a real site rate-limits or blocks the crawler at
this interval; concurrent per-URL crawling (async or threaded) is
introduced, which would require the per-host table to become
thread-safe; a requirement emerges to adjust the interval at runtime; or
a source needs a different delay from the others.
