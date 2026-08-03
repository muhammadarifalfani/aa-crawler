# AA Crawler

A multi-platform media monitoring and crawling framework for collecting, processing, and analyzing content from social networks, video platforms, and online news sources.

## Overview

AA Crawler provides a unified foundation for building reliable, extensible crawlers across multiple media platforms. The framework is structured for long-term maintainability — with clear separation of configuration, source code, documentation, operational scripts, and data pipelines.

**Current status:** Sprint 2 — Configuration and Observability Foundation is complete. Sprint 3 remains planned; crawler functionality has not been implemented yet.

## Vision

Build a scalable and extensible media monitoring platform capable of collecting, normalizing, storing, and analyzing information from multiple digital platforms through a unified data pipeline.

## Planned Data Sources

| Platform      | Type              |
|---------------|-------------------|
| Instagram     | Social media      |
| Facebook      | Social media      |
| TikTok        | Short-form video  |
| X (Twitter)   | Microblogging     |
| Threads       | Social media      |
| YouTube       | Video             |
| Online News   | Web / news sites  |

## Planned Components

- Query Management
- Collector Engine
- Scheduler
- Data Pipeline
- Storage Layer
- Search Engine
- Dashboard API
- AI Insight Engine

## Technology Stack

| Component       | Technology                          |
|-----------------|-------------------------------------|
| Language        | Python 3.12+                        |
| Package Manager | [uv](https://docs.astral.sh/uv/)    |
| Version Control | Git                                 |
| IDE             | Cursor / VS Code                    |
| Database        | Planned                             |
| Search Engine   | Planned                             |

## Requirements

- Python **3.12+**
- [uv](https://docs.astral.sh/uv/) for dependency and project management

## Project Structure

```
aa_crawler/
├── config/              # Optional static configuration files; no secrets
├── data/
│   ├── raw/             # Unprocessed crawled data
│   ├── processed/       # Cleaned and transformed outputs
│   └── failed/          # Records that failed processing
├── docs/
│   ├── architecture/    # System design and component docs
│   ├── sprint/          # Sprint planning and notes
│   ├── adr/             # Architecture Decision Records
│   └── diagrams/        # Architecture and flow diagrams
├── logs/                # Runtime and application logs
├── scripts/             # Operational and utility scripts
├── src/
│   └── aa_crawler/      # Main application package
├── tests/               # Test suite
├── pyproject.toml       # Project metadata and dependencies
└── README.md
```

## Getting Started

### Clone the repository

```bash
git clone https://github.com/muhammadarifalfani/aa-crawler.git
cd aa_crawler
```

### Set up the environment

```bash
uv sync
```

This creates a virtual environment and installs project dependencies as defined in `pyproject.toml`.

## Sprint 2 application bootstrap

Application startup is explicit and uses the public bootstrap API:

```python
from pathlib import Path

from aa_crawler import bootstrap_application

settings = bootstrap_application(
    base_dir=Path("."),
    env_file=None,
    overrides={"logging": {"level": "INFO"}},
)
```

`env_file` is optional and is never discovered automatically. Configuration
sources have the following precedence, from highest to lowest:

1. Explicit overrides
2. OS environment variables
3. An explicitly supplied `.env` file
4. Model defaults

Bootstrap resolves runtime paths, prepares the required runtime directories,
and configures logging. None of these operations happen when the package is
imported.

### Supported environment variables

AA Crawler recognizes only the following application variables:

| Area | Variables |
|---|---|
| Core | `AA_ENV`, `AA_DEBUG`, `AA_DATA_DIR`, `AA_LOG_DIR`, `AA_CONFIG_DIR`, `AA_TEMP_DIR` |
| Logging | `AA_LOG_LEVEL`, `AA_LOG_CONSOLE_ENABLED`, `AA_LOG_FILE_ENABLED`, `AA_LOG_FORMAT`, `AA_LOG_FILE_NAME`, `AA_LOG_MAX_BYTES`, `AA_LOG_BACKUP_COUNT` |

Application variables must use the `AA_` prefix. Unknown `AA_` variables are
rejected, while unrelated non-`AA_` variables are ignored. `AA_HTTP_PROXY` and
`AA_HTTPS_PROXY` are reserved for future use and are not active. Never commit
secrets or a local `.env` file.

### Runtime paths

- `base_dir` is supplied explicitly.
- Relative runtime paths are anchored below `base_dir`; traversal outside it is rejected.
- Absolute paths remain absolute.
- Bootstrap prepares `data_dir` and `temp_dir` idempotently.
- `log_dir` is prepared only when file logging is enabled.
- `config_dir` is never created automatically.

### Logging and observability

The `aa_crawler` logger hierarchy writes text logs to stderr by default at
`INFO`. Optional UTF-8 file logging uses `aa-crawler.log`, rotates at 10 MiB,
and retains five backups; file logging is disabled by default. Missing
correlation context is rendered as `-`, and recognized sensitive values are
replaced with `[REDACTED]`. JSON logging and comprehensive PII detection are not
implemented. Logging is configured during bootstrap, never at import time.

## Roadmap

| Sprint | Focus | Status |
|--------|-------|--------|
| **Sprint 1** | Project Foundation — repository layout, documentation structure, tooling setup | **Completed** |
| **Sprint 2** | Configuration & Observability — configuration management, environment variables, runtime paths, logging, observability, application bootstrap | **Completed** |
| **Sprint 3** | Core Crawler Framework — base abstractions, crawler interface, plugin architecture | Planned |
| **Sprint 4** | Request Engine — HTTP client layer, rate limiting, retry logic, anti-bot handling | Planned |
| **Sprint 5** | Social Platform Crawlers — Instagram, Facebook, Threads | Planned |
| **Sprint 6** | Short-Form & Microblog Crawlers — TikTok, X (Twitter) | Planned |
| **Sprint 7** | Video & News Crawlers — YouTube, Online News | Planned |
| **Sprint 8** | Data Processing Pipeline — ingestion, normalization, validation, output to `data/processed/` | Planned |
| **Sprint 9** | Orchestration & Monitoring — job scheduling, health checks, failure handling via `data/failed/` | Planned |
| **Sprint 10** | Production Hardening — performance tuning, deployment, operational documentation | Planned |

## Documentation

Project documentation lives under `docs/`:

| Directory            | Purpose                                    |
|----------------------|--------------------------------------------|
| `docs/architecture/` | High-level system design and components    |
| `docs/sprint/`       | Sprint goals, tasks, and progress          |
| `docs/adr/`          | Architecture Decision Records              |
| `docs/diagrams/`     | Visual diagrams and workflow illustrations |

## Data Layout

| Path               | Purpose                                    |
|--------------------|--------------------------------------------|
| `data/raw/`        | Raw crawled content before transformation  |
| `data/processed/`  | Normalized and processed outputs           |
| `data/failed/`     | Failed records for inspection and retry    |

## License

This project is currently under active development.
The license will be determined before the first stable release.
