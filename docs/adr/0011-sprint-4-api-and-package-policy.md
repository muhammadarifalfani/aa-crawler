# ADR-011 — Sprint 4 Public API and Package Policy

- Status: Accepted
- Date: 2026-08-04
- Decision owners: Tech Lead, API owners
- Related ADRs: ADR-008, ADR-010, ADR-017, ADR-018, ADR-019

## Context

Sprint 2 APIs are mature, while Sprint 3 crawler APIs have not yet been tested
by a real platform crawler. The physical `crawler` package also contains domain
contracts, runtime behavior, and composition.

## Decision drivers

- Protect mature behavior
- Avoid accidental commitments in newly introduced APIs
- Permit evidence-driven refinement
- Avoid speculative restructuring

## Considered options

1. Freeze the complete API.
2. Keep every API provisional.
3. Partially freeze APIs by maturity.
4. Restructure crawler packages before platform work.

## Decision

Partially freeze the public API for Sprint 4. Freeze mature Sprint 2
configuration and primary observability APIs. Preserve crawler contract names
and broad meanings. Keep crawler fields, subclass seams, HTTP policies, and
physical crawler package boundaries provisional through the first platform
crawler. Do not perform a speculative crawler package restructure.

## Rationale

The policy balances compatibility discipline with the need to validate new
framework abstractions under real platform requirements.

## Consequences

### Positive

- Mature behavior is protected.
- Sprint 4 can refine provisional seams with evidence.

### Negative

- Public does not yet mean fully stable for every Sprint 3 symbol.

### Neutral

- The current conceptual package cycle remains temporarily accepted.

## Compatibility implications

Changes to provisional APIs still require review and migration notes; frozen
Sprint 2 behavior requires normal backward-compatibility handling.

## Follow-up work

Publish symbol stability guidance and review it after the first platform crawler.

## Review triggers

First platform crawler completion or external API adoption.
