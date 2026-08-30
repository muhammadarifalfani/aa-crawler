# ADR-026 — Microdata Article Parser Family

- Status: Accepted
- Date: 2026-08-30
- Decision owners: Application owner, Parser owner, Tech Lead
- Related ADRs: ADR-002, ADR-005, ADR-007, ADR-008, ADR-010, ADR-011,
  ADR-020, ADR-021, ADR-023, ADR-024, ADR-025

## Context

Sprint 8 (ADR-025) built a closed, statically-dispatched parser-family seam
and proved it with exactly one proof-of-concept family,
`generic_json_article`: a synthetic family parsing a flat JSON payload that
is, by construction, never reachable through real network acquisition,
since `HtmlFetcher` accepts only `text/html`/`application/xhtml+xml`
content types.

Sprint 9 Task 9.1 (read-only architecture discovery) re-verified ADR-025's
implementation directly against the repository — `SourceProfile.
supported_parser_families`, `ParserComposer.create()`'s dispatch, and an
independent `grep` confirming `aa_crawler.application`, `aa_crawler.cli`,
and `aa_crawler.persistence` contain zero references to parser-family
internals — and found the seam already fully isolates those layers from
parser-family details. What remained unproven was whether the seam holds
for a format that is also acquisition-compatible, not only a purely
synthetic one.

Task 9.1 selected Microdata (`schema.org` `NewsArticle`/`Article` expressed
through `itemscope`/`itemtype`/`itemprop` HTML attributes, as defined by the
WHATWG Microdata specification) as the smallest format that proves this:
unlike `generic_json_article`, Microdata remains `text/html`, so it is
reachable through the existing, unmodified `HtmlFetcher` boundary. It also
expresses the same schema.org vocabulary already modeled by `ArticleItem`
(`headline`, `datePublished`, `author`, `image`, `articleSection`,
`description`, `inLanguage`), so no new domain contract is required.

This ADR builds only the parser-family mechanism and one new concrete
parser. It does not enable any new real production source, does not change
acquisition or credential boundaries, and makes no legal or
publisher-authorization determination for any source.

## Decision drivers

- Prove ADR-025's parser-family seam with a format that is both genuinely
  different from `jsonld_article` and acquisition-compatible, not only
  synthetic
- Preserve `ArticleItem`/`CrawlerItem`'s existing JSON-safe output shape so
  ADR-023's CLI stdout contract and ADR-024's persistence serialization
  remain valid without any change to either
- Keep parser-family dispatch closed, static, and explicit, exactly as
  ADR-025 established
- Leave `HtmlFetcher`'s HTML-only acquisition boundary and the absence of
  any credential mechanism unchanged
- Avoid enabling a new real production source; that remains a separate
  project-owner governance decision
- Introduce no new third-party dependency

## Considered options

### A second synthetic JSON-based family, repeating Sprint 8's pattern

Rejected. This would not add evidence beyond what ADR-025 already proved.
Task 9.1 specifically sought a format that also demonstrates
real-acquisition compatibility, which a second synthetic JSON family would
not provide.

### An RSS/Atom feed-item representation

Rejected. RSS/Atom requires expanding `HtmlFetcher`'s content-type gate to
XML media types (`application/rss+xml`, `application/atom+xml`,
`text/xml`), which ADR-025 explicitly left as a separate, later decision
reviewing ADR-005's scope. RSS/Atom documents also typically enumerate
multiple articles per fetch, conflicting with the CLI's existing
"exactly one item" assumption (ADR-023) and requiring its own review to
avoid silently widening that contract.

### A content-sniffing or auto-detection layer choosing between families

Rejected. Task 9.1 confirmed format selection is already fully explicit and
deterministic at the `SourceProfile.parser_family` declaration; no
ambiguity exists to resolve. A detection layer would add an unrequested
responsibility and a new risk of non-deterministic or silently-wrong family
selection.

### Enabling a new real production source using the new family

Rejected for this ADR. Selecting a real publisher is a governance and legal
decision belonging to the project owner, not an architecture decision. This
ADR builds only the mechanism and leaves production enablement to a
separate, future decision — mirroring exactly how ADR-025 treated
`generic_json_article`.

### Combining with batch/multi-URL CLI input

Rejected. Batch input is a CLI/process-boundary concern (ADR-023's
territory) orthogonal to parser-family selection; combining the two would
mix unrelated architectural concerns in one decision.

### Microdata (`schema.org` `NewsArticle`/`Article`) as a third parser family (chosen)

Reuses the exact schema.org vocabulary already modeled by `ArticleItem`,
requires no acquisition-layer change (remains `text/html`), requires no new
domain contract, and is exercised through the same `BaseParser` lifecycle
the existing families already use.

## Decision

### Third parser family

`SourceProfile.supported_parser_families` gains a third literal value,
`microdata_article`, alongside `jsonld_article` and `generic_json_article`
— each addable only through a reviewed code change, exactly as ADR-025
requires. `ParserComposer.create()` gains one new explicit `elif` branch
dispatching to a new concrete parser, `MicrodataArticleParser`, following
the same static, closed dispatch discipline: never reflection, entry
points, or dynamic lookup. The existing `jsonld_article` and
`generic_json_article` branches and their `ParserCompositionError` messages
remain unchanged.

### `MicrodataArticleParser` scope

Parses one article's `schema.org` `NewsArticle`/`Article` Microdata
(`itemscope`, `itemtype`, `itemprop` attributes) directly from
`HtmlDocument.content` — a genuine HTML markup convention, distinct from
`JsonLdArticleParser`'s `<script type="application/ld+json">` extraction,
but expressing the same underlying vocabulary. It must produce the
identical JSON-safe `ArticleItem`/`CrawlerItem` output shape already
produced by both existing families, so ADR-023's CLI stdout contract and
ADR-024's persistence serialization remain valid without any change to
either.

Supported Microdata properties, mapped onto `ArticleItem`'s existing
fields: `headline`, `datePublished` → `published_at`, `dateModified` →
`modified_at`, `description`, `author` → `author_names`, `image` →
`lead_image_url`, `articleSection` → `section`, `inLanguage` → `language`.
Canonical-URL identity resolution and exact-host validation follow the same
approach `JsonLdArticleParser` already uses (`mainEntityOfPage`/`url`
identity, validated against the profile's approved exact hosts).

### Acquisition boundary unchanged

`HtmlFetcher`'s content-type gate (`text/html`, `application/xhtml+xml`
only) is not changed by this ADR. `MicrodataArticleParser` is reachable
through this existing boundary without modification, since Microdata is
itself `text/html` content — this is what distinguishes it from
`generic_json_article`. This ADR does not itself authorize or require any
live-network exercise of this family; Task 9.4's implementation and its
tests remain synthetic and network-isolated per the repository's existing
testing discipline.

### No new production source

No entry in `DEFAULT_SOURCE_PROFILES` uses `microdata_article` under this
ADR. Selecting a real publisher requiring Microdata remains a separate,
project-owner governance decision, exactly as `generic_json_article`
was left unused by any production profile under ADR-025.

### No credential, acquisition, or detection changes

This ADR introduces no format-detection or auto-selection mechanism, no
credential or authentication mechanism, and no acquisition-layer change.
`adapter_key` remains exactly as ADR-020/ADR-025 left it: reserved, inert,
and unconditionally rejected regardless of `parser_family`.

### No new dependency

`MicrodataArticleParser` uses only the standard library, reusing the same
`html.parser.HTMLParser`-based attribute-scanning approach
`JsonLdArticleParser` already uses (via `handle_starttag`), applied to
`itemscope`/`itemtype`/`itemprop` attributes instead of JSON-LD script
blocks.

### Non-goals

This ADR does not implement social-media ingestion, batch/multi-URL CLI
input, a format-detection layer, an acquisition-layer content-type change,
a credential/authentication mechanism, or a new domain contract.

## Rationale

Task 9.1 found ADR-025's seam already isolates `application`, `cli`, and
`persistence` from parser-family details, but had only been proven with a
purely synthetic family. Microdata closes that gap: it is a real,
still-used web-publishing convention, expresses the same vocabulary
`ArticleItem` already models, requires zero acquisition-layer change since
it remains `text/html`, and requires no new dependency, since the
repository's existing stdlib `HTMLParser`-based approach already generalizes
to attribute scanning. This proves the multi-format architecture with a
format capable of real acquisition, without prematurely committing to a
real publisher, a new contract, or any of the larger, unresolved
prerequisites (non-HTML acquisition, credentialed access) that a third
platform or social-media ingestion would require.

## Consequences

### Positive

- The parser-family seam is now proven with a genuinely acquisition-
  compatible format, not only a synthetic one.
- `ArticleItem`/`CrawlerItem`'s output shape, the CLI stdout contract, and
  the persistence serialization all remain valid unchanged.
- No dynamic-loading or plugin risk is introduced; dispatch remains fully
  static and reviewable.
- No new dependency, acquisition change, or credential mechanism is
  required.

### Negative

- A third parser family adds one more hand-synchronized set of changes
  (the supported-families constant, the parser class, the dispatch
  branch); this continues ADR-025's noted scaling concern.
- `MicrodataArticleParser` adds code and test surface without shipping a
  user-facing capability on its own, since no production source uses it.
- Microdata's `itemprop`/`itemscope` parsing introduces its own edge cases
  (nested `itemscope` values, multiple `itemprop` values per element) that
  require careful, narrowly-scoped handling distinct from JSON-LD's.

### Neutral

- `HtmlFetcher`, `SourceRegistry`, `ArticleCrawlService`, `ApplicationRuntime`,
  `aa_crawler.cli`, and `aa_crawler.persistence` are all unchanged.
- `adapter_key` remains exactly as reserved and inert as ADR-020/ADR-025
  left it.
- `generic_json_article`'s status and scope are unchanged by this ADR.
- ADR-016, ADR-017 (full portability policy), ADR-018, and ADR-019 statuses
  are unchanged.

## Compatibility implications

This ADR is additive only. `jsonld_article` and `generic_json_article`
behavior and output are unchanged. Enabling a real production source with
`microdata_article`, expanding `HtmlFetcher`'s accepted content types,
adding a format-detection layer, or adding a credential mechanism would each
alter this accepted contract and requires its own review.

## Testing implications

Implementation tests must verify: the existing `jsonld_article` and
`generic_json_article` composition paths remain byte-for-byte unaffected;
`MicrodataArticleParser` produces the same JSON-safe `ArticleItem`/
`CrawlerItem` output shape as the other two families; malformed, missing,
or ambiguous Microdata fails deterministically through the existing
`ArticleParserError` boundary; a non-null `adapter_key` is still
unconditionally rejected for this family too; and no test contacts a real
network or depends on wall-clock state — synthetic `HtmlDocument` fixtures
only. At least one integration test must prove the full
`SourceProfile → ParserComposer → MicrodataArticleParser → ArticleItem →
CrawlerItem` flow without disturbing the existing `jsonld_article`
integration path.

## Relationship to existing decisions

- ADR-002, ADR-007, and ADR-008 remain authoritative; `BaseParser`'s lazy,
  validated lifecycle is unchanged, and `MicrodataArticleParser` must still
  satisfy it.
- ADR-005 remains authoritative; `HtmlFetcher`'s HTML-only acquisition
  boundary is unchanged.
- ADR-010 remains authoritative; parser-family dispatch stays explicit and
  static.
- ADR-011 remains authoritative; parser and composition APIs remain
  provisional under its policy.
- ADR-020 remains authoritative for exact-host source governance and
  `SourceRegistry`; unchanged by this ADR.
- ADR-021 and ADR-023 remain authoritative; `ArticleCrawlService`'s
  sequence and the CLI's stdout contract are unchanged, since output shape
  is preserved.
- ADR-024 remains authoritative; its review trigger "a second parser family
  with a different output shape is introduced" is not fired, since
  `MicrodataArticleParser`'s output shape is identical to the existing
  families'.
- ADR-025 remains authoritative and is directly extended: this ADR adds a
  third family to the same closed, static seam, without reopening any of
  its decisions about `adapter_key`, the acquisition boundary, or the
  absence of a credential mechanism.

## Follow-up work

- Implement Task 9.4: add `microdata_article` to `SourceProfile.
  supported_parser_families`, add the `ParserComposer` dispatch branch, and
  implement `MicrodataArticleParser`.
- Add focused and integration tests proving output-shape parity, error
  handling, and non-interference with the existing two families.
- Align documentation only after implementation and integration
  verification are complete, mirroring the Sprint 7/8 sequence.
- Do not enable any real production source under this ADR; that requires a
  separate, project-owner-approved decision.

## Review triggers

- A real external source or publisher using Microdata is proposed for
  production enablement, requiring its own source-approval and legal
  review.
- Non-HTML content acquisition (for example, RSS/Atom) is required,
  requiring revisiting `HtmlFetcher`/ADR-005's scope.
- A parser family with a genuinely different output shape (not
  `ArticleItem`-compatible) is needed, requiring revisiting ADR-023's
  stdout contract and ADR-024's persistence serialization.
- A fourth or later parser family creates dispatch-table maintenance
  pressure that may justify a registry, revisiting ADR-025's "small,
  static, explicit" dispatch choice.
- Credentialed or authenticated outbound requests are required, requiring
  revisiting `RequestIdentity`/ADR-014's scope.
- A social-media platform or CLI-triggered batch input is proposed,
  requiring its own separate architecture track.
