# AA Crawler

A production-ready foundation for building media monitoring and crawling
systems across social networks, video platforms, and online news sources.

## Overview

AA Crawler provides explicit configuration and observability foundations plus
a reusable synchronous crawler stack. It supports robots-aware HTML acquisition,
validated request identity, deterministic HTTP policies, and source-agnostic
article composition with application-level orchestration and explicit runtime
resource ownership.

**Current status:** Sprints 5 through 17 are complete and closed. Sprint 10
(CLI-triggered persistence) added ADR-027: the CLI gained one optional
`--output` argument that reuses the existing `FileCrawlResultSink`, with
integration verification confirming default CLI behavior (no `--output`) is
unchanged while the new path works end-to-end through the real pipeline.
Sprint 11 activated Kompas as a second real production source — a project-
governance decision (no new ADR required; ADR-020 pre-authorizes ordinary
source onboarding) — and both current production sources now resolve and
compose normally. Sprint 12 added a GitHub Actions CI pipeline
(`.github/workflows/ci.yml`, no new ADR required) that runs the full
quality-gate suite on every push and pull request targeting `main`,
verified green on both a real pull request and a real push to `main`.
Sprint 13 added ADR-028: an optional `--interval` CLI argument that
repeats the same synchronous crawl on a schedule — the project's first
step toward its realtime goal, staying fully synchronous and
deliberately not triggering ADR-017 (queues/workers) or ADR-019 (async/
browser runtimes). Sprint 14 added ADR-029: an optional `--urls-file`
CLI argument that crawls a list of URLs, once or on the same
`--interval` schedule, resolving ADR-023's own long-standing "Multi-URL
batch input... is proposed" review trigger — with a per-URL failure
policy that deliberately treats an unsupported source as recoverable
(skip that URL, keep going) rather than terminal, unlike ADR-028's
single-URL scheduled mode. Sprint 15 added ADR-030: a second concrete
persistence sink, `SqliteCrawlResultSink`, using only the standard-library
`sqlite3` module (no new runtime dependency) — it upserts by
`requested_url` instead of appending, giving real idempotency for the
repeated re-crawls scheduled and batch mode make common; CLI wiring was
explicitly deferred that sprint, mirroring the ADR-024-then-ADR-027
precedent. Sprint 16 added ADR-031: an optional `--sink {file,sqlite}`
CLI argument, valid only with `--output`, that resolves to the
corresponding sink class once in `main()` and reuses it across
single-shot, scheduled, batch, and scheduled-batch mode — closing that
exact gap. `FileCrawlResultSink` remains completely unmodified, and every
existing invocation's behavior is unchanged when `--sink` is omitted.
Sprint 17 activated Detik (`news.detik.com` only) as a third real
production source — another project-owner governance decision under
ADR-020's ordinary-source-onboarding pre-authorization (no new ADR
required, mirroring Sprint 11's Kompas precedent) — bringing the current
production source count to three. Detik's `jsonld_article` parser-family
assignment follows the existing convention but has not yet been confirmed
against a live fetch, consistent with this project's standing
no-live-network-request testing constraint.

## Current capabilities

- Validated immutable crawler identity shared by robots and page acquisition
- Synchronous HTTP transport with explicit timeouts and bounded retry policy
- Per-origin `robots.txt` policy and caching
- Strict, immutable HTML document acquisition and validation
- Immutable crawler and normalized article contracts
- Source-agnostic `NewsArticle` JSON-LD parsing
- Declarative source profiles with exact-host registry lookup
- Explicit, static parser composition without dynamic plugins
- Application-level article crawl orchestration with source-boundary gates
- Explicit synchronous runtime composition and failure-safe resource cleanup
- Synthetic, network-isolated application and runtime integration tests
- Frozen, environment-first application settings and deterministic paths
- Standard-library logging with correlation context and sensitive-data redaction
- An operational synchronous CLI (`aa-crawler <url>`) around the existing
  application runtime, with one JSON object on stdout (single-shot) or one
  per line per iteration/URL (scheduled or batch mode), and CLI-local
  exit codes
- Network-isolated CLI process-boundary integration verification exercising
  real bootstrap, runtime, source, and parser components
- An optional, application-level persistence port (`BaseCrawlResultSink`)
  with two concrete sinks — an append-only file sink
  (`FileCrawlResultSink`) and a SQLite sink with idempotent, per-
  `requested_url` upserts (`SqliteCrawlResultSink`, ADR-030); neither is
  constructed by `ArticleCrawlService` or `ApplicationRuntime`, and only
  the file sink is currently wired into the CLI
- Three closed, statically-dispatched parser families (`jsonld_article`,
  `generic_json_article`, and `microdata_article`), with `adapter_key`
  remaining reserved and unconditionally rejected
- An optional CLI `--output PATH` flag (ADR-027) that appends the crawl
  result to a file via `FileCrawlResultSink`, off by default; default CLI
  behavior is unchanged when it is omitted
- Three enabled production sources (CNN Indonesia, Kompas, Detik)
  resolving and composing identically through the declarative source
  architecture
- A GitHub Actions CI pipeline (`.github/workflows/ci.yml`) that runs
  `uv lock --check`, the full pre-commit hook suite, and coverage-enforced
  tests on every push and pull request targeting `main`
- An optional CLI `--interval SECONDS` / `--max-runs N` scheduled crawl
  mode (ADR-028) that repeats the same synchronous crawl on one reused
  `ApplicationRuntime`, with a documented recoverable-vs-terminal
  per-iteration failure policy; single-shot mode is unchanged when
  `--interval` is omitted
- An optional CLI `--urls-file PATH` batch/multi-URL mode (ADR-029,
  mutually exclusive with the positional `url`) that crawls a list of
  URLs once or repeatedly, reusing one `ApplicationRuntime` and the same
  `--output`/`--interval`/`--max-runs` flags; an unsupported source for
  one URL is recoverable within a batch (skip and continue) rather than
  terminal
- A second concrete persistence sink, `SqliteCrawlResultSink` (ADR-030),
  using only the standard-library `sqlite3` module — `save()` upserts by
  `requested_url` into one table, replacing the previous row for that URL
  instead of duplicating it
- An optional CLI `--sink {file,sqlite}` argument (ADR-031, valid only
  with `--output`) that selects which concrete sink `--output` targets,
  resolved once in `main()` and reused across single-shot, scheduled,
  batch, and scheduled-batch mode; defaults to `file`, preserving every
  existing invocation's exact behavior when omitted

## Current limitations

- Automatic redirect following is not enabled.
- `generic_json_article` is a synthetic proof-of-concept parser family
  exercised only through in-test fixtures; no production `SourceProfile`
  uses it, and it is not reachable through real network acquisition, since
  `HtmlFetcher` still accepts only HTML content types.
- `microdata_article` is likewise a proof-of-concept family with no
  production `SourceProfile`; unlike `generic_json_article` it remains
  `text/html` and is therefore reachable through the existing acquisition
  boundary, but no real publisher is enabled.
- Dynamic adapters and plugin runtimes are not implemented.
- The production source set is intentionally small, and live crawling remains
  governance-controlled.
- Persistence is an explicit, optional primitive: no distributed worker,
  message queue, distributed execution, asynchronous runtime, browser
  rendering, or live profile reload exists. The CLI's `--interval` flag
  (ADR-028) and `--urls-file` flag (ADR-029) together provide only a
  single-process, in-memory, sequential repeat loop over a fixed list of
  URLs — not a general scheduler, cron-like registry, remote/dynamic
  URL-list source, concurrent per-URL crawling, or multi-process
  coordination. The CLI's `--output` flag (ADR-027) is the only wiring
  between the CLI and persistence; the application service and runtime
  remain fully unaware of persistence.
- `FileCrawlResultSink` (the CLI's default sink, and the only one before
  ADR-031) remains append-only with no deduplication or idempotency
  guarantee. `SqliteCrawlResultSink` (ADR-030) provides per-`requested_url`
  idempotency and is now CLI-selectable via `--sink sqlite` (ADR-031).
  Persisting to both sinks in one invocation is not supported; each
  invocation targets exactly one destination and one sink.
- `SqliteCrawlResultSink`'s upsert-by-`requested_url` keeps only the
  latest successful crawl per URL; it does not keep history across
  crawls, and is not safe for concurrent writers from separate processes.
- The synchronous runtime provides no thread-safety guarantee.
- The CLI accepts either one URL (the positional `url`) or a batch of URLs
  from a local file (`--urls-file`, ADR-029) — never both, and never
  stdin. A single-URL invocation's stdout is exactly one JSON object in
  single-shot mode; scheduled and batch modes' stdout is one JSON object
  per line per successful iteration/URL (JSON Lines), matching the
  `--output` file's existing format.
- Only `UnsupportedSourceError` is recoverable, and only in batch mode
  (`--urls-file`); every other failure category, and every failure in
  single-URL mode, remains terminal exactly as documented in the exit-code
  table below.
- The CLI has no flag that overrides source, robots, retry, identity, or
  parser behavior; it cannot bypass source governance. `--output` selects a
  persistence destination only, and `--interval`/`--max-runs`/`--urls-file`
  select only how many URLs are crawled and how often — none of them
  affect what is crawled or how.

## Architecture overview

The major packages each own a narrow responsibility:

| Package | Responsibility |
|---|---|
| `configuration` | Typed settings, explicit loading, and runtime paths |
| `observability` | Logging setup, correlation context, and redaction |
| `identity` | Validated immutable request identity |
| `crawler` | Crawler contracts and synchronous lifecycle |
| `http` | HTTPX transport, timeout, and retry policies |
| `robots` | `robots.txt` retrieval, evaluation, and caching |
| `html` | Robots-aware HTML acquisition and strict decoding |
| `contracts` | Normalized application-level data contracts |
| `parser` | Lazy parser lifecycle and generic article parsing |
| `sources` | Declarative profiles and exact-host lookup |
| `composition` | Explicit source-to-parser construction |
| `application` | Article crawl coordination, application errors, and runtime ownership |
| `cli` | Synchronous process boundary: argument parsing, bootstrap/runtime invocation, serialization, and exit-code translation |
| `persistence` | Optional, explicitly composed crawl-result persistence port and concrete sinks |

The current application-level flow is:

```text
URL
  → SourceRegistry
  → ArticleCrawlService
  → HtmlFetcher
  → HtmlDocument
  → final-source validation
  → ParserComposer
  → JsonLdArticleParser
  → ArticleItem
  → CrawlerItem
```

`ArticleCrawlService` rejects malformed, non-HTTPS, unknown, and disabled
sources before acquisition. After acquisition, the final transport URL must
resolve to the same selected `SourceProfile`; transitions between that
profile's exact hosts are allowed, while cross-profile transitions raise
`SourceBoundaryError`. Parser composition occurs only after this gate, and the
service returns an ordered `tuple[CrawlerItem, ...]`, including an empty tuple
when parsing yields no items.

`UnsupportedSourceError` represents the pre-acquisition source gate;
`SourceBoundaryError` represents a post-acquisition source mismatch. Canonical
URL validation remains parser-owned. Caller metadata is forwarded to
acquisition unchanged and cannot select source governance, retry behavior,
identity, or parser family.

### Application runtime

`create_application_runtime()` builds an independent synchronous
`ApplicationRuntime` containing the runtime-local `RequestIdentity`,
`TimeoutPolicy`, `RetryPolicy`, `HttpClient`, `RobotsPolicy`, `HtmlFetcher`,
`SourceRegistry`, `ParserComposer`, and `ArticleCrawlService`. The service
coordinates the use case; each lower-level component retains its own policy.

Each runtime owns exactly one `HttpClient`, exposes only
`article_crawl_service`, and supports explicit `close()` and synchronous context
management. Closing repeatedly is safe. Construction failures release any
client already acquired, while dependent components never own or close it.
There is no global runtime, singleton, or service locator.

The application package intentionally exports only `ApplicationError`,
`ApplicationRuntime`, `ArticleCrawlService`, `SourceBoundaryError`,
`UnsupportedSourceError`, and `create_application_runtime`.

### Operational CLI

The `aa-crawler` console script (declared as `aa_crawler:main`) is a thin,
synchronous process boundary around the application runtime described above.
It accepts either one positional URL or a `--urls-file` batch (ADR-029,
mutually exclusive with each other), parsed with the standard-library
`argparse`, and follows the sequence:

```text
process
  → aa_crawler:main
  → aa_crawler.cli
  → bootstrap_application()
  → create_application_runtime()
  → ApplicationRuntime
  → ArticleCrawlService.crawl()
  → serialization
  → stdout / process exit
```

On success with a single URL, it prints exactly one JSON object to stdout
and exits `0`. With `--interval` (ADR-028) and/or `--urls-file` (ADR-029),
it instead prints one JSON object per line per successful iteration/URL —
see "Scheduled crawl mode" and "Batch/multi-URL mode" below. Lifecycle and
failure logging use the existing logger hierarchy and never reach stdout.
Known failures translate to a small, CLI-local, deterministic exit-code
mapping (see below); this mapping does not replace or extend the internal
exception hierarchy, and no new runtime dependency was introduced —
argument parsing, serialization, and correlation-ID generation use only
the standard library (`argparse`, `json`, `time`, `uuid`).

#### CLI usage

```bash
aa-crawler https://www.cnnindonesia.com/nasional/20990101010101-20-9999999/example-story

# Also append the result to a file (ADR-027); omit -o for the same
# behavior as above:
aa-crawler https://www.cnnindonesia.com/nasional/20990101010101-20-9999999/example-story \
  -o data/processed/results.jsonl

# Re-crawl the same URL every 5 minutes, indefinitely, also persisting
# each successful result (ADR-028):
aa-crawler https://www.cnnindonesia.com/nasional/20990101010101-20-9999999/example-story \
  --interval 300 -o data/processed/results.jsonl

# Crawl a list of URLs from a file once (ADR-029); one absolute HTTPS URL
# per line, blank lines and lines starting with # are skipped:
aa-crawler --urls-file sources.txt -o data/processed/results.jsonl

# Re-crawl the whole list every 5 minutes:
aa-crawler --urls-file sources.txt --interval 300

# Persist to a SQLite database instead, with real per-URL idempotency
# (ADR-031, ADR-030) — combines with any of the modes above:
aa-crawler https://www.cnnindonesia.com/nasional/20990101010101-20-9999999/example-story \
  -o data/processed/results.db --sink sqlite
```

The CLI takes either exactly one positional URL, or a `--urls-file PATH`
batch of URLs (ADR-029) — mutually exclusive, exactly one is required per
invocation. It also accepts one optional `-o`/`--output PATH` argument, an
optional `--sink {file,sqlite}` argument (ADR-031, valid only with
`--output`), and an optional `-i`/`--interval SECONDS` argument (with an
optional `--max-runs N` bound, valid only together with `--interval`)
that selects scheduled crawl mode instead of the default single pass.
There are no subcommands and no flags that override source, robots,
retry, identity, or parser behavior; `--output`/`--sink` select a
persistence destination and sink only, and `--interval`/`--max-runs`/
`--urls-file` select only how many URLs are crawled and how often.

#### Output contract

A successful invocation prints one JSON object containing the current
shipped article fields:

`source`, `source_domain`, `requested_url`, `canonical_url`, `headline`,
`published_at`, `description`, `author_names`, `modified_at`, `section`,
`lead_image_url`, `language`.

`requested_url` preserves the exact URL supplied to the CLI; `canonical_url`
preserves the parser-derived canonical URL independently. In practice, the
CLI only ever produces `jsonld_article`-parsed output today: no production
`SourceProfile` uses the second or third, synthetic `generic_json_article`
(ADR-025) or `microdata_article` (ADR-026) families, and `HtmlFetcher` still
accepts only HTML content types for the family that requires it. This
output contract does not promise a stable serialization for a hypothetical
future parser family with a different output shape.

#### Exit codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | Unexpected or unmapped failure |
| `2` | Unsupported or disabled source |
| `3` | Crawl-domain failure (acquisition, robots, source-boundary, or parsing) |
| `4` | Configuration or startup failure |
| `5` | Crawl succeeded, but the `--output` persistence write failed (ADR-027) |

These are CLI-local process-boundary semantics only. They do not introduce
or replace a project-wide exception hierarchy or error taxonomy. Exit code
`5` is reported only when `--output` is supplied; the JSON payload is
already on stdout by the time it can occur.

#### Scheduled crawl mode (ADR-028)

`--interval SECONDS` (optionally bounded by `--max-runs N`) repeats the
same synchronous crawl on one reused `ApplicationRuntime` instead of
opening and closing one per invocation: the first crawl happens
immediately, then the CLI waits `SECONDS` and crawls again, until
interrupted, `--max-runs` iterations complete, or a terminal failure
occurs. This stays fully synchronous — no async runtime, browser, queue,
or worker was introduced (ADR-017 and ADR-019 remain exactly as Deferred/
Proposed as before).

Each iteration applies a documented recoverable-vs-terminal failure
policy:

| Condition | Behavior |
|---|---|
| A crawl-domain failure (exit code `3`'s underlying cause) | Recoverable: logged, no output for that iteration, the loop continues after the usual wait |
| Reaching `--max-runs`, or a keyboard interrupt (`Ctrl+C`) | Clean shutdown: exit `0` |
| An unsupported source, an unexpected failure, or a persistence write failure | Terminal: logged, the loop stops immediately with the same exit code single-shot mode would use |

Because a scheduled run can produce more than one result, stdout's
contract differs from single-shot mode: one JSON object **per line** per
successful iteration (JSON Lines), matching the `--output` file's existing
format — not the single "exactly one JSON object" single-shot promises.
`--output`, when supplied, still saves via the selected sink (ADR-024/
ADR-027/ADR-031), once per successful iteration.

#### Batch/multi-URL mode (ADR-029)

`--urls-file PATH` — mutually exclusive with the positional `url` —
crawls a list of URLs from a local file (one absolute HTTPS URL per line;
blank lines and lines starting with `#` are skipped) on one reused
`ApplicationRuntime`, once (single-shot batch) or repeatedly with
`--interval` (scheduled batch, where one "run"/iteration is one full pass
over the whole list, and `--max-runs` bounds the number of passes, not the
number of URLs).

Batch mode's per-URL failure policy deliberately differs from ADR-028's
single-URL scheduled mode for one condition:

| Condition | Behavior |
|---|---|
| An unsupported source for one URL | **Recoverable** here (differs from ADR-028): logged, that URL is skipped, the pass continues with the next URL |
| A crawl-domain failure for one URL | Recoverable: logged, skipped, the pass continues |
| A persistence write failure, or an unexpected failure | Terminal: logged, the whole batch/run stops immediately with the same exit code single-URL mode would use |
| Reaching `--max-runs`, or a keyboard interrupt | Clean shutdown: exit `0` |

Exit code `0` is returned once a pass (or the whole scheduled run)
completes, even if some URLs were skipped — partial success is still
process-level success; each successful URL prints its own JSON line, and
each skipped URL logs its own error, so the operator can tell full success
from partial success without a new exit-code category. No new exit code
is introduced; batch mode reuses exactly the codes above. `--output`, when
supplied, saves via the selected sink (see below), once per successful
URL.

#### Sink selection (ADR-031)

`--sink {file,sqlite}` — valid only together with `--output` — selects
which concrete sink `--output` targets, resolved once regardless of
whether the CLI is in single-shot, scheduled, batch, or scheduled-batch
mode:

- `file` (the default when `--sink` is omitted) appends one JSON Lines
  record per successful result via `FileCrawlResultSink` — ADR-027's
  original, unchanged behavior.
- `sqlite` upserts by `requested_url` into a SQLite database via
  `SqliteCrawlResultSink` (ADR-030) instead, giving real idempotency:
  re-crawling the same URL under `--interval` or across repeated
  `--urls-file` passes replaces that URL's row rather than duplicating
  it.

`--sink` without `--output` is rejected by argument parsing, since there
is then no destination for it to target. Persisting to both sinks in one
invocation is not supported.

### Persistence boundary

`aa_crawler.persistence` is an optional, application-level port
implementing ADR-024. It defines an abstract `BaseCrawlResultSink`
(`save(item: CrawlerItem) -> None`) and two concrete implementations.

`FileCrawlResultSink` serializes `CrawlerItem.data` to JSON and appends it
as one line to a caller-supplied file path — reusing the exact
`dict(item.data)` → `json.dumps(...)` pattern already used by
`aa_crawler.cli`:

```python
from pathlib import Path

from aa_crawler.persistence import FileCrawlResultSink

sink = FileCrawlResultSink(destination=Path("data/processed/results.jsonl"))
for item in items:
    sink.save(item)
```

`save()` raises `PersistenceWriteError` (a `CrawlerError` subclass) when
serialization or the durable write fails. The sink does not deduplicate,
overwrite, or guarantee idempotency; repeated `save()` calls with the same
item append the same line again.

`SqliteCrawlResultSink` (ADR-030) instead upserts by
`item.data["requested_url"]` into one SQLite table, using only the
standard-library `sqlite3` module — no new runtime dependency:

```python
from pathlib import Path

from aa_crawler.persistence import SqliteCrawlResultSink

sink = SqliteCrawlResultSink(destination=Path("data/processed/results.db"))
for item in items:
    sink.save(item)
```

Unlike the file sink, repeated `save()` calls for the same `requested_url`
replace that row's `payload` and `updated_at` timestamp instead of
duplicating it — real idempotency for the repeated re-crawls scheduled
(ADR-028) and batch (ADR-029) mode make common. `save()` raises
`PersistenceWriteError` when serialization fails, when `requested_url` is
missing, empty, or not a string, or when the durable write fails (an
invalid destination or database file, for example).

Neither sink is imported by `ArticleCrawlService` or `ApplicationRuntime`;
a static test verifies this. Per ADR-027, the CLI is one deliberate
exception to both sinks' optionality: when `--output` is supplied, it
constructs `FileCrawlResultSink` by default, or `SqliteCrawlResultSink`
when `--sink sqlite` is also given (ADR-031), and calls `save()` after the
JSON payload has already been printed to stdout. `aa_crawler.cli.app`,
`aa_crawler.cli.scheduler`, and `aa_crawler.cli.batch` each import
`aa_crawler.persistence` only for this purpose; a static test asserts this
positively for `cli.app`, alongside the unchanged negative assertion for
`ArticleCrawlService` and `ApplicationRuntime`. Composing either sink
directly in Python, as shown above, remains fully supported and is not
CLI-specific.

### Request identity

`RequestIdentity` is immutable and supplies one consistent User-Agent to
robots retrieval, robots evaluation, and page requests. `HttpClient` remains
identity-neutral and sends the headers supplied by its caller. Validation
rejects browser, search-engine, and third-party crawler impersonation.
Runtime creation obtains the installed product version with
`importlib.metadata.version("aa-crawler")` and reuses one exact identity instance
for `RobotsPolicy` and `HtmlFetcher`.

### Retry behavior

Automatic retries apply only to `GET` and `HEAD`. Other HTTP methods remain
valid but receive one transport attempt. Retry behavior is owned by the HTTP
policy and uses bounded deterministic backoff.

### Article parsing

`ArticleItem` represents normalized immutable article metadata, produced by
any of the three shipped parser families. `JsonLdArticleParser` extracts
source-agnostic `NewsArticle` JSON-LD from HTML while keeping requested and
canonical URLs distinct. `GenericJsonArticleParser` (ADR-025) is a synthetic
proof-of-concept second family that parses a flat JSON object directly from
`HtmlDocument.content` — never JSON-LD, never HTML. `MicrodataArticleParser`
(ADR-026) is a third family that parses `schema.org` `NewsArticle`/`Article`
Microdata (`itemscope`/`itemtype`/`itemprop` attributes) directly from HTML,
including one level of nested Microdata (for example an `author` expressed
as a nested `Person`, or an `image` as a nested `ImageObject`). All three
families produce the exact same `ArticleItem`/`CrawlerItem` output shape.
`GenericJsonArticleParser` and `MicrodataArticleParser` are exercised only
through synthetic in-test fixtures. Tests use synthetic metadata;
article-body extraction is not part of any of the three generic contracts.

### Declarative sources

- `SourceProfile` is an immutable declarative source definition.
- `SourceRegistry` performs exact-host lookup and excludes disabled profiles
  by default.
- `ParserComposer` constructs parsers through an explicit static mapping; no
  dynamic plugin system exists. Three parser families are currently
  supported (`jsonld_article`, `generic_json_article`, `microdata_article`);
  each addition requires a reviewed code change to
  `SourceProfile.supported_parser_families` and `ParserComposer`'s dispatch,
  never configuration or runtime registration.

Ordinary source onboarding adds a reviewed profile and reuses the generic
parser when the source is structurally compatible. A source-specific parser or
adapter should be introduced only when observed evidence requires it.

#### Initial production profiles

| Source | State | Parser | Adapter | Exact hosts |
|---|---|---|---|---|
| CNN Indonesia | Enabled | `jsonld_article` | None | `www.cnnindonesia.com` |
| Kompas | Enabled | `jsonld_article` | None | `www.kompas.com`, `nasional.kompas.com`, `surabaya.kompas.com` |
| Detik | Enabled | `jsonld_article` | None | `news.detik.com` |

Enabled and disabled states record project governance. They do not replace
`robots.txt`, publisher policy, legal review, rate-limit approval, or
operational authorization, and they do not constitute legal approval. Host
ownership is exact; wildcard, suffix, and implicit subdomain matching are not
supported.

## Technology stack

| Component | Technology |
|---|---|
| Language | Python 3.12+ |
| Package manager | [uv](https://docs.astral.sh/uv/) |
| HTTP transport | HTTPX, behind `HttpClient` |
| Configuration | Pydantic and `pydantic-settings` |
| Quality | Ruff, mypy, pytest, coverage, pre-commit |
| Version control | Git and pull requests |

Direct runtime dependencies are maintained in `pyproject.toml`:

- `httpx>=0.28.1,<0.29`
- `pydantic>=2.13.4,<3`
- `pydantic-settings>=2.14.2,<2.15`

## Requirements

- Python **3.12+**
- [uv](https://docs.astral.sh/uv/) for dependency and project management

## Project structure

```text
aa_crawler/
├── config/                         # Optional static configuration; no secrets
├── data/                           # Ignored runtime data
├── docs/                           # ADRs, standards, and sprint records
├── logs/                           # Ignored runtime logs
├── scripts/                        # Operational and development utilities
├── src/aa_crawler/
│   ├── configuration/              # Settings, loading, and paths
│   ├── observability/              # Logging, context, and redaction
│   ├── identity/                   # Request identity contract
│   ├── crawler/                    # Crawler contracts and lifecycle
│   ├── http/                       # Synchronous transport and policies
│   ├── robots/                     # robots.txt authority
│   ├── html/                       # Strict HTML acquisition
│   ├── contracts/                  # Normalized data contracts
│   ├── parser/                     # Parser lifecycle and article parsing
│   ├── sources/                    # Profiles and exact-host lookup
│   ├── composition/                # Explicit parser construction
│   ├── application/
│   │   ├── errors.py               # Application boundary errors
│   │   ├── service.py              # Article crawl orchestration
│   │   └── runtime.py              # Runtime graph and resource ownership
│   ├── cli/
│   │   ├── __init__.py             # Argument parsing and public main()
│   │   ├── app.py                  # Bootstrap → runtime → crawl → exit-code mapping (single-shot)
│   │   ├── scheduler.py            # Bootstrap → reused runtime → repeated crawl (scheduled, ADR-028)
│   │   └── batch.py                # Bootstrap → reused runtime → per-URL pass (batch, ADR-029)
│   ├── persistence/
│   │   ├── base.py                 # Abstract BaseCrawlResultSink port
│   │   ├── errors.py               # PersistenceError, PersistenceWriteError
│   │   ├── file_sink.py            # FileCrawlResultSink (append-only JSON Lines)
│   │   └── sqlite_sink.py          # SqliteCrawlResultSink (idempotent upsert, ADR-030)
│   └── bootstrap.py                # Configuration, paths, and logging startup
├── tests/                          # Mirrored automated test suite
├── pyproject.toml                  # Project metadata and dependencies
└── README.md
```

## Getting started

```bash
git clone https://github.com/muhammadarifalfani/aa-crawler.git
cd aa_crawler
uv sync
```

## Application bootstrap

The `aa-crawler` command-line entry point (see
[Operational CLI](#operational-cli) above) already wires both boundaries
below together for a single crawl invocation. Library callers compose them
explicitly instead.

Startup is explicit and uses the public bootstrap API:

```python
from pathlib import Path

from aa_crawler import bootstrap_application

settings = bootstrap_application(
    base_dir=Path("."),
    env_file=None,
    overrides={"logging": {"level": "INFO"}},
)
```

`env_file` is optional and never discovered automatically. Configuration
precedence, from highest to lowest, is:

1. Explicit overrides
2. OS environment variables
3. An explicitly supplied `.env` file
4. Model defaults

Bootstrap resolves runtime paths, prepares required runtime directories, and
configures logging. It returns `ApplicationSettings`; it does not create or
return `ApplicationRuntime`. Runtime composition remains a separate explicit
operation, and neither API implicitly calls the other. None of these operations
occur at import time.

Application startup may use both public boundaries explicitly:

```python
from pathlib import Path

from aa_crawler import bootstrap_application
from aa_crawler.application import create_application_runtime

settings = bootstrap_application(base_dir=Path("."))

with create_application_runtime() as runtime:
    items = runtime.article_crawl_service.crawl(
        "https://www.cnnindonesia.com/example/article"
    )
```

The settings value remains available to the caller. The current runtime factory
accepts no settings, so configuration bootstrap is application setup rather
than a hidden runtime dependency.

### Environment variables

| Area | Variables |
|---|---|
| Core | `AA_ENV`, `AA_DEBUG`, `AA_DATA_DIR`, `AA_LOG_DIR`, `AA_CONFIG_DIR`, `AA_TEMP_DIR` |
| Logging | `AA_LOG_LEVEL`, `AA_LOG_CONSOLE_ENABLED`, `AA_LOG_FILE_ENABLED`, `AA_LOG_FORMAT`, `AA_LOG_FILE_NAME`, `AA_LOG_MAX_BYTES`, `AA_LOG_BACKUP_COUNT` |

Application variables use the `AA_` prefix. Unknown `AA_` variables are
rejected; unrelated variables are ignored. `AA_HTTP_PROXY` and
`AA_HTTPS_PROXY` are reserved and inactive. Never commit secrets or a local
`.env` file.

### Runtime paths

- `base_dir` is explicit.
- Relative runtime paths are anchored below `base_dir`; traversal is rejected.
- Absolute paths remain absolute.
- Bootstrap prepares `data_dir` and `temp_dir` idempotently.
- `log_dir` is prepared only when file logging is enabled.
- `config_dir` is never created automatically.

### Logging and observability

The `aa_crawler` logger hierarchy writes text logs to stderr at `INFO` by
default. Optional UTF-8 file logging uses `aa-crawler.log`, rotates at 10 MiB,
and retains five backups. Missing correlation context is rendered as `-`, and
recognized sensitive values are replaced with `[REDACTED]`. JSON logging,
metrics, tracing, and comprehensive PII detection are not implemented.

## Testing and quality

Ruff enforces linting and formatting, mypy checks the configured typed scope,
pytest runs the automated suite, coverage enforces the repository threshold,
and pre-commit runs the integrated checks. Application unit tests, article-crawl
integration tests, and runtime-composition integration tests use synthetic,
network-isolated boundaries. They verify source gates, cleanup after normal and
failed construction, runtime independence, and bootstrap/runtime separation.
CLI unit tests cover argument parsing and exit-code translation; CLI
process-boundary integration tests exercise real bootstrap, runtime, source,
and parser components behind synthetic or network-guarded acquisition, and
verify stdout/log channel separation, the requested/canonical URL
distinction, runtime cleanup, and correlation-context isolation across
invocations.

## Roadmap

| Sprint | Focus | Status |
|---|---|---|
| **Sprint 1** | Repository foundation, policies, and tooling | **Completed** |
| **Sprint 2** | Configuration, runtime paths, observability, and bootstrap | **Completed** |
| **Sprint 3** | Synchronous crawler, HTTP, robots, HTML, and parser foundation | **Completed** |
| **Sprint 4** | Identity, retry safety, article parsing, and declarative sources | **Completed** |
| **Sprint 5** | Application orchestration and runtime resource ownership | **Completed** |
| **Sprint 6** | Operational CLI process boundary | **Completed** |
| **Sprint 7** | Application-level persistence boundary | **Completed** |
| **Sprint 8** | Extensible parser-family composition seam | **Completed** |
| **Sprint 9** | Microdata article parser family | **Completed** |
| **Sprint 10** | CLI-triggered persistence | **Completed** |
| **Sprint 11** | Second production source activation (Kompas enabled) | **Completed** |
| **Sprint 12** | GitHub Actions CI pipeline | **Completed** |
| **Sprint 13** | CLI scheduled crawl mode (`--interval`) | **Completed** |
| **Sprint 14** | CLI batch/multi-URL input (`--urls-file`) | **Completed** |
| **Sprint 15** | SQLite crawl result sink (`SqliteCrawlResultSink`) | **Completed** |
| **Sprint 16** | CLI sink selection (`--sink {file,sqlite}`) | **Completed** |
| **Sprint 17** | Third production source activation (Detik enabled) | **Completed** |

Possible future directions remain provisional, not committed scope: a real
external source or platform proposal (with its own legal/acquisition/
credential review), non-HTML content acquisition, a credential/
authentication mechanism, separately reviewed redirect architecture, broader
reviewed sources, alternate execution families under ADR-019, persisting
to more than one sink in a single invocation, concurrent per-URL crawling
within one pass, a remote/dynamic URL-list source, distributed worker/
queue concerns, and observability hardening.

## Documentation

- [Engineering Standards](docs/architecture/engineering-standards.md)
- [Architecture Decision Record index](docs/adr/README.md)
- [ADR-014: User-Agent Ownership](docs/adr/0014-user-agent-ownership.md)
- [ADR-015: Retry Idempotency](docs/adr/0015-retry-idempotency.md)
- [ADR-020: Declarative Source Architecture](docs/adr/0020-declarative-source-architecture.md)
- [ADR-021: Application-Level Article Crawl Orchestration](docs/adr/0021-application-level-article-crawl-orchestration.md)
- [ADR-022: Application Runtime Composition and Resource Ownership](docs/adr/0022-application-runtime-composition-and-resource-ownership.md)
- [ADR-023: CLI Application Entry Point and Process Boundary](docs/adr/0023-cli-application-entry-point-and-process-boundary.md)
- [ADR-024: Application-Level Persistence Boundary for Crawl Results](docs/adr/0024-application-level-persistence-boundary.md)
- [ADR-025: Extensible Parser-Family Composition Seam](docs/adr/0025-extensible-parser-family-composition.md)
- [ADR-026: Microdata Article Parser Family](docs/adr/0026-microdata-article-parser-family.md)
- [ADR-027: CLI-Triggered Persistence](docs/adr/0027-cli-triggered-persistence.md)
- [ADR-028: CLI Scheduled Crawl Mode](docs/adr/0028-cli-scheduled-crawl-mode.md)
- [ADR-029: CLI Batch/Multi-URL Input](docs/adr/0029-cli-batch-url-input.md)
- [ADR-030: SQLite Crawl Result Sink](docs/adr/0030-sqlite-crawl-result-sink.md)
- [ADR-031: CLI Sink Selection](docs/adr/0031-cli-sink-selection.md)
- [Sprint 3 completion record](docs/sprint/sprint-3.md)
- [Contribution guide](CONTRIBUTING.md)

## Data layout

| Path | Purpose |
|---|---|
| `data/raw/` | Raw crawled content before transformation |
| `data/processed/` | Normalized and processed output |
| `data/failed/` | Failed records for inspection |

## License

This project is under active development. The license will be determined
before the first stable release.
