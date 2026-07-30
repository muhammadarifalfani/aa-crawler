# Sprint 1 — Engineering Foundation

## Objective

Establish the repository, engineering policies, development tooling, automated
checks, and reproducible development environment.

## Completed work

- Repository foundation and src layout
- Engineering Standards
- EditorConfig
- Git attributes
- Git ignore policy
- Contribution guide
- Environment template
- Production-ready pyproject.toml
- uv.lock
- Ruff
- mypy
- pytest and coverage
- pre-commit

## Verification

- Ruff lint passed
- Ruff formatting check passed
- mypy passed
- pytest passed
- Coverage reached 100%, threshold 70%
- pre-commit passed

## Key decisions

- Python 3.12+
- uv for dependency management
- uv_build backend
- src layout
- line length 88
- gradual mypy adoption
- uv.lock committed from Sprint 1
- runtime dependencies remain empty

## Deliverables

- `.editorconfig`
- `.env.example`
- `.gitattributes`
- `.gitignore`
- `.pre-commit-config.yaml`
- `CONTRIBUTING.md`
- `README.md`
- `docs/architecture/engineering-standards.md`
- `docs/sprint/sprint-1.md`
- `pyproject.toml`
- `tests/__init__.py`
- `tests/test_main.py`
- `uv.lock`

## Status

Completed and ready for commit review.
