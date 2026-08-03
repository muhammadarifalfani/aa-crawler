# Sprint 2 — Configuration and Observability Foundation

## Objective

Establish typed configuration, deterministic runtime-path handling, secure
application logging, and an explicit application bootstrap suitable for future
crawler components.

## Completed work

- Configuration contract
- Documentation and environment alignment
- `pydantic-settings` dependency
- Frozen settings models
- Configuration loader and source precedence
- Runtime path resolution
- Runtime-directory preparation
- Logging foundation
- Correlation context
- Sensitive-data redaction
- Application bootstrap

## Key decisions

- Application environment variables use the `AA_` namespace.
- `.env` loading requires an explicitly selected file.
- Precedence is explicit overrides, OS environment, explicit `.env`, then defaults.
- Unknown `AA_` variables are rejected.
- Configuration models are frozen.
- `base_dir` is explicit and relative runtime paths must remain within it.
- Settings loading and path resolution are side-effect free.
- Runtime-directory preparation is explicit and idempotent.
- Logging uses Python's standard library and the `aa_crawler` hierarchy.
- Console output uses stderr; rotating file logging is optional.
- Correlation IDs use `ContextVar` and are not generated automatically.
- Sensitive values use the deterministic `[REDACTED]` replacement.
- Imports never perform application bootstrap.

## Pull requests

- PR #2 — `docs(config): align Sprint 2 configuration contract`
- PR #3 — `chore(deps): add pydantic-settings`
- PR #4 — `feat(config): add frozen settings models`
- PR #5 — `feat(config): add configuration loader`
- PR #6 — `feat(config): add runtime path resolution`
- PR #7 — `feat(observability): add logging foundation`
- PR #8 — `feat(observability): add logging context and redaction`
- PR #9 — `feat(app): add application bootstrap`

## Verification

- Locked dependency synchronization passed.
- End-to-end bootstrap integration passed with temporary runtime directories.
- Ruff lint and formatting checks passed.
- mypy passed.
- pytest passed with 130 tests.
- Coverage reached 94.68%, exceeding the 70% threshold.
- pre-commit passed across all files.

## Deliverables

- `src/aa_crawler/bootstrap.py`
- `src/aa_crawler/configuration/`
- `src/aa_crawler/observability/`
- `tests/test_bootstrap.py`
- `tests/configuration/`
- `tests/observability/`
- `README.md`
- `CONTRIBUTING.md`
- `docs/architecture/engineering-standards.md`
- `docs/sprint/sprint-2.md`

## Deferred work

- JSON logging
- Automatic correlation-ID generation
- Tracing and metrics
- Crawler framework
- HTTP request engine
- Platform collectors
- Scheduler and orchestration

## Status

Completed and ready for Sprint 3.
