# ADR-001 — Configuration Source Precedence and Explicit Dotenv Selection

- Status: Accepted
- Date: 2026-08-04
- Decision owners: Tech Lead, Configuration owner
- Related ADRs: ADR-002, ADR-010, ADR-013

## Context

Configuration must be deterministic across local development, tests, staging,
and production without import-time environment access or accidental discovery
of a developer's dotenv file.

## Decision drivers

- Deterministic precedence and test isolation
- Explicit production secret sources
- No global settings singleton
- Safe handling of unknown application variables

## Considered options

1. A module-level settings singleton.
2. Automatic parent-directory dotenv discovery.
3. OS environment variables only.
4. Explicit layered loading at the composition root.

## Decision

Load configuration once, from highest to lowest precedence: explicit overrides,
OS environment variables, one explicitly selected dotenv file, and model
defaults. No dotenv file is loaded when none is supplied, and parent directories
are never searched. Unknown `AA_` variables are rejected.

## Rationale

Explicit selection prevents local files from silently influencing production
and makes tests independent of process-global configuration discovery.

## Consequences

### Positive

- Predictable values and straightforward test overrides.
- Production never loads dotenv implicitly.

### Negative

- The loader must maintain the approved variable mapping.
- Callers must provide `base_dir` and any dotenv path explicitly.

### Neutral

- Deployment remains responsible for injecting production secrets.

## Compatibility implications

Changing source precedence or implicit-loading behavior is a breaking behavioral
change.

## Follow-up work

Keep the environment template and configuration documentation aligned.

## Review triggers

A secret manager, remote configuration service, or additional configuration
source is proposed.
