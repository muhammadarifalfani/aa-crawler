# Engineering Standards & Development Tooling

| Field            | Value                                      |
|------------------|--------------------------------------------|
| **Project**      | AA Crawler                                 |
| **Sprint**       | Living standard — aligned through implemented Sprint 5 scope |
| **Task**         | Engineering Standards & Development Tooling |
| **Status**       | Approved                                   |
| **Author**       | Engineering Team                           |
| **Last Updated** | 2026-08-11                                 |

---

## 1. Objectives

Maintain a consistent, enforceable engineering baseline for AA Crawler as the
project evolves. This document defines how the team writes, tests, formats,
commits, and manages dependencies so that crawlers, pipelines, storage, and
APIs share one foundation.

**Primary goals:**

- Define project-wide standards for code quality, Git workflow, and tooling.
- Select and document the development toolchain (formatter, linter, test runner, pre-commit hooks).
- Establish environment and dependency management practices using **uv** and **Python 3.12+**.
- Define a logging policy suitable for a long-running, multi-platform crawling system.
- Provide a clear **Definition of Done** for all future tasks and sprints.
- Ensure standards support the planned components: Query Management, Query Engine, Collector Engine, Scheduler, Data Pipeline, Storage Layer, Search Engine, Dashboard API, and AI Insight Engine.

---

## 2. Scope

### In Scope

- Engineering standards documentation (this document).
- Tooling selection and configuration strategy for:
  - Dependency management (`uv`)
  - Code formatting and linting (`ruff`)
  - Static type checking (`mypy`)
  - Testing framework (`pytest`)
  - Pre-commit hooks (`pre-commit`)
  - Environment variable management (`.env` conventions)
  - Logging configuration policy
- Git branching and commit conventions.
- Project layout conventions aligned with the existing `src/aa_crawler` structure.
- Developer onboarding workflow (`clone → uv sync → verify tooling`).

### Out of Scope

- Platform-specific crawler implementation.
- Database or search engine selection and setup (Sprint 2+).
- CI/CD pipeline configuration (deferred to a later sprint).
- Production deployment and infrastructure.
- Implementation of platform crawlers, scheduling, persistence, and other
  future product components.

---

## 3. Deliverables

| # | Deliverable | Location / Artifact |
|---|-------------|---------------------|
| 1 | Engineering standards design document | `docs/architecture/engineering-standards.md` |
| 2 | Tooling configuration — formatting & linting | `pyproject.toml` (`[tool.ruff]`, etc.) |
| 3 | Tooling configuration — type checking | `pyproject.toml` (`[tool.mypy]`) |
| 4 | Tooling configuration — testing | `pyproject.toml` (`[tool.pytest]`), `tests/` layout |
| 5 | Pre-commit hook configuration | `.pre-commit-config.yaml` |
| 6 | Environment template | `.env.example` |
| 7 | Updated `.gitignore` | Root `.gitignore` |
| 8 | Developer setup verification script (optional) | `scripts/verify_dev_setup.py` |
| 9 | Sprint 1 task completion record | `docs/sprint/sprint-1.md` |

All deliverables must be reviewed and approved before being merged to the main branch.

---

## 4. Project Standards

### 4.1 Repository Layout

The existing layout established in Task 1.4 is the canonical structure. All new code and configuration must respect these boundaries:

| Path | Purpose | Write Policy |
|------|---------|--------------|
| `src/aa_crawler/` | Application source code | Python packages and modules only |
| `tests/` | Test suite | Mirror `src/` structure |
| `config/` | Runtime configuration files | YAML/TOML/JSON; no secrets |
| `scripts/` | Operational and dev utility scripts | Standalone scripts |
| `docs/` | Documentation | Markdown, diagrams, ADRs |
| `data/raw/` | Raw crawled output | Generated at runtime; not committed |
| `data/processed/` | Processed output | Generated at runtime; not committed |
| `data/failed/` | Failed records | Generated at runtime; not committed |
| `logs/` | Application logs | Generated at runtime; not committed |

### 4.2 Naming Conventions

| Element | Convention | Example |
|---------|------------|---------|
| Python package | `snake_case` | `aa_crawler` |
| Python module | `snake_case` | `html_crawler.py` |
| Python class | `PascalCase` | `HtmlCrawler` |
| Python function / variable | `snake_case` | `fetch_posts()` |
| Python constant | `UPPER_SNAKE_CASE` | `MAX_RETRY_COUNT` |
| Test file | `test_<module>.py` | `test_html_crawler.py` |
| Test function | `test_<behavior>()` | `test_fetch_posts_returns_list()` |
| Config file | `snake_case` or `kebab-case` | `logging.yaml`, `dev-settings.toml` |
| Environment variable | `UPPER_SNAKE_CASE` prefixed with `AA_` | `AA_LOG_LEVEL`, `AA_ENV` |
| Git branch | `<type>/<short-description>` | `feat/collector-engine` |
| ADR file | `NNNN-<title>.md` | `0001-use-uv-for-dependencies.md` |

### 4.3 Module Organization

Source code under `src/aa_crawler/` is organized by explicit responsibility:

```
src/aa_crawler/
├── __init__.py
├── bootstrap.py       # Configuration, path, and logging bootstrap
├── application/       # Use-case coordination and runtime composition
│   ├── errors.py      # Narrow application error contracts
│   ├── service.py     # Single-article crawl orchestration
│   └── runtime.py     # Runtime graph and resource ownership
├── configuration/     # Settings, loading, and runtime paths
├── observability/     # Logging, context, and redaction
├── identity/          # Validated immutable request identity
├── crawler/           # Domain contracts and crawl lifecycle
├── http/              # Synchronous transport and policies
├── robots/            # robots.txt decisions
├── html/              # HTML acquisition and validation
├── contracts/         # Normalized application domain contracts
├── parser/            # Lazy parsing and generic article extraction
├── sources/           # Declarative source profiles and exact-host lookup
└── composition/       # Explicit source-to-parser construction
```

New modules must not be created until their sprint task authorizes them.

### 4.4 Documentation Standards

- All architectural decisions recorded as ADRs in `docs/adr/`.
- Sprint progress tracked in `docs/sprint/sprint-<N>.md`.
- Public APIs and complex modules require docstrings (Google style).
- README remains the project entry point; deep technical detail lives in `docs/architecture/`.

---

## 5. Architecture Principles

The following principles guide all design and implementation decisions across AA Crawler:

### Single Responsibility Principle

Each module, class, and function should have one clearly defined responsibility.
For example, an HTTP client performs transport, an HTML fetcher validates and
decodes content, a pipeline stage transforms data, and a storage adapter
persists it. Avoid combining unrelated concerns in one unit.

### Open/Closed Principle

Core abstractions (`BaseCrawler`, `BaseParser`, pipeline stages, and storage
adapters) must be open for extension but closed for incidental modification.
New platforms and data sources compose approved interfaces instead of
duplicating shared behavior.

### Composition over Inheritance

Prefer composing behavior from small, focused components rather than building
deep inheritance hierarchies. Use inheritance sparingly and only for true
is-a relationships such as `BaseCrawler`.

### Dependency Injection

Components receive their dependencies (HTTP clients, storage backends, configuration) via constructor injection or factory functions — not through global state or direct instantiation of concrete implementations. This enables testability and runtime flexibility.

### Configuration over Hardcode

Environment-specific operational values such as credentials, deployment URLs,
rate limits, and log levels must come from validated configuration. Approved
immutable policy defaults and reviewed static source-profile declarations may
live in source code when their ownership is documented by an ADR. Do not scatter
magic numbers, credentials, or unreviewed endpoints through runtime code.

### Explicit composition and dependency ownership

Runtime collaborators are supplied through constructor injection. Each
boundary has one owner: `HttpClient` owns transport, `RobotsPolicy` owns robots
decisions, `HtmlFetcher` owns HTML validation and decoding, `BaseParser` owns
parser output validation, `BaseCrawler` owns the crawl template lifecycle,
`SourceRegistry` owns source lookup, and `ParserComposer` owns parser
construction. `ArticleCrawlService` owns application-level coordination, while
`ApplicationRuntime` and `create_application_runtime()` own runtime composition
and resource lifetime. Service locators, mutable global registries, and implicit
global dependency construction are prohibited.

### Synchronous crawler architecture

- Crawler contracts are immutable and slotted, with defensive top-level copies
  for mapping inputs.
- HTTPX is isolated behind `HttpClient`; domain metadata must not configure
  transport behavior.
- `TimeoutPolicy` and `RetryPolicy` are explicit constructor dependencies.
- `RetryPolicy` owns automatic retry eligibility. Only GET and HEAD may receive
  bounded retries; every other method receives one physical transport attempt.
  Request metadata and higher layers cannot broaden eligibility.
- Retry behavior uses the bounded status and transient-exception policy,
  deterministic exponential backoff, and no jitter or `Retry-After` handling.
- `RobotsPolicy` is the only robots authority used by HTML acquisition.
- `HtmlFetcher` performs deterministic content-type validation and strict
  decoding.
- `BaseParser` lazily yields and validates `CrawlerItem` values.
- `BaseCrawler` owns ordered, lazy, fail-fast request processing.
- The protected `_process_request` seam is the approved specialization point;
  the default lifecycle remains unchanged.
- `HtmlCrawler` composes `HtmlFetcher` and `BaseParser` and performs exactly one
  page transport request per configured URL.

### Request identity

- `RequestIdentity` is the immutable validated runtime-scoped identity.
  Product, version, project URL, and optional contact remain distinct values.
- One injected identity supplies the same User-Agent for robots retrieval,
  robots evaluation, and page retrieval through `RobotsPolicy` and
  `HtmlFetcher`.
- `HttpClient` remains identity-neutral. Acquisition components must not own
  duplicate raw User-Agent values.
- Browser or third-party crawler impersonation and User-Agent rotation are not
  permitted. The runtime composition root supplies the installed distribution
  version from `importlib.metadata.version("aa-crawler")`. Operational contact
  policy and any approved CLI override remain future concerns.

### Article and parser contracts

- `ArticleItem` is the normalized immutable article contract. Its requested
  URL and canonical URL remain distinct, and article-body extraction is not
  part of the current generic contract.
- `JsonLdArticleParser` remains source-agnostic. It prefers JSON-LD
  `NewsArticle` over generic `Article` and receives the source identifier and
  exact approved hosts through composition.
- Parser and source tests use synthetic HTML and metadata. Copied live page
  content is not the default fixture strategy.

### Declarative source architecture

- `SourceProfile` contains immutable declarative source metadata only: stable
  identifier, ordered exact hosts, parser family, inert adapter key, and
  enabled state.
- `SourceRegistry` performs immutable exact source, hostname, and safe HTTPS URL
  lookup. It uses no wildcard, suffix, or implicit subdomain matching and
  excludes disabled profiles from normal lookup.
- `ParserComposer` constructs parsers only. Parser-family mapping is explicit
  and static; reflection, dynamic imports, entry points, and plugin scanning
  are prohibited until separately approved.
- Ordinary compatible sources are added profile-first and reuse the generic
  parser. A publisher-specific parser or adapter requires observed evidence;
  non-null adapter keys remain unsupported.

Profile existence does not authorize network crawling. `enabled=True` makes a
source available to normal lookup; `enabled=False` retains known state while
blocking normal lookup and composition. Enablement does not replace robots.txt,
publisher-policy or legal review, rate limits, or operational safety controls.
The current reference declarations enable CNN Indonesia and disable Kompas;
these values are project governance state, not universal policy.

| Source | Exact hosts | Parser family | Adapter key | Enabled |
|--------|-------------|---------------|-------------|---------|
| CNN Indonesia | `www.cnnindonesia.com` | `jsonld_article` | `None` | Yes |
| Kompas | `www.kompas.com`, `nasional.kompas.com`, `surabaya.kompas.com` | `jsonld_article` | `None` | No |

The Sprint 4 source-composition integration remains a supported lower-level
flow:

```text
URL
  → SourceRegistry
  → SourceProfile
  → ParserComposer
  → JsonLdArticleParser
  → ArticleItem
  → CrawlerItem
```

It assumes an existing `HtmlDocument` and intentionally performs no live
networking.

### Application orchestration

`ArticleCrawlService` is the synchronous application boundary for crawling one
article URL. It receives an exact `SourceRegistry`, `HtmlFetcher`, and
`ParserComposer`; it does not construct or close those collaborators.

Its implemented sequence is:

```text
requested URL
  → enabled source lookup
  → robots-aware HTML acquisition
  → final URL lookup
  → exact same-profile validation
  → parser composition
  → parsing
  → tuple[CrawlerItem, ...]
```

The initial lookup occurs before acquisition. Malformed, non-HTTPS, unknown,
and disabled sources raise `UnsupportedSourceError` before any acquisition.
After acquisition, the final URL must resolve through the same authoritative
registry to the exact originally selected `SourceProfile`. Transitions between
the profile's declared exact hosts are allowed; a missing, disabled, or
different final profile raises `SourceBoundaryError`. Parser construction
occurs only after this gate. Parser order and zero-or-more cardinality are
preserved in an eager immutable tuple.

`SourceBoundaryError` governs registered source ownership, not canonical URL
interpretation. `JsonLdArticleParser` and `ArticleItem` remain responsible for
canonical semantics. Existing subsystem exceptions propagate without broad
application wrapping.

`ArticleCrawlService` forwards caller metadata to acquisition unchanged.
Metadata does not control source selection, retry eligibility, identity,
parser selection, or source governance. Automatic redirect following remains
unimplemented.

The application error hierarchy is:

```text
CrawlerError
└── ApplicationError
    ├── UnsupportedSourceError
    └── SourceBoundaryError
```

These errors use concise deterministic messages and do not retain rejected
URLs, source data, responses, or metadata.

### Application runtime composition

`create_application_runtime()` constructs one independent synchronous
`ApplicationRuntime`. The frozen, slotted runtime exposes only
`article_crawl_service` as its application service and provides explicit
`close()` plus synchronous context-manager support. It is not a singleton,
service locator, mutable registry, or global default runtime.

The implemented construction order is:

1. Resolve `importlib.metadata.version("aa-crawler")`.
2. Construct one `RequestIdentity`.
3. Construct `TimeoutPolicy` and `RetryPolicy`.
4. Construct `SourceRegistry(DEFAULT_SOURCE_PROFILES)` and `ParserComposer`.
5. Create and enter one `HttpClient` under a private `ExitStack`.
6. Construct `RobotsPolicy` and `HtmlFetcher` with the same exact identity.
7. Construct `ArticleCrawlService` with the runtime-local registry, fetcher,
   and composer.
8. Transfer cleanup ownership into `ApplicationRuntime`.

`RequestIdentity` is not injected into `HttpClient`. Exactly one runtime owns
each created client; `RobotsPolicy`, `HtmlFetcher`, and `ArticleCrawlService`
use but do not close it. Context exit and explicit close release owned
resources, repeated close is harmless, and failure after client acquisition
closes the client while preserving the original construction exception. A
partially built runtime does not escape.

Every runtime receives fresh identity, transport, robots policy, fetcher,
registry, composer, and service instances. Immutable profile declarations may
be reused as constructor input, but mutable runtime state is not shared.

`bootstrap_application()` and `create_application_runtime()` remain separate.
The former returns `ApplicationSettings` after configuration, path, and logging
startup; the latter accepts no settings and owns the synchronous network
runtime graph. Neither implicitly calls the other.

Actual dependency direction remains explicit: neutral crawler and article
contracts support transport and parsing; robots and HTML acquisition depend on
HTTP and request identity; parsing consumes HTML contracts; source profiles are
declarative; composition depends on sources and parsers; and the application
layer coordinates those public boundaries without creating circular ownership.

Crawler package boundaries, contract fields, source/composition seams, and
Sprint 3–4 public APIs remain partially provisional under
[ADR-011](../adr/0011-sprint-4-api-and-package-policy.md). Mature Sprint 2
configuration and primary observability APIs remain frozen.

ADR-014 (user-agent ownership), ADR-015 (retry idempotency), ADR-020
(declarative source architecture), ADR-021 (application-level article crawl
orchestration), and ADR-022 (application runtime composition and resource
ownership) are Accepted and implemented. ADR-016 (logging-redaction scope) and
ADR-019 (future execution families) remain Proposed. ADR-017 (metadata
portability) and ADR-018 (error-root taxonomy) remain Deferred. Current totals
are 15 Accepted, 2 Proposed, 2 Deferred, and 0 Superseded.

Async execution, browser automation, dynamic plugins, distributed crawling,
workers, queues, metrics, tracing, persistence, scheduling, thread-safety
guarantees, automatic redirects, and live profile reload remain unimplemented
or conditional future work.

### Public API discipline

- Package `__all__` declarations define intentional public surfaces.
- Source and composition APIs remain minimal and responsibility-specific.
- The `aa_crawler.application` public surface is exactly `ApplicationError`,
  `ApplicationRuntime`, `ArticleCrawlService`, `SourceBoundaryError`,
  `UnsupportedSourceError`, and `create_application_runtime`.
- Do not introduce premature compatibility aliases, mutable global registries,
  service locators, or unapproved convenience orchestration methods.

---

## 6. Coding Standards

### 6.1 Language & Runtime

- **Python 3.12+** is required. Pin the version in `.python-version`.
- Use modern Python features where they improve clarity: type hints, `pathlib`, structural pattern matching where appropriate.
- Prefer the standard library before adding third-party dependencies.

### 6.2 Type Hints

- All public functions, methods, and class attributes must have type annotations.
- Use `from __future__ import annotations` in modules where forward references are needed.
- Avoid `Any` unless justified and documented.
- Return types must be explicit; use `-> None` for procedures.

### 6.3 Docstrings

- Use **Google-style** docstrings for all public modules, classes, and functions.
- Docstrings must describe purpose, arguments, return values, and raised exceptions where applicable.
- Internal/private helpers (`_prefixed`) require docstrings only when behavior is non-obvious.

### 6.4 Error Handling

- Raise specific, domain-appropriate exceptions; never silently swallow errors.
- Use custom exception hierarchies per domain (e.g., `CollectorError`, `PipelineError`) once those modules exist.
- Log exceptions at appropriate levels before re-raising or handling.
- Do not use bare `except:` clauses.

### 6.5 Imports

- Order: standard library → third-party → local (`aa_crawler`).
- One import per line for `from` imports.
- No wildcard imports (`from module import *`).
- Enforced automatically by `ruff` (isort rules).

### 6.6 Complexity & Size

- Functions should do one thing; target ≤ 40 lines.
- Modules should remain focused; split when exceeding ~300 lines.
- Cyclomatic complexity monitored via `ruff` (`C901` rule, max complexity = 10).

### 6.7 Security

- Secrets must never be committed. Use environment variables loaded from `.env` (local) or a secrets manager (production).
- Validate and sanitize all external input (URLs, API responses, user queries).
- Crawler credentials stored only in environment variables or secure vaults — never in source code or config files committed to Git.

---

## 7. Git Workflow

### 7.1 Branching Model

Use a simplified **GitHub Flow** model:

| Branch | Purpose |
|--------|---------|
| `main` | Stable, always deployable baseline |
| `feat/<description>` | New features |
| `fix/<description>` | Bug fixes |
| `docs/<description>` | Documentation-only changes |
| `chore/<description>` | Tooling, dependencies, maintenance |
| `test/<name>` | Test changes (for example, `test/collector-contract`) |

Direct commits to `main` are discouraged. All changes go through pull requests.

### 7.2 Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short summary>

[optional body]

[optional footer]
```

**Types:** `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `ci`, `perf`

**Examples:**

```
feat(collector): add base crawler interface
fix(pipeline): handle empty response from API
docs(architecture): add engineering standards design
chore(tooling): configure ruff and pre-commit hooks
```

- Subject line: ≤ 72 characters, imperative mood, no trailing period.
- Body: explain *why*, not *what* (the diff shows what).

### 7.3 Pull Request Process

1. Create a feature branch from `main`.
2. Implement changes; ensure all pre-commit hooks pass locally.
3. Open a PR with:
   - Clear title matching commit convention.
   - Description: what changed, why, and how to test.
   - Link to relevant sprint task or issue.
4. At least one reviewer approval required before merge.
5. Squash merge preferred to keep `main` history clean.

### 7.4 Protected Paths

The following require explicit review and must not be changed casually:

- `pyproject.toml` — dependency and tooling changes
- `.pre-commit-config.yaml` — hook changes
- `docs/adr/` — architectural decisions
- `.gitignore` — ignore rule changes

---

## 8. Dependency Management Strategy

### 8.1 Tool: uv

[uv](https://docs.astral.sh/uv/) is the sole package and environment manager. Do not use `pip`, `pipenv`, or `poetry` directly.

| Action | Command |
|--------|---------|
| Install all dependencies | `uv sync` |
| Add a runtime dependency | `uv add <package>` |
| Add a dev dependency | `uv add --dev <package>` |
| Remove a dependency | `uv remove <package>` |
| Update lockfile | `uv lock` |
| Run a command in the venv | `uv run <command>` |

### 8.2 Dependency Groups

Dependencies are organized in `pyproject.toml`:

| Group | Purpose | Current packages |
|-------|---------|------------------|
| `dependencies` | Runtime packages | `httpx>=0.28.1,<0.29`, `pydantic>=2.13.4,<3`, `pydantic-settings>=2.14.2,<2.15` |
| `[dependency-groups] dev` | Development tooling | `ruff`, `pytest`, `mypy`, `pre-commit` |

Dev dependencies must never be imported in runtime code under `src/`.

### 8.3 Version Pinning

- Runtime dependencies: use the approved compatible range recorded in
  `pyproject.toml`, or an exact pin when risk requires it.
- Dev dependencies: pin to major version ranges acceptable for tooling.
- Lockfile (`uv.lock`) is committed starting in Sprint 1 and must be maintained whenever approved dependencies change to ensure reproducible environments.
- Dependency updates are intentional — no drive-by upgrades in feature PRs.

### 8.4 Dependency Review

- New runtime dependencies require justification in the PR description.
- Prefer well-maintained, widely adopted packages.
- Evaluate license compatibility before adding.
- Avoid dependencies that duplicate functionality already in the standard library.

---

## 9. Environment Management

### 9.1 Local Development

| Item | Convention |
|------|------------|
| Virtual environment | Managed by `uv` at `.venv/` (git-ignored) |
| Python version | Pinned in `.python-version` (currently `3.12`) |
| Environment variables | OS environment first; optional explicit `.env` for local use |
| Environment template | `.env.example` committed with safe development values and no secrets |

Configuration is loaded once at the application composition root into one frozen settings instance. Components receive that instance or narrower subsystem settings through dependency injection; modules must not create a global settings singleton or read environment variables independently.

Configuration sources use this precedence, from highest to lowest:

1. Explicit constructor or test overrides.
2. OS environment variables.
3. An explicitly selected `.env` file.
4. Model defaults.

`.env` loading must be explicit. The application must not search parent directories automatically, OS environment variables must override `.env`, and production must not load `.env` automatically.

Unknown variables using the `AA_` namespace are rejected to catch deployment
mistakes. Environment variables outside the `AA_` namespace are ignored by the
application settings loader.

### 9.2 Environment Variable Naming

All application environment variables use the `AA_` prefix:

| Variable | Purpose | Example Value |
|----------|---------|---------------|
| `AA_ENV` | Environment name | `development`, `testing`, `staging`, `production` |
| `AA_DEBUG` | Application diagnostics | `false` |
| `AA_LOG_LEVEL` | Logging verbosity | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `AA_LOG_DIR` | Log output directory | `logs/` |
| `AA_DATA_DIR` | Base data directory | `data/` |
| `AA_CONFIG_DIR` | Static configuration directory | `config/` |
| `AA_TEMP_DIR` | Temporary working directory | `.tmp/` |
| `AA_LOG_CONSOLE_ENABLED` | Enable stderr logging | `true` |
| `AA_LOG_FILE_ENABLED` | Enable rotating file logging | `false` |
| `AA_LOG_FORMAT` | Logging output format | `text` |
| `AA_LOG_FILE_NAME` | Rotating log filename | `aa-crawler.log` |
| `AA_LOG_MAX_BYTES` | File rotation threshold | `10485760` (10 MiB) |
| `AA_LOG_BACKUP_COUNT` | Rotated backup count | `5` |

Future application proxy settings use `AA_HTTP_PROXY` and `AA_HTTPS_PROXY`. Unprefixed `HTTP_PROXY` and `HTTPS_PROXY` are not AA Crawler settings; HTTP clients receive validated proxy settings explicitly.

### 9.3 Runtime Paths and Configuration Bootstrap

`bootstrap_application()` is the explicit configuration, path, and logging
bootstrap. Its startup order is:

```text
load_settings
→ prepare_runtime_directories
→ configure_logging
```

`base_dir` is supplied explicitly. Relative runtime paths are normalized and
must remain below `base_dir`; absolute paths remain absolute. Path resolution
does not require paths to exist and performs no filesystem writes.

Directory preparation is a separate, idempotent startup operation. It always
prepares `data_dir` and `temp_dir`, prepares `log_dir` only when file logging is
enabled, and never creates `config_dir`. The same frozen settings instance is
passed through directory preparation and logging configuration. Imports must
not load settings, create directories, configure logging, or cache settings.

The bootstrap returns that `ApplicationSettings` instance. It does not create
or own `HttpClient`, `RobotsPolicy`, `HtmlFetcher`, `SourceRegistry`,
`ParserComposer`, `ArticleCrawlService`, or `ApplicationRuntime`. Runtime graph
composition and cleanup belong separately to `create_application_runtime()`.

### 9.4 Environment Separation

| Environment | Config Source | Data | Logging |
|-------------|--------------|------|---------|
| Development | Explicit `.env`, OS environment, and defaults | Local `data/` dirs | Console to stderr; file disabled by default |
| Testing | Explicit overrides, isolated `.env`, or OS environment | Temporary isolated dirs | Console to stderr; file disabled by default |
| Staging | OS environment variables | Isolated storage | Console to stderr; file explicitly enabled when required |
| Production | Secrets manager / env vars | Managed storage | `WARNING`+ to centralized log |

### 9.5 Secrets Policy

- `.env` is listed in `.gitignore` and must never be committed.
- `.env.example` documents approved variables with safe development values and no secrets.
- Production secrets are injected at runtime — never baked into images or config files.

---

## 10. Logging Policy

### 10.1 Objectives

AA Crawler is a long-running, multi-platform system. Logging must support debugging failed crawls, auditing data pipeline stages, and operational monitoring.

### 10.2 Log Levels

| Level | Usage |
|-------|-------|
| `DEBUG` | Detailed diagnostic output; development only |
| `INFO` | Normal operational events (crawl started, batch processed, job scheduled) |
| `WARNING` | Recoverable issues (rate limit hit, retry triggered, partial data) |
| `ERROR` | Failures requiring attention (crawl failed, pipeline exception, storage unreachable) |
| `CRITICAL` | System-level failures (configuration invalid, cannot start) |

The default level is `INFO`. `AA_LOG_LEVEL` controls the effective level independently of `AA_DEBUG`.

### 10.3 Log Format

The implemented text format is:

```
%(asctime)s | %(levelname)s | %(name)s | %(correlation_id)s | %(message)s
```

Example:

```
2026-08-03T14:22:01+0700 | INFO | aa_crawler.collectors.instagram | job-42 | Fetched 50 posts
```

Structured JSON logging is deferred until the Dashboard API and centralized monitoring are implemented (Sprint 9+).

### 10.4 Log Output

| Output | Location | Rotation |
|--------|----------|----------|
| Console (stderr) | Enabled by default in every environment | N/A |
| File | Disabled by default; `logs/` when explicitly enabled | Size-based rotation (10 MiB, 5 backups) |

Log files are git-ignored. The `logs/` directory is tracked via `.gitkeep`.
Failure to initialize explicitly enabled file logging is fatal.

Handlers are attached only to the `aa_crawler` logger hierarchy. Console logs
use stderr. AA Crawler-owned handlers are replaced safely during
reconfiguration without removing unrelated handlers or propagating records to
the root logger.

### 10.5 Logging Rules

- Use the module-level logger: `logger = logging.getLogger(__name__)`.
- Never use `print()` in application code (except CLI user-facing output in `main()`).
- Include contextual information in log messages: platform, query ID, batch size, duration.
- Do not log secrets, tokens, or full API responses containing PII.
- Exceptions must be logged with `logger.exception()` or `exc_info=True`.
- Correlation IDs use `ContextVar` so concurrent and asynchronous contexts do
  not leak state. When no ID exists, logs use `-`; IDs are never generated
  automatically.
- Recognized secret-bearing key/value pairs are replaced deterministically with
  `[REDACTED]` before owned handlers emit them. This is defensive secret
  filtering, not arbitrary PII detection.

### 10.6 Logger Hierarchy

```
aa_crawler                          # Root application logger
├── aa_crawler.application           # Use-case and runtime composition
├── aa_crawler.configuration       # Settings and runtime paths
├── aa_crawler.observability       # Logging context and redaction
├── aa_crawler.identity            # Request identity
├── aa_crawler.crawler             # Contracts and crawl lifecycle
├── aa_crawler.http                # Synchronous transport
├── aa_crawler.robots              # robots.txt policy
├── aa_crawler.html                # HTML acquisition
├── aa_crawler.contracts           # Normalized domain contracts
├── aa_crawler.parser              # Parser framework
├── aa_crawler.sources             # Source profiles and registry
└── aa_crawler.composition         # Parser construction
```

---

## 11. Testing Strategy

### 11.1 Framework

**pytest** is the standard test runner. No `unittest`-style test classes unless integrating with a library that requires them.

### 11.2 Test Layout

```
tests/
├── application/             # Error, service, and runtime unit tests
├── configuration/           # Package-focused unit tests
├── crawler/                 # Domain and lifecycle tests
├── http/                    # Transport-policy tests with mock transport
├── identity/                # Request-identity tests
├── robots/                  # Robots-policy tests
├── html/                    # Acquisition-contract tests
├── contracts/               # Normalized contract tests
├── parser/                  # Parser lifecycle and synthetic metadata tests
├── sources/                 # Profile and exact-registry tests
├── composition/             # Parser-construction tests
└── integration/             # Cross-package synthetic integration tests
```

Test files mirror the `src/aa_crawler/` module structure.

### 11.3 Test Categories

| Category | Scope | Network | Speed | When Required |
|----------|-------|---------|-------|---------------|
| Unit | Single function/class | Mocked | Fast | Every public function |
| Integration | Module interaction | Mocked or local | Medium | Pipeline, storage boundaries |
| End-to-end | Full crawl → process flow | Live (staging) | Slow | Sprint 9+ |

Tests cover configuration, paths, observability, identity, crawler contracts,
HTTP policy, robots, HTML acquisition, article contracts, parsing, source
lookup, parser composition, application errors and orchestration, runtime
composition, and bootstrap integration. Tests must isolate environment
variables, logging and correlation state, and filesystem writes; use `tmp_path`
for runtime paths.

Sprint 4 integration tests use synthetic HTML to exercise source resolution and
parser composition. They assume document acquisition and intentionally do not
instantiate live networking components.

Sprint 5 adds application crawl and runtime composition integration tests.
These remain synthetic and network-isolated while verifying real package
boundaries. Durable coverage includes source gates, metadata forwarding,
runtime construction order, installed-version ordering, identity reuse,
context and explicit cleanup, repeated close, partial-construction cleanup,
runtime independence, and bootstrap separation. Documentation must describe
these architecture facts rather than transient test counts.

### 11.4 Coverage Targets

| Phase | Target |
|-------|--------|
| Enforced repository minimum | ≥ 70% |
| Sprint 4–8 engineering target | ≥ 80% |
| Sprint 9–10 (production) | ≥ 90% |

The enforced minimum comes from `pyproject.toml`; higher phase targets guide
engineering improvement without misrepresenting the active quality gate.
Coverage is measured with `pytest-cov` and reported in CI when configured.

### 11.5 Testing Rules

- Tests must be deterministic — no reliance on wall-clock time, random values, or network without mocking.
- Use `pytest fixtures` for shared setup; avoid global state.
- Name tests to describe behavior: `test_fetch_posts_returns_empty_list_when_no_results`.
- Mock external HTTP calls with the installed HTTPX mock transport.
- Test data files live in `tests/fixtures/` and must not contain real credentials or PII.
- Prefer synthetic HTML and metadata for parser, source, and integration tests.
- Normal test execution must not access external networks.
- Retry tests must replace sleeping with deterministic test doubles.
- Run Ruff, Ruff format check, mypy, pytest, coverage, and pre-commit across the
  repository before merge.

### 11.6 Running Tests

```bash
uv run pytest                    # Run all tests
uv run pytest tests/http/         # Focused package tests
uv run pytest -v --cov=aa_crawler  # With coverage report
```

---

## 12. Formatting & Linting Strategy

### 12.1 Tools

| Tool | Purpose | Config Location |
|------|---------|-----------------|
| **Ruff** | Linting + formatting (replaces black, isort, flake8) | `pyproject.toml` `[tool.ruff]` |
| **mypy** | Static type checking | `pyproject.toml` `[tool.mypy]` |

Ruff is the primary tool to minimize toolchain complexity.

### 12.2 Ruff Configuration

| Setting | Value | Rationale |
|---------|-------|-----------|
| Line length | 88 | Consistent with Black convention |
| Target Python | `py312` | Matches project requirement |
| Quote style | Double quotes | Enforced by formatter |
| Import sorting | Enabled (isort rules) | Consistent import order |
| Selected rules | `E`, `F`, `W`, `I`, `N`, `UP`, `B`, `C4`, `SIM`, `TCH` | Errors, warnings, imports, naming, pyupgrade, bugbear, comprehensions, simplify, type-checking |

### 12.3 Pre-Commit Hooks

`.pre-commit-config.yaml` enforces checks before every commit:

| Hook | Action |
|------|--------|
| `ruff check` | Lint |
| `ruff format` | Format |
| `mypy` | Type check (staged files or full project) |
| Trailing whitespace | Remove |
| End-of-file fixer | Ensure newline at EOF |
| YAML / TOML validation | Syntax check |
| Repository hygiene | Detect merge markers, malformed configuration, trailing whitespace, and oversized files |

Install hooks:

```bash
uv run pre-commit install
```

### 12.4 Manual Commands

```bash
uv run ruff check .              # Lint
uv run ruff check . --fix        # Lint with auto-fix
uv run ruff format .             # Format
uv run mypy src/                 # Type check
```

### 12.5 Enforcement

- Pre-commit hooks are **mandatory** for all contributors.
- CI (when configured) will run the same checks — a PR cannot merge with lint or type errors.
- Formatting debates are resolved by tooling, not review comments.

---

## 13. Definition of Done

A task or sprint item is **Done** when all of the following are satisfied:

| # | Criterion |
|---|-----------|
| 1 | Code implements the agreed scope — no more, no less |
| 2 | All new public functions and classes have type hints and docstrings |
| 3 | Unit tests written and passing for new logic |
| 4 | `uv run ruff check .` passes with zero errors |
| 5 | `uv run ruff format --check .` passes |
| 6 | `uv run mypy` passes for the configured repository scope |
| 7 | Pre-commit hooks pass locally |
| 8 | No secrets, credentials, or `.env` values committed |
| 9 | Documentation updated if behavior, config, or architecture changed |
| 10 | ADR written if an architectural decision was made |
| 11 | PR reviewed and approved |
| 12 | Sprint notes updated in `docs/sprint/sprint-<N>.md` |

For **Sprint 1 Task 2** specifically, Done means: tooling is configured, this document is finalized, `.env.example` exists, pre-commit hooks are installable, and a developer can run `uv sync && uv run pre-commit run --all-files` successfully.

---

## 14. Risks

| # | Risk | Impact | Likelihood | Mitigation |
|---|------|--------|------------|------------|
| 1 | Tooling configuration drift between developers | Inconsistent code quality, merge conflicts | Medium | Lock tooling versions in `pyproject.toml`; enforce via pre-commit |
| 2 | Over-engineering standards before features exist | Slowed development, unused rules | Medium | Start with minimal rule set; expand as codebase grows |
| 3 | `uv` ecosystem immaturity vs pip/poetry | Onboarding friction for new contributors | Low | Document setup clearly in README; provide `scripts/verify_dev_setup.py` |
| 4 | Pre-commit hooks slow down commits | Developer frustration, hooks bypassed | Medium | Keep hooks fast (< 10s); use `--no-verify` only in emergencies with team agreement |
| 5 | Type checking too strict too early | Blocks progress on exploratory code | Medium | Start with moderate mypy strictness; tighten per module as they stabilize |
| 6 | Logging volume from crawlers overwhelms disk | Operational issues in production | Medium | Define rotation policy early; plan centralized logging for Sprint 9 |
| 7 | Secrets accidentally committed | Security breach | Low | Pre-commit secret detection hook; `.env` in `.gitignore`; PR review checklist |
| 8 | Dependency bloat as platforms are added | Large attack surface, slow installs | Medium | Require dependency justification in PRs; periodic audit |
| 9 | Anti-bot detection, rate limiting, CAPTCHA, and platform blocking | Crawlers fail or produce incomplete data; increased maintenance burden | High | Preserve transport and robots boundaries; resolve identity and proxy policy through ADR review before production crawling |

---

## 15. Future Extensibility

The standards defined in this document are designed to scale with the AA Crawler roadmap.

### 15.1 Component Readiness

| Planned Component | Standards Support |
|-------------------|-------------------|
| **Query Management** | Typed interfaces and validated configuration foundation |
| **Query Engine** | Composable query builder; typed query models; unit-tested parsing and validation |
| **Crawler framework** | Synchronous contracts, application orchestration, and explicitly owned runtime lifecycle |
| **Scheduler** | Logging of job lifecycle events; testable with mocked clock |
| **Data Pipeline** | Stage-level logging; unit + integration test categories |
| **Storage Layer** | Abstract interface; integration tests against local/test storage |
| **Search Engine** | Index schema documented in ADR; integration test fixtures |
| **Dashboard API** | API-specific lint rules; OpenAPI schema generation |
| **AI Insight Engine** | Separate module; model I/O logging without PII |

### 15.2 Tooling Evolution

| Sprint | Engineering state |
|--------|-------------------|
| Sprint 2 | Completed configuration, runtime-path, observability, and bootstrap foundation |
| Sprint 3 | Completed synchronous crawler, HTTP, robots, HTML, parser, and composition foundation |
| Sprint 4 | Completed identity, retry safety, article parsing, declarative sources, and documentation closure |
| Sprint 5 | Application orchestration and runtime composition implemented; documentation closure and final verification in progress |
| Sprint 8 | Data validation schemas, pipeline test fixtures |
| Sprint 9 | CI pipeline (GitHub Actions), coverage reporting, structured JSON logging |
| Sprint 10 | Performance benchmarks, security scanning (`bandit`), dependency audit automation |

### 15.3 ADR Triggers

An Architecture Decision Record must be created when:

- A new runtime dependency is introduced for a core component.
- A logging, storage, or messaging technology is selected.
- A breaking change to the module structure or public API is proposed.
- A deviation from these standards is required.

`docs/adr/` is the canonical ADR location. Files use an immutable four-digit
sequence and a lowercase kebab-case title, such as
`0001-configuration-source-precedence.md`; documents display the corresponding
decision as `ADR-001`.

ADR statuses are:

- **Accepted** — approved and part of the supported architecture.
- **Proposed** — under review; no decision is approved yet.
- **Deferred** — intentionally postponed until a documented trigger occurs.
- **Superseded** — replaced by a later ADR that preserves the historical record.

Accepted ADRs are never renumbered or silently rewritten. When an accepted
decision changes, create a new ADR that supersedes the historical decision.
Review the ADR index and all Proposed or triggered Deferred ADRs during sprint
closure.

### 15.4 Standards Review

This document will be reviewed and updated at the end of each sprint to reflect lessons learned and tooling changes. The goal is a living standard — not a one-time artifact.

---

## Appendix A: Quick Reference

```bash
# Setup
git clone https://github.com/muhammadarifalfani/aa-crawler.git
cd aa_crawler
uv sync
uv run pre-commit install

# Daily development
uv run ruff check . --fix     # Lint and fix
uv run ruff format .          # Format
uv run mypy src/              # Type check
uv run pytest                 # Test
uv run pre-commit run --all-files  # Run all hooks manually

# Dependencies
uv add <package>              # Add runtime dep
uv add --dev <package>        # Add dev dep
uv lock                       # Update lockfile
```

## Appendix B: Related Documents

| Document | Location |
|----------|----------|
| Project README | `README.md` |
| Sprint 1 Notes | `docs/sprint/sprint-1.md` |
| Sprint 2 Notes | `docs/sprint/sprint-2.md` |
| Sprint 3 Notes | `docs/sprint/sprint-3.md` |
| Architecture Decision Records | `docs/adr/` |
| Sprint Roadmap | `README.md` § Roadmap |
