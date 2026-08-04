# ADR-007 — Lazy Parser Lifecycle and Output Validation

- Status: Accepted
- Date: 2026-08-04
- Decision owners: Parser owner
- Related ADRs: ADR-005, ADR-008, ADR-017

## Context

Platform parsers need a shared lifecycle that preserves item order and laziness
while preventing invalid values from crossing the parser boundary.

## Decision drivers

- Lazy production and ordered output
- Runtime enforcement of `CrawlerItem`
- Safe exception translation
- No silent coercion of parser defects

## Considered options

1. Require parsers to return complete lists.
2. Accept arbitrary mappings and coerce them.
3. Validate after full materialization.
4. Lazily validate each result from an abstract implementation method.

## Decision

Parser implementations define `parse_document()`. The framework `parse()`
method lazily iterates its results, requires every result to be a `CrawlerItem`,
propagates parser errors, and chains unexpected failures as execution errors.

## Rationale

This gives implementations flexibility while enforcing one framework output
contract at the boundary.

## Consequences

### Positive

- Ordered lazy output and early contract failure.
- Invocation and iteration failures share one safe boundary.

### Negative

- Failures may occur only when the iterator is consumed.
- The current parser input is HTML-specific.

### Neutral

- No DOM library is selected.

## Compatibility implications

Lazy timing and output validation are compatibility-sensitive.

## Follow-up work

Validate naming and ergonomics with the first platform parser.

## Review triggers

Non-HTML parsing, async parsing, batch results, or typed item schemas.
