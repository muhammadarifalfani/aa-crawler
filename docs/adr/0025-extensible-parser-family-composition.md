# ADR-025 — Extensible Parser-Family Composition Seam

- Status: Accepted
- Date: 2026-08-30
- Decision owners: Application owner, Parser owner, Tech Lead
- Related ADRs: ADR-002, ADR-007, ADR-008, ADR-010, ADR-011, ADR-014, ADR-017,
  ADR-018, ADR-019, ADR-020, ADR-021, ADR-023, ADR-024

## Context

`SourceProfile.supported_parser_families` is a `ClassVar[frozenset[str]]`
frozen to exactly `{"jsonld_article"}`, and `ParserComposer.create()`
unconditionally rejects any other `parser_family` value and any non-null
`adapter_key` ("source adapters are not supported"). ADR-020 deliberately
left both closed, stating that a reserved declarative key "does not justify
a loader, registry, or plugin API" and listing two explicit review triggers
for revisiting this: "a real publisher requires custom parser or adapter
behavior" and "multiple parser families are implemented."

The project owner's stated long-term goal is an engine that ingests online
news alongside Twitter/X, Instagram, TikTok, Facebook, YouTube, and Threads,
eventually running near real time. Sprint 7 Task 8.1 (read-only architecture
discovery) evaluated this goal against repository evidence and found that
none of these platforms can be represented by `jsonld_article`: their data
is platform-specific JSON, not JSON-LD embedded in an HTML news article.
This constitutes the "real evidence" ADR-020 required and fires both of its
listed review triggers.

Two additional architectural constraints surfaced during that discovery and
bound this decision:

- `HtmlFetcher._content_type()` currently accepts only `text/html` and
  `application/xhtml+xml`; every other `Content-Type` is rejected before any
  parser ever runs. Real acquisition of non-HTML content (for example, a
  platform's JSON API response) is not possible today regardless of parser
  changes.
- No credential or authentication mechanism exists for outbound requests.
  `RequestIdentity` (ADR-014) carries only a validated User-Agent; there is
  no API-key, bearer-token, or OAuth support anywhere in `http/` or
  `identity/`.

This ADR builds only the internal parser-family composition mechanism. It
selects, authorizes, or implements no specific external source, platform, or
API — not Twitter/X, Instagram, TikTok, Facebook, YouTube, Threads, or any
other — and makes no legal, publisher-authorization, or terms-of-service
determination for any of them.

## Decision drivers

- Answer ADR-020's two fired review triggers without reopening its exact-host
  source-governance model
- Keep parser-family mapping closed, explicit, and reviewable: no dynamic
  plugin loading, no arbitrary import paths, entry points, reflection, or
  caller-provided factories, matching ADR-010/ADR-011/ADR-020's existing
  discipline
- Preserve `CrawlerItem`/`ArticleItem`'s current JSON-safe output shape so
  ADR-023's CLI stdout contract and ADR-024's persistence serialization
  remain valid without any change to either
- Keep `adapter_key` conceptually distinct from parser-family selection
  rather than conflating two different extension concerns
- Avoid premature commitment to any specific external platform, credential
  mechanism, or acquisition-layer content-type change

## Considered options

### Activate `adapter_key` as the extension mechanism

Rejected. ADR-020 reserved `adapter_key` for source-specific customization
*within* an existing parser family (for example, a publisher's non-standard
JSON-LD quirk), not for a wholesale different content format. Using it to
select between fundamentally different platforms would conflate two
distinct concerns under one seam.

### A dynamic plugin or entry-point system for parser families

Rejected. This directly contradicts ADR-010, ADR-011, and ADR-020's existing,
explicit prohibition on dynamic import paths, entry points, plugin scanning,
and caller-provided factories. Nothing observed in this discovery justifies
overturning that discipline.

### A parallel, platform-specific orchestration service per source

Rejected. This would duplicate ADR-021's `ArticleCrawlService` orchestration
per platform, multiplying maintenance surface and abandoning the single
reviewed crawl sequence that ADR-021 and ADR-022 already established.

### Also generalize `HtmlFetcher` to accept non-HTML content types now

Rejected for this ADR. No parser family requiring non-HTML acquisition is
implemented yet, and no platform is approved. Expanding the acquisition
content-type boundary is a separate, larger decision belonging to a future
ADR reviewing ADR-005's scope, once a real candidate needs it.

### Also design a credential/authentication mechanism now

Rejected for this ADR. No concrete API target is approved, so no credential
shape (API key, bearer token, OAuth flow) can yet be evaluated against a
real requirement. This remains explicit future work.

### Generalize `SourceProfile` and `ParserComposer` to a small, static, closed
### set of parser families (chosen)

`SourceProfile.supported_parser_families` may list more than one literal
family name, each added only through a reviewed code change.
`ParserComposer.create()` dispatches through a small, static, explicit
mapping from each supported `parser_family` name to its concrete parser
class — never a dynamic lookup, import path, or plugin registration. This
answers both of ADR-020's fired triggers while preserving every constraint
above.

## Decision

### Parser-family extensibility

`SourceProfile.supported_parser_families` becomes a closed, explicit,
reviewable set that may contain more than the single `jsonld_article` value.
Each new family name requires, in the same reviewed change: an addition to
that constant, a new concrete `BaseParser` subclass, and a new explicit
branch in `ParserComposer.create()`'s dispatch. No family may be added
through configuration, environment variables, or any runtime mechanism.

### `ParserComposer` dispatch

`ParserComposer.create()` continues to reject disabled profiles before
inspecting `parser_family`, exactly as ADR-020 defined. For enabled
profiles, it dispatches to the concrete parser class matching
`parser_family` through a small, static, explicit table or equivalent
branching — never reflection, entry points, or a caller-supplied factory —
and continues to raise `ParserCompositionError` for any unrecognized family.
The exact dispatch data structure is left to Task 8.3's implementation; the
constraint is that it remains static and fully reviewable in source control.

### `adapter_key` remains reserved and inert

This ADR does not activate `adapter_key`. It remains exactly as ADR-020
defined: validated as data by `SourceProfile`, unconditionally rejected by
`ParserComposer.create()` when non-null. Per-publisher customization within
one parser family (the seam's original motivating case) remains separate,
unapproved future work, distinct from cross-format parser-family selection.

### Output-contract constraint for any family added under this ADR

Any parser family introduced as a direct consequence of this ADR (including
Task 8.3's proof-of-concept family) must produce the same JSON-safe
`ArticleItem`/`CrawlerItem` output shape the `jsonld_article` family already
produces. A parser family with a genuinely different output shape (for
example, a tweet-, video-, or post-shaped contract) is explicitly out of
scope here and requires its own future decision, since it would also affect
ADR-023's CLI stdout contract and ADR-024's persistence serialization.

### Acquisition-layer boundary unchanged

`HtmlFetcher`'s content-type gate (`text/html`, `application/xhtml+xml`
only) is not changed by this ADR. Task 8.3's proof-of-concept parser family
must be exercised through synthetic, in-test `HtmlDocument` fixtures only —
never through real network acquisition of a new content type. Real
acquisition of non-HTML content requires its own separate architecture
review of `HtmlFetcher`/ADR-005's scope.

### No credential or authentication mechanism

This ADR introduces no API-key, bearer-token, or OAuth mechanism.
`RequestIdentity` remains User-Agent-only. Any real external platform
integration requiring authenticated API access is out of scope and requires
its own future review.

### No platform selected

This ADR selects, authorizes, or implements no specific external source. It
defines only the internal mechanism that would let a future, separately
reviewed and separately approved source use a parser family other than
`jsonld_article`.

## Rationale

The project owner's stated goal is real evidence that ADR-020's closed,
single-family design has reached its limit — but the honest architectural
gap is narrower than "support social media": it is specifically "support
more than one parser family through a still-closed, still-reviewable
mechanism." Generalizing `SourceProfile` and `ParserComposer` to a small,
static, explicit dispatch answers exactly that gap without disturbing
`SourceRegistry`'s exact-host governance, `ArticleCrawlService`'s
orchestration, `ApplicationRuntime`'s resource graph, the CLI's stdout
contract, or the persistence boundary's serialization contract — and
without prematurely committing to any specific platform, credential
mechanism, or acquisition-layer change that no current evidence justifies.

## Consequences

### Positive

- Parser-family selection is no longer hardcoded to a single value; a
  second, reviewed family can coexist with `jsonld_article`.
- Both of ADR-020's long-standing review triggers are answered.
- ADR-023's CLI stdout contract and ADR-024's persistence serialization
  remain valid unchanged, since output shape is preserved.
- No dynamic-loading or plugin risk is introduced; composition remains fully
  static and reviewable.

### Negative

- Each new parser family requires three synchronized, hand-written changes
  (the constant, the parser class, the dispatch branch); this does not scale
  to a large number of families without further review.
- Does not itself unblock real platform onboarding: non-HTML acquisition and
  credentialed API access remain separate, unresolved prerequisites.
- Task 8.3's proof-of-concept family adds code and test surface without
  shipping a user-facing capability on its own.

### Neutral

- `HtmlFetcher`, `SourceRegistry`, `ArticleCrawlService`, `ApplicationRuntime`,
  `aa_crawler.cli`, and `aa_crawler.persistence` are all unchanged.
- `adapter_key` remains exactly as reserved and inert as ADR-020 left it.
- ADR-016, ADR-017 (full portability policy), ADR-018, and ADR-019 statuses
  are unchanged.

## Compatibility implications

This ADR is additive only. `jsonld_article` behavior and output are
unchanged. Adding a parser family with a different output shape, activating
`adapter_key`, expanding `HtmlFetcher`'s accepted content types, or adding a
credential mechanism would each alter this accepted contract and requires
its own review.

## Testing implications

Implementation tests must verify: the existing `jsonld_article` composition
path is byte-for-byte unaffected; the new proof-of-concept family produces
the same JSON-safe `ArticleItem`/`CrawlerItem` output shape; a non-null
`adapter_key` is still unconditionally rejected; an unrecognized
`parser_family` value is still rejected with `ParserCompositionError`; and no
test contacts a real network, uses a real credential, or depends on
wall-clock state — synthetic `HtmlDocument` fixtures only.

## Relationship to existing decisions

- ADR-002, ADR-007, and ADR-008 remain authoritative; `BaseParser`'s lazy,
  validated lifecycle is unchanged, and any new parser family must still
  satisfy it.
- ADR-010 remains authoritative; parser-family dispatch stays explicit and
  static, never a service locator or dynamic registry.
- ADR-011 remains authoritative; parser and composition APIs remain
  provisional under its policy.
- ADR-014 remains authoritative; no credential or identity change is made.
- ADR-017 remains Deferred for its full portability policy; this ADR does
  not resolve it, and deliberately keeps any new family's output shape
  identical to avoid forcing that resolution now.
- ADR-018 and ADR-019 are unrelated and unchanged.
- ADR-020 remains authoritative for exact-host source governance and
  `SourceRegistry`; this ADR only extends its `parser_family`/composition
  seam and answers two of its review triggers.
- ADR-021 and ADR-022 remain authoritative; `ArticleCrawlService`'s sequence
  and `ApplicationRuntime`'s resource graph are unchanged.
- ADR-023 remains authoritative; the CLI's stdout contract remains valid
  because output shape is unchanged.
- ADR-024 remains authoritative; its own review trigger "a second parser
  family with a different output shape is introduced" is not fired by this
  ADR, since the output shape is deliberately preserved.

## Follow-up work

- Implement Task 8.3: generalize `SourceProfile.supported_parser_families`
  and `ParserComposer.create()` per this decision, and implement one
  synthetic, non-network proof-of-concept second parser family producing
  the same `ArticleItem`/`CrawlerItem` output shape.
- Add focused tests proving the existing `jsonld_article` path is unaffected
  and the new dispatch remains fully static and reviewable.
- Do not implement any real external platform, credential mechanism, or
  `HtmlFetcher` content-type change under this ADR; each requires its own
  future ADR.
- Align documentation only after implementation is verified, mirroring the
  Sprint 7 sequence.

## Review triggers

- A real external source or platform is proposed for implementation,
  requiring its own source-approval, legal, and acquisition/credential
  review.
- A parser family with a genuinely different output shape (not
  `ArticleItem`-compatible) is needed, requiring revisiting ADR-023's stdout
  contract and ADR-024's persistence serialization.
- Non-HTML content acquisition (for example, a JSON API response) is
  required, requiring revisiting `HtmlFetcher`/ADR-005's scope.
- Credentialed or authenticated outbound requests (API keys, OAuth) are
  required, requiring revisiting `RequestIdentity`/ADR-014's scope.
- Activating `adapter_key` for per-publisher customization within an
  existing family is proposed.
- More than a small handful of parser families are implemented, creating
  dispatch-table maintenance pressure that may justify a registry.
