# AA Crawler

A production-ready foundation for building media monitoring and crawling
systems across social networks, video platforms, and online news sources.

## Overview

AA Crawler provides explicit configuration and observability foundations plus
a reusable synchronous crawler stack. It supports robots-aware HTML acquisition,
validated request identity, deterministic HTTP policies, and source-agnostic
article composition with application-level orchestration and explicit runtime
resource ownership.

**Current status:** Sprint 5 and Sprint 6 are complete and closed. Sprint 7
(an application-level persistence boundary) is in progress: ADR-024 is
Accepted, the persistence port and a minimal file-based sink are implemented,
and integration verification confirmed the boundary stays fully optional and
unreferenced by the application or CLI layers.

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
  application runtime, with one JSON object on stdout and CLI-local exit codes
- Network-isolated CLI process-boundary integration verification exercising
  real bootstrap, runtime, source, and parser components
- An optional, application-level persistence port (`BaseCrawlResultSink`)
  with one minimal append-only file sink (`FileCrawlResultSink`), reused by
  callers explicitly; never constructed by `ArticleCrawlService`,
  `ApplicationRuntime`, or `aa_crawler.cli`

## Current limitations

- Automatic redirect following is not enabled.
- `jsonld_article` is the only supported parser family.
- Dynamic adapters and plugin runtimes are not implemented.
- The production source set is intentionally small, and live crawling remains
  governance-controlled.
- Persistence is an explicit, optional, caller-composed primitive only: no
  worker, queue, scheduler, distributed execution, asynchronous runtime,
  browser rendering, or live profile reload exists, and no CLI or
  application-service flag wires persistence into the crawl flow.
- The shipped file sink is append-only with no deduplication, no idempotency
  guarantee, and no database or schema selection.
- The synchronous runtime provides no thread-safety guarantee.
- The CLI accepts exactly one URL per invocation: no batch input, no file or
  stdin input, and no JSON Lines output.
- The CLI has no flag that overrides source, robots, retry, identity, or
  parser behavior; it cannot bypass source governance.

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
It accepts exactly one positional URL, parsed with the standard-library
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

On success, it prints exactly one JSON object to stdout and exits `0`.
Lifecycle and failure logging use the existing logger hierarchy and never
reach stdout. Known failures translate to a small, CLI-local, deterministic
exit-code mapping (see below); this mapping does not replace or extend the
internal exception hierarchy, and no new runtime dependency was introduced —
argument parsing, serialization, and correlation-ID generation use only the
standard library (`argparse`, `json`, `uuid`).

#### CLI usage

```bash
aa-crawler https://www.cnnindonesia.com/nasional/20990101010101-20-9999999/example-story
```

The CLI takes exactly one positional URL per invocation. There are no
subcommands and no flags that override source, robots, retry, identity, or
parser behavior.

#### Output contract

A successful invocation prints one JSON object containing the current
shipped article fields:

`source`, `source_domain`, `requested_url`, `canonical_url`, `headline`,
`published_at`, `description`, `author_names`, `modified_at`, `section`,
`lead_image_url`, `language`.

`requested_url` preserves the exact URL supplied to the CLI; `canonical_url`
preserves the parser-derived canonical URL independently. This output
contract reflects the currently shipped `jsonld_article` parser family only;
it does not promise a stable serialization for hypothetical future parser
families.

#### Exit codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | Unexpected or unmapped failure |
| `2` | Unsupported or disabled source |
| `3` | Crawl-domain failure (acquisition, robots, source-boundary, or parsing) |
| `4` | Configuration or startup failure |

These are CLI-local process-boundary semantics only. They do not introduce
or replace a project-wide exception hierarchy or error taxonomy.

### Persistence boundary

`aa_crawler.persistence` is an optional, application-level port implementing
ADR-024. It defines an abstract `BaseCrawlResultSink` (`save(item: CrawlerItem)
-> None`) and one concrete implementation, `FileCrawlResultSink`, which
serializes `CrawlerItem.data` to JSON and appends it as one line to a
caller-supplied file path — reusing the exact `dict(item.data)` →
`json.dumps(...)` pattern already used by `aa_crawler.cli`.

This package is never imported by `ArticleCrawlService`, `ApplicationRuntime`,
or `aa_crawler.cli`; a static test statically verifies this. A caller that
already holds a produced `CrawlerItem` composes a sink explicitly:

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

`ArticleItem` represents normalized immutable article metadata.
`JsonLdArticleParser` extracts source-agnostic `NewsArticle` JSON-LD while
keeping requested and canonical URLs distinct. Tests use synthetic metadata;
article-body extraction is not part of the current generic contract.

### Declarative sources

- `SourceProfile` is an immutable declarative source definition.
- `SourceRegistry` performs exact-host lookup and excludes disabled profiles
  by default.
- `ParserComposer` constructs parsers through an explicit static mapping; no
  dynamic plugin system exists.

Ordinary source onboarding adds a reviewed profile and reuses the generic
parser when the source is structurally compatible. A source-specific parser or
adapter should be introduced only when observed evidence requires it.

#### Initial production profiles

| Source | State | Parser | Adapter | Exact hosts |
|---|---|---|---|---|
| CNN Indonesia | Enabled | `jsonld_article` | None | `www.cnnindonesia.com` |
| Kompas | Disabled | `jsonld_article` | None | `www.kompas.com`, `nasional.kompas.com`, `surabaya.kompas.com` |

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
│   │   └── app.py                  # Bootstrap → runtime → crawl → exit-code mapping
│   ├── persistence/
│   │   ├── base.py                 # Abstract BaseCrawlResultSink port
│   │   ├── errors.py               # PersistenceError, PersistenceWriteError
│   │   └── file_sink.py            # FileCrawlResultSink (append-only JSON Lines)
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
| **Sprint 7** | Application-level persistence boundary | **In progress** |

Possible future directions remain provisional, not committed scope: separately
approved redirect architecture, broader reviewed sources, alternate execution
families under ADR-019, CLI-triggered persistence, worker/queue/scheduler
concerns, observability hardening, and evidence-driven adapter extensibility.

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
