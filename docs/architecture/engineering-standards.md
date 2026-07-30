# Engineering Standards & Development Tooling

| Field            | Value                                      |
|------------------|--------------------------------------------|
| **Project**      | AA Crawler                                 |
| **Sprint**       | Sprint 1 — Project Foundation              |
| **Task**         | Task 2 — Engineering Standards & Development Tooling |
| **Status**       | Approved                                   |
| **Author**       | Engineering Team                           |
| **Last Updated** | 2026-07-30                                 |

---

## 1. Objectives

Establish a consistent, enforceable engineering baseline for AA Crawler before feature development begins. This task defines how the team writes, tests, formats, commits, and manages dependencies so that future sprints — crawlers, pipelines, storage, and APIs — can be built on a shared foundation.

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

- Crawler or platform-specific implementation.
- Database or search engine selection and setup (Sprint 2+).
- CI/CD pipeline configuration (deferred to a later sprint).
- Production deployment and infrastructure.
- Implementation of planned components (Collector Engine, Scheduler, etc.).

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
| Python module | `snake_case` | `collector_engine.py` |
| Python class | `PascalCase` | `CollectorEngine` |
| Python function / variable | `snake_case` | `fetch_posts()` |
| Python constant | `UPPER_SNAKE_CASE` | `MAX_RETRY_COUNT` |
| Test file | `test_<module>.py` | `test_collector_engine.py` |
| Test function | `test_<behavior>()` | `test_fetch_posts_returns_list()` |
| Config file | `snake_case` or `kebab-case` | `logging.yaml`, `dev-settings.toml` |
| Environment variable | `UPPER_SNAKE_CASE` prefixed with `AA_` | `AA_LOG_LEVEL`, `AA_ENV` |
| Git branch | `<type>/<short-description>` | `feat/collector-engine` |
| ADR file | `NNNN-<title>.md` | `0001-use-uv-for-dependencies.md` |

### 4.3 Module Organization

Source code under `src/aa_crawler/` will grow by domain as sprints progress. Top-level modules should reflect planned components:

```
src/aa_crawler/
├── __init__.py
├── collectors/        # Platform-specific crawlers (Sprint 5–7)
├── pipeline/          # Data processing pipeline (Sprint 8)
├── scheduler/         # Job scheduling (Sprint 9)
├── storage/           # Storage layer abstractions (Sprint 8+)
├── query/             # Query management (Sprint 3+)
├── api/               # Dashboard API (future sprint)
├── insights/          # AI Insight Engine (future sprint)
├── config/            # Settings and environment loading (Sprint 2)
└── logging/           # Logging setup and utilities (Sprint 2)
```

New modules must not be created until their sprint task authorizes them. During Sprint 1, only tooling-related changes are permitted.

### 4.4 Documentation Standards

- All architectural decisions recorded as ADRs in `docs/adr/`.
- Sprint progress tracked in `docs/sprint/sprint-<N>.md`.
- Public APIs and complex modules require docstrings (Google style).
- README remains the project entry point; deep technical detail lives in `docs/architecture/`.

---

## 5. Architecture Principles

The following principles guide all design and implementation decisions across AA Crawler:

### Single Responsibility Principle

Each module, class, and function should have one clearly defined responsibility. For example, a platform collector fetches data; a pipeline stage transforms it; a storage adapter persists it. Avoid combining unrelated concerns in a single unit.

### Open/Closed Principle

Core abstractions (base collector, pipeline stage, storage adapter) must be open for extension but closed for modification. New platforms and data sources are added by implementing existing interfaces — not by altering shared base code.

### Composition over Inheritance

Prefer composing behavior from small, focused components rather than building deep inheritance hierarchies. Use inheritance sparingly and only for true is-a relationships (e.g., `BaseCollector`).

### Dependency Injection

Components receive their dependencies (HTTP clients, storage backends, configuration) via constructor injection or factory functions — not through global state or direct instantiation of concrete implementations. This enables testability and runtime flexibility.

### Configuration over Hardcode

All environment-specific values (URLs, timeouts, rate limits, credentials, log levels) must be externalized to configuration files or environment variables. No magic numbers or hardcoded endpoints in source code.

### Plugin-based Architecture

Platform collectors, pipeline stages, and storage backends are registered as plugins discovered at runtime. Adding a new data source (Instagram, TikTok, YouTube, etc.) requires implementing a plugin — not modifying the core engine.

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

| Group | Purpose | Examples (planned) |
|-------|---------|---------------------|
| `dependencies` | Runtime packages | `httpx`, `pydantic`, `apscheduler` |
| `[dependency-groups] dev` | Development tooling | `ruff`, `pytest`, `mypy`, `pre-commit` |

Dev dependencies must never be imported in runtime code under `src/`.

### 8.3 Version Pinning

- Runtime dependencies: pin with compatible release specifiers (e.g., `httpx>=0.27,<0.28`) or exact pins for critical packages.
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
| Environment variables | Loaded from `.env` (local only, git-ignored) |
| Environment template | `.env.example` committed with all required keys, no values |

### 9.2 Environment Variable Naming

All application environment variables use the `AA_` prefix:

| Variable | Purpose | Example Value |
|----------|---------|---------------|
| `AA_ENV` | Environment name | `development`, `staging`, `production` |
| `AA_LOG_LEVEL` | Logging verbosity | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `AA_LOG_DIR` | Log output directory | `logs/` |
| `AA_DATA_DIR` | Base data directory | `data/` |

Platform-specific credentials (added in later sprints) follow the same prefix: `AA_INSTAGRAM_TOKEN`, `AA_YOUTUBE_API_KEY`, etc.

### 9.3 Environment Separation

| Environment | Config Source | Data | Logging |
|-------------|--------------|------|---------|
| Development | `.env` + defaults | Local `data/` dirs | `DEBUG` to console + file |
| Staging | Environment variables / config files | Isolated storage | `INFO` to file |
| Production | Secrets manager / env vars | Managed storage | `WARNING`+ to centralized log |

### 9.4 Secrets Policy

- `.env` is listed in `.gitignore` and must never be committed.
- `.env.example` documents every required variable with placeholder values.
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

Default level by environment: `DEBUG` (dev), `INFO` (staging), `WARNING` (production).

### 10.3 Log Format

Structured logging is the target format for production. During Sprint 1–2, establish a consistent text format:

```
%(asctime)s | %(levelname)-8s | %(name)s | %(message)s
```

Example:

```
2026-07-30 14:22:01,483 | INFO     | aa_crawler.collectors.instagram | Fetched 50 posts for query "brand-x"
```

Structured JSON logging will be adopted when the Dashboard API and centralized monitoring are implemented (Sprint 9+).

### 10.4 Log Output

| Output | Location | Rotation |
|--------|----------|----------|
| Console (stderr) | Development only | N/A |
| File | `logs/` directory | Size-based rotation (10 MB, 5 backups) |

Log files are git-ignored. The `logs/` directory is tracked via `.gitkeep`.

### 10.5 Logging Rules

- Use the module-level logger: `logger = logging.getLogger(__name__)`.
- Never use `print()` in application code (except CLI user-facing output in `main()`).
- Include contextual information in log messages: platform, query ID, batch size, duration.
- Do not log secrets, tokens, or full API responses containing PII.
- Exceptions must be logged with `logger.exception()` or `exc_info=True`.

### 10.6 Logger Hierarchy

```
aa_crawler                          # Root application logger
├── aa_crawler.collectors            # Collector Engine
│   ├── aa_crawler.collectors.instagram
│   └── aa_crawler.collectors.youtube
├── aa_crawler.pipeline             # Data Pipeline
├── aa_crawler.scheduler            # Scheduler
├── aa_crawler.storage              # Storage Layer
└── aa_crawler.api                  # Dashboard API
```

---

## 11. Testing Strategy

### 11.1 Framework

**pytest** is the standard test runner. No `unittest`-style test classes unless integrating with a library that requires them.

### 11.2 Test Layout

```
tests/
├── conftest.py              # Shared fixtures
├── unit/                    # Unit tests (no I/O, no network)
│   └── test_<module>.py
├── integration/             # Integration tests (local services, file I/O)
│   └── test_<module>.py
└── fixtures/                # Shared test data files
    └── sample_response.json
```

Test files mirror the `src/aa_crawler/` module structure.

### 11.3 Test Categories

| Category | Scope | Network | Speed | When Required |
|----------|-------|---------|-------|---------------|
| Unit | Single function/class | Mocked | Fast | Every public function |
| Integration | Module interaction | Mocked or local | Medium | Pipeline, storage boundaries |
| End-to-end | Full crawl → process flow | Live (staging) | Slow | Sprint 9+ |

During Sprint 1, only tooling verification tests are required (e.g., confirming `ruff`, `pytest`, and imports work).

### 11.4 Coverage Targets

| Phase | Target |
|-------|--------|
| Sprint 1–3 (foundation & framework) | ≥ 70% |
| Sprint 4–8 (features) | ≥ 80% |
| Sprint 9–10 (production) | ≥ 90% |

Coverage is measured with `pytest-cov` and reported in CI (when CI is configured).

### 11.5 Testing Rules

- Tests must be deterministic — no reliance on wall-clock time, random values, or network without mocking.
- Use `pytest fixtures` for shared setup; avoid global state.
- Name tests to describe behavior: `test_fetch_posts_returns_empty_list_when_no_results`.
- Mock external HTTP calls with `httpx` mock transport or `pytest-httpx` / `respx`.
- Test data files live in `tests/fixtures/` and must not contain real credentials or PII.

### 11.6 Running Tests

```bash
uv run pytest                    # Run all tests
uv run pytest tests/unit/        # Unit tests only
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

### 12.2 Ruff Configuration (Planned)

| Setting | Value | Rationale |
|---------|-------|-----------|
| Line length | 88 | Consistent with Black convention |
| Target Python | `py312` | Matches project requirement |
| Quote style | Double quotes | Enforced by formatter |
| Import sorting | Enabled (isort rules) | Consistent import order |
| Selected rules | `E`, `F`, `W`, `I`, `N`, `UP`, `B`, `C4`, `SIM`, `TCH` | Errors, warnings, imports, naming, pyupgrade, bugbear, comprehensions, simplify, type-checking |

### 12.3 Pre-Commit Hooks

A `.pre-commit-config.yaml` will enforce checks before every commit:

| Hook | Action |
|------|--------|
| `ruff check` | Lint |
| `ruff format` | Format |
| `mypy` | Type check (staged files or full project) |
| Trailing whitespace | Remove |
| End-of-file fixer | Ensure newline at EOF |
| YAML / TOML validation | Syntax check |
| No committed secrets | Detect `.env`, credentials patterns |

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
| 6 | `uv run mypy src/` passes with zero errors |
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
| 9 | Anti-bot detection, rate limiting, CAPTCHA, and platform blocking | Crawlers fail silently or produce incomplete data; increased maintenance burden | High | Abstract request engine with retry/backoff; rotate user agents and proxies; monitor failure rates; design collectors for graceful degradation |

---

## 15. Future Extensibility

The standards defined in this document are designed to scale with the AA Crawler roadmap.

### 15.1 Component Readiness

| Planned Component | Standards Support |
|-------------------|-------------------|
| **Query Management** | Typed interfaces, validated config via Pydantic (Sprint 2+) |
| **Query Engine** | Composable query builder; typed query models; unit-tested parsing and validation |
| **Collector Engine** | Plugin architecture with base class; per-platform modules under `collectors/` |
| **Scheduler** | Logging of job lifecycle events; testable with mocked clock |
| **Data Pipeline** | Stage-level logging; unit + integration test categories |
| **Storage Layer** | Abstract interface; integration tests against local/test storage |
| **Search Engine** | Index schema documented in ADR; integration test fixtures |
| **Dashboard API** | API-specific lint rules; OpenAPI schema generation |
| **AI Insight Engine** | Separate module; model I/O logging without PII |

### 15.2 Tooling Evolution

| Sprint | Tooling Addition |
|--------|-----------------|
| Sprint 2 | Logging configuration module, Pydantic settings |
| Sprint 3 | Plugin discovery conventions, base test fixtures for collectors |
| Sprint 4 | HTTP mock library (`respx` / `pytest-httpx`), retry test utilities |
| Sprint 8 | Data validation schemas, pipeline test fixtures |
| Sprint 9 | CI pipeline (GitHub Actions), coverage reporting, structured JSON logging |
| Sprint 10 | Performance benchmarks, security scanning (`bandit`), dependency audit automation |

### 15.3 ADR Triggers

An Architecture Decision Record must be created when:

- A new runtime dependency is introduced for a core component.
- A logging, storage, or messaging technology is selected.
- A breaking change to the module structure or public API is proposed.
- A deviation from these standards is required.

ADRs live in `docs/adr/` and follow the naming convention `NNNN-<title>.md`.

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
| Architecture Decision Records | `docs/adr/` |
| Sprint Roadmap | `README.md` § Roadmap |
