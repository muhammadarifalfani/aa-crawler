# AA Crawler

A production-ready foundation for building media monitoring and crawling
systems across social networks, video platforms, and online news sources.

## Overview

AA Crawler provides an explicit configuration and observability baseline plus
a reusable synchronous crawler stack. Sprint 3 is complete; the project can
acquire robots-compliant HTML and transform it into validated domain items
without coupling platform implementations to transport details.

**Current status:** Sprint 3 — Synchronous Crawler Foundation is completed.
Sprint 4 is planned.

## Current capabilities

- Immutable, slotted crawler request, response, and item contracts
- A reusable synchronous HTTP client isolated behind domain adapters
- Explicit timeout and deterministic retry policies
- Per-origin `robots.txt` policy and caching
- Strict HTML content validation and decoding
- A lazy parser framework with output-contract validation
- A generic HTML crawler with preserved ordering and fail-fast behavior
- Frozen, environment-first application settings and deterministic paths
- Standard-library logging with correlation context and sensitive-data redaction

## Current limitations

- No platform-specific crawler
- No asynchronous runtime or browser automation
- No scheduler, concurrency, or recursive crawling
- No persistence layer
- No plugin system
- No production crawler CLI

## Architecture overview

The synchronous crawler stack uses constructor injection and keeps each
responsibility behind one boundary:

```text
Configured URLs
    → BaseCrawler / HtmlCrawler
    → HtmlFetcher
    → RobotsPolicy
    → HttpClient
    → HtmlDocument
    → BaseParser
    → CrawlerItem
```

`HttpClient` owns transport, `RobotsPolicy` owns robots decisions,
`HtmlFetcher` owns HTML validation and decoding, `BaseParser` validates parser
outputs, and `BaseCrawler` owns the lazy crawl lifecycle. For each configured
URL, `HtmlCrawler` performs exactly one page transport request after the
robots decision. Execution is synchronous, ordered, and fail-fast.

## Planned data sources

| Platform | Type |
|---|---|
| Instagram | Social media |
| Facebook | Social media |
| TikTok | Short-form video |
| X (Twitter) | Microblogging |
| Threads | Social media |
| YouTube | Video |
| Online News | Web / news sites |

## Technology stack

| Component | Technology |
|---|---|
| Language | Python 3.12+ |
| Package manager | [uv](https://docs.astral.sh/uv/) |
| HTTP transport | HTTPX, behind `HttpClient` |
| Configuration | `pydantic-settings` |
| Quality | Ruff, mypy, pytest, coverage, pre-commit |
| Version control | Git and pull requests |

Pydantic is used by the settings implementation and is classified by
[ADR-013](docs/adr/0013-pydantic-dependency-classification.md) as a future
direct dependency declaration. That metadata alignment has not yet occurred.

## Requirements

- Python **3.12+**
- [uv](https://docs.astral.sh/uv/) for dependency and project management

## Project structure

```text
aa_crawler/
├── config/                         # Optional static configuration; no secrets
├── data/                           # Ignored runtime data
├── docs/
│   ├── adr/                        # Architecture Decision Records
│   ├── architecture/               # Engineering and architecture standards
│   ├── diagrams/                   # Architecture and flow diagrams
│   └── sprint/                     # Sprint completion records
├── logs/                           # Ignored runtime logs
├── scripts/                        # Operational and development utilities
├── src/aa_crawler/
│   ├── configuration/              # Typed settings, loading, and paths
│   ├── observability/              # Logging, context, and redaction
│   ├── crawler/                    # Domain contracts and crawl lifecycle
│   ├── http/                       # Synchronous transport and policies
│   ├── robots/                     # robots.txt authority
│   ├── html/                       # Strict HTML acquisition
│   ├── parser/                     # Lazy parser framework
│   └── bootstrap.py                # Explicit application composition root
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

## Roadmap

| Sprint | Focus | Status |
|---|---|---|
| **Sprint 1** | Repository foundation, policies, and tooling | **Completed** |
| **Sprint 2** | Configuration, runtime paths, observability, and bootstrap | **Completed** |
| **Sprint 3** | Synchronous crawler contracts, transport, robots, HTML, parsing, and composition | **Completed** |
| **Sprint 4** | First production evolution scope, subject to approved backlog and ADR entry conditions | Planned |
| **Sprint 5+** | Platform crawlers, processing, persistence, orchestration, and production hardening | Planned |

## Documentation

- [Engineering Standards](docs/architecture/engineering-standards.md)
- [Architecture Decision Record index](docs/adr/README.md)
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
