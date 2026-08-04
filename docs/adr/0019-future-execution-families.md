# ADR-019 — Future Execution Families and Dependency Isolation

- Status: Proposed
- Date: 2026-08-04
- Decision owners: Tech Lead, Dependency owner
- Related ADRs: ADR-003, ADR-005, ADR-011, ADR-017

## Context

Current APIs are synchronous and HTTP/HTML-oriented. Async execution and browser
automation have materially different lifecycles, artifacts, and dependency
footprints.

## Decision drivers

- Preserve synchronous API clarity
- Avoid universal but misleading abstractions
- Keep the core environment small
- Isolate browser binaries and platform SDKs

## Considered options

1. Add async methods to current classes.
2. Make every interface dual synchronous/asynchronous.
3. Hide browser automation behind `HttpClient`.
4. Create separate execution and acquisition families.
5. Install all platform and browser dependencies in core.

## Decision

Propose separate architecture families for materially different runtimes. Reuse
neutral domain contracts where appropriate, but do not stretch synchronous APIs
into universal interfaces. Browser and platform dependencies should be optional,
plugin-owned, or separately deployable rather than unconditional core packages.

## Rationale

Separate families preserve honest lifecycle and resource semantics while
containing supply-chain and installation cost.

## Consequences

### Positive

- Small core installation and independently evolvable runtimes.

### Negative

- Some parallel interfaces and explicit runtime selection may be required.

### Neutral

- No async or browser library is selected by this proposal.

## Compatibility implications

Current synchronous APIs remain valid without promising universal substitution.

## Follow-up work

Accept or revise this ADR only when an alternate runtime is scheduled.

## Review triggers

JavaScript-rendered targets, async throughput requirements, or public plugins.
