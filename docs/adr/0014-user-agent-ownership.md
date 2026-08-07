# ADR-014 — User-Agent Ownership

- Status: Accepted
- Date: 2026-08-04
- Decision owners: Robots owner, HTTP owner
- Related ADRs: ADR-005, ADR-008, ADR-010

## Context

At proposal time, `RobotsPolicy` and `HtmlFetcher` independently received
user-agent strings, and robots retrieval did not use the configured crawler
identity as its request header. That allowed robots evaluation, robots
retrieval, and page retrieval to identify the crawler differently.

The crawler needs one application-scoped identity that is safe to send over
HTTP, explicit in the composition graph, and independent of any source
implementation.

## Decision drivers

- Robots compliance
- Consistent crawler identity
- Explicit ownership and dependency injection
- Safe, honest identification without browser or third-party impersonation
- One source of truth across acquisition components
- Testable behavior without global mutable state

## Considered options

1. Preserve independent values.
2. Let `HtmlFetcher` own and pass identity.
3. Let `RobotsPolicy` own identity.
4. Inject one immutable request-identity value into both.
5. Apply a global default in `HttpClient`.

## Decision

Use one immutable `RequestIdentity` value as the authoritative
application-scoped identity for the acquisition graph. The application
composition root owns its creation and injects it into `RobotsPolicy` and
`HtmlFetcher`.

`RequestIdentity` keeps product name, product version, canonical project URL,
and optional contact distinct. It formats the canonical User-Agent value and
validates the complete value before it can reach the network. Its default
identity is:

```text
AA-Crawler/<version> (+https://github.com/muhammadarifalfani/aa-crawler)
```

An approved contact may be represented as:

```text
AA-Crawler/<version> (+https://github.com/muhammadarifalfani/aa-crawler; contact=<contact>)
```

The product version is an explicit validated input. Runtime components must
not independently hardcode the application version. A future composition-root
integration will supply the canonical installed package version; automatic
package-metadata lookup is not part of the current implementation.

Identity validation requires HTTP-token-compatible product and version values,
public HTTPS project and contact URLs, no embedded credentials, query, or
fragment, no control characters, and no browser, search-engine, or third-party
crawler impersonation. The formatted User-Agent is limited to 256 characters.
The value object is frozen and immutable.

`RobotsPolicy` receives `RequestIdentity`, exposes it through a read-only
property, and uses `identity.user_agent` for both robots.txt retrieval and
`RobotFileParser.can_fetch(...)`. Its cache remains scoped to the policy
instance and origin.

`HtmlFetcher` receives `RequestIdentity`, verifies compatibility with its
`RobotsPolicy` during construction, and rejects a mismatch before network
execution. It preserves robots-first ordering and uses `identity.user_agent`
for page retrieval.

`HttpClient` remains identity-neutral. It neither owns nor mutates User-Agent
policy; it sends the transport-neutral headers supplied in `CrawlerRequest`.
No global mutable identity, user-agent rotation, or raw `user_agent`
compatibility path is approved.

## Rationale

Independent values create correctness and compliance risk. Constructor
injection makes ownership visible, keeps the transport layer generic, and
allows robots retrieval, robots evaluation, and page retrieval to use the same
validated identity. An immutable value prevents accidental mutation after the
acquisition graph has been composed.

## Implementation status

Implemented in Sprint 4 as `RequestIdentity`.

- `RobotsPolicy` receives the immutable identity value.
- `HtmlFetcher` receives the immutable identity value.
- Robots retrieval and robots evaluation use `identity.user_agent`.
- Page retrieval uses `identity.user_agent`.
- Raw component-owned `user_agent` constructor parameters were removed from
  the migrated acquisition components.
- `HtmlFetcher` rejects an identity mismatch with its `RobotsPolicy` before
  network execution.
- `HttpClient` remains identity-neutral.
- Focused tests cover validation, propagation, and mismatch prevention.

## Consequences

### Positive

- Robots and page acquisition present one consistent crawler identity.
- Identity validation occurs before network execution.
- Components receive an explicit, immutable, testable dependency.
- Transport concerns remain separate from application identity policy.

### Negative

- Acquisition constructors require an additional dependency.
- Callers must compose matching identity values deliberately.
- The composition root must eventually resolve the installed product version.

### Neutral

- Source-specific behavior does not own crawler identity.
- An operational contact remains optional until a deployment policy approves
  one.
- User-agent rotation remains outside the supported architecture.

## Compatibility implications

The Sprint 4 migration intentionally changed the public constructors of
`RobotsPolicy` and `HtmlFetcher`. Callers must now provide `RequestIdentity`;
the former raw `user_agent` constructor ownership is not retained as a
compatibility shim. `HttpClient` remains unchanged and identity-neutral.

## Migration

Completed in Sprint 4:

- Introduced `RequestIdentity` as the immutable application-scoped value.
- Migrated `RobotsPolicy` and `HtmlFetcher` to constructor injection.
- Added focused propagation and mismatch-prevention tests.
- Removed raw component-owned `user_agent` parameters from migrated
  acquisition components.

Still future:

- A CLI identity override, if explicitly approved.
- Composition-root lookup and injection of the installed package version.
- An operational contact policy.
- Identity serialization required by a future async or distributed execution
  family.

## Follow-up work

- Supply the canonical installed package version from the application
  composition root.
- Define operational contact ownership before one is enabled in production.
- Review any future CLI override against the validation and propagation
  invariants in this ADR.

## Review triggers

- A user-agent rotation feature is proposed.
- A CLI or deployment-specific identity override is introduced.
- Browser automation requires a distinct honest identity policy.
- Async or distributed execution requires identity serialization.
- Operational contact requirements change.
