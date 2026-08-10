# AA Crawler

A production-ready foundation for building media monitoring and crawling
systems across social networks, video platforms, and online news sources.

## Overview

AA Crawler provides explicit configuration and observability foundations plus
a reusable synchronous crawler stack. It supports robots-aware HTML acquisition,
validated request identity, deterministic HTTP policies, and source-agnostic
article composition without coupling source declarations to transport details.

**Current status:** Sprint 4 implementation is complete and documentation
closure is in progress. Sprint 5 remains future work.

## Current capabilities

- Validated immutable crawler identity shared by robots and page acquisition
- Synchronous HTTP transport with explicit timeouts and bounded retry policy
- Per-origin `robots.txt` policy and caching
- Strict, immutable HTML document acquisition and validation
- Immutable crawler and normalized article contracts
- Source-agnostic `NewsArticle` JSON-LD parsing
- Declarative source profiles with exact-host registry lookup
- Explicit, static parser composition without dynamic plugins
- Synthetic end-to-end source-composition integration tests
- Frozen, environment-first application settings and deterministic paths
- Standard-library logging with correlation context and sensitive-data redaction

## Current limitations

- Source composition assumes an `HtmlDocument` has already been acquired.
- No application-level acquisition-to-parsing orchestrator exists yet.
- `jsonld_article` is the only supported parser family.
- Custom adapter loading and a generic adapter runtime are not implemented.
- The production source set is intentionally small, and live crawling remains
  governance-controlled.
- No persistence, scheduler, queue, distributed execution, asynchronous
  crawling, browser rendering, or live profile reload exists.

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

Transport acquisition and source composition remain separate. The current
source-composition flow is:

```text
URL
  → SourceRegistry
  → SourceProfile
  → ParserComposer
  → JsonLdArticleParser
  → ArticleItem
  → CrawlerItem
```

This flow starts with an already acquired `HtmlDocument`; it is not yet a full
URL-to-network-to-article application orchestrator.

### Request identity

`RequestIdentity` is immutable and supplies one consistent User-Agent to
robots retrieval, robots evaluation, and page requests. `HttpClient` remains
identity-neutral and sends the headers supplied by its caller. Validation
rejects browser, search-engine, and third-party crawler impersonation.

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
`robots.txt`, publisher policy, or legal and operational review, and they do
not constitute legal approval.

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
│   └── bootstrap.py                # Application composition root
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
configures logging. None of these operations occur at import time.

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
and pre-commit runs the integrated checks. Source-composition integration tests
use synthetic HTML and metadata and do not access external networks.

## Roadmap

| Sprint | Focus | Status |
|---|---|---|
| **Sprint 1** | Repository foundation, policies, and tooling | **Completed** |
| **Sprint 2** | Configuration, runtime paths, observability, and bootstrap | **Completed** |
| **Sprint 3** | Synchronous crawler, HTTP, robots, HTML, and parser foundation | **Completed** |
| **Sprint 4** | Identity, retry safety, article parsing, and declarative sources | **Implemented; documentation closure** |
| **Sprint 5** | Future production orchestration and source evolution | Future |

Potential Sprint 5 direction includes application-level orchestration from
robots-aware acquisition through source resolution and parser composition,
broader integration testing, additional reviewed source profiles, and targeted
observability or governance hardening. This direction is not yet an approved
detailed sprint scope.

## Documentation

- [Engineering Standards](docs/architecture/engineering-standards.md)
- [Architecture Decision Record index](docs/adr/README.md)
- [ADR-014: User-Agent Ownership](docs/adr/0014-user-agent-ownership.md)
- [ADR-015: Retry Idempotency](docs/adr/0015-retry-idempotency.md)
- [ADR-020: Declarative Source Architecture](docs/adr/0020-declarative-source-architecture.md)
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
