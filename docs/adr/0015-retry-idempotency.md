# ADR-015 — Retry Idempotency

- Status: Accepted
- Date: 2026-08-04
- Decision owners: HTTP owner
- Related ADRs: ADR-003, ADR-004, ADR-005

## Context

At proposal time, retry decisions used transient exceptions and statuses
without accounting for whether repeating the HTTP method was safe. The
GET-oriented framework needed an explicit boundary before supporting other
methods, because a transport failure cannot establish whether repeating an
application-level operation is safe.

## Decision drivers

- Prevent duplicated mutations
- Predictable client behavior
- Explicit HTTP-layer ownership
- Safe support for valid non-GET requests
- Deterministic, testable retry behavior

## Considered options

1. Retry every method.
2. Retry only GET and HEAD.
3. Retry recognized idempotent methods.
4. Require an explicit idempotency declaration or key.
5. Disable retries for requests with bodies.

## Decision

`RetryPolicy` owns automatic retry eligibility. Only `GET` and `HEAD` are
automatically retryable. `RetryPolicy.is_method_retryable(...)` performs a
case-insensitive comparison against a fixed immutable method set that callers
cannot broaden.

`POST`, `PUT`, `PATCH`, `DELETE`, `OPTIONS`, `TRACE`, `CONNECT`, and unknown or
extension methods remain valid requests, but they are not automatically
retried. One logical `CrawlerRequest` therefore maps to:

- exactly one physical transport attempt for a non-eligible method; or
- one or more bounded physical attempts for an eligible `GET` or `HEAD`, as
  controlled by `RetryPolicy`.

Retry eligibility must not be broadened by request metadata, source profiles,
parsers, crawler-layer configuration, body emptiness, headers, response status
alone, or caller-supplied method collections. Retry policy remains an HTTP-layer
responsibility.

## Existing retry semantics

The accepted method rule operates with the existing synchronous retry
semantics:

- Default `max_attempts` is 3 and includes the initial attempt.
- Retryable statuses are `408`, `429`, `500`, `502`, `503`, and `504`.
- Retryable transient exceptions are HTTPX `ConnectError`, `ConnectTimeout`,
  `ReadTimeout`, `WriteTimeout`, `PoolTimeout`, and `RemoteProtocolError`.
- Backoff before attempt `n`, for `n >= 2`, is
  `backoff_base * 2 ** (n - 2)`, capped by `backoff_max`.
- Default `backoff_base` is 0.5 seconds and default `backoff_max` is 8 seconds.
- No delay occurs before the initial attempt.
- Backoff has no jitter.
- `Retry-After` is not interpreted.
- The `HttpClient` reuses its configured `TimeoutPolicy` for every physical
  attempt.
- A fresh HTTPX request is rebuilt from the same immutable `CrawlerRequest` for
  every eligible attempt.
- A retryable response is closed before the next attempt.
- Exhausted retryable statuses raise `ResponseError`.
- Exhausted retryable transport failures are translated to `RequestError` with
  exception chaining preserved.
- Other HTTPX failures are translated immediately and are not retried.

For a non-eligible method, a configured retryable status or transient failure
does not authorize another attempt. The existing final status or error handling
still applies after that single attempt.

## Acquisition interaction

`HtmlFetcher` page retrieval and `RobotsPolicy` robots.txt retrieval construct
`CrawlerRequest` values with the default `GET` method, so they remain eligible
for bounded HTTP retries. This decision does not move robots policy or HTML
acquisition policy into the HTTP layer; it governs only physical transport
attempts made by `HttpClient`.

## Rationale

GET and HEAD are the only methods the current acquisition architecture needs to
repeat automatically. A fixed narrow set avoids accidental mutation retries
while allowing every other method to remain a valid single-attempt request.
Keeping the rule in `RetryPolicy` makes eligibility explicit and prevents
domain metadata or higher layers from becoming hidden transport controls.

## Implementation status

Implemented in Sprint 4.

- `RetryPolicy` declares the fixed immutable `GET` and `HEAD` set.
- `RetryPolicy.is_method_retryable(...)` normalizes method comparison.
- `HttpClient` enforces the eligible attempt limit before transport execution.
- Non-eligible methods receive exactly one physical attempt.
- Existing status, exception, timeout, request rebuilding, response closing,
  backoff, translation, and chaining behavior remains in place.
- Focused `RetryPolicy` and `HttpClient` tests cover eligible and non-eligible
  methods, including metadata that attempts to request retries.

## Consequences

### Positive

- Mutation-capable and unknown methods cannot be retried automatically by
  accident.
- GET and HEAD retain bounded recovery from approved transient failures.
- Retry ownership and request-count behavior are explicit and testable.

### Negative

- Operations that could be retried safely with an idempotency key still receive
  only one attempt.
- Expanding eligibility requires a new architecture review rather than caller
  configuration.

### Neutral

- Jitter, `Retry-After`, rate limiting, circuit breaking, and distributed retry
  coordination remain separate decisions.
- The rule governs synchronous physical attempts, not business-operation
  idempotency.

## Compatibility implications

Retry eligibility is observable through physical request counts. Callers may
rely on `GET` and `HEAD` receiving bounded retries and on all other methods
receiving one physical attempt. Expanding this set would change transport
behavior and requires explicit compatibility review.

## Migration

Completed in Sprint 4:

- Added immutable method eligibility to `RetryPolicy`.
- Fixed the eligible set to `GET` and `HEAD`.
- Enforced the rule in `HttpClient`.
- Added single-attempt behavior for all other methods.
- Added focused policy and client tests and repository verification.

Still future review areas, not committed roadmap items:

- `Retry-After` support
- Jitter
- An overall logical-operation deadline
- Rate limiting and circuit breaking
- Idempotency-key semantics
- Distributed retry coordination
- Async retry semantics

## Follow-up work

No implementation follow-up is required for the accepted synchronous GET/HEAD
policy. Revisit the decision only when a review trigger occurs.

## Review triggers

- Acquisition introduces a method other than GET or HEAD.
- Idempotency-key semantics are proposed.
- Async execution or distributed workers are introduced.
- A source-specific transport policy is proposed.
- Rate limiting, circuit breaking, jitter, or `Retry-After` support is added.
