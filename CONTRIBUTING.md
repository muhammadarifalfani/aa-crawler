# Contributing to AA Crawler

This guide describes the current contribution workflow for AA Crawler. The development tooling is configured in `pyproject.toml` and installed through the locked `uv` environment.

## Prerequisites

Install the following tools:

- Git
- Python 3.12
- [uv](https://docs.astral.sh/uv/)

Confirm that they are available:

```bash
git --version
python --version
uv --version
```

The active Python version must match the project version declared in `.python-version` and `pyproject.toml`.

## Local setup

Clone the repository and enter the project directory:

```bash
git clone https://github.com/muhammadarifalfani/aa-crawler.git
cd aa_crawler
```

Create or synchronize the project environment with:

```bash
uv sync
```

`uv sync` installs the project and its approved development tools from `pyproject.toml` and `uv.lock`.

Do not use `pip`, Poetry, or Pipenv directly for project dependency management.

## Branching

Do not work directly on `main`. Keep `main` protected and update it through reviewed pull requests. Create a focused task branch from the latest approved `main` branch.

Suggested branch patterns:

| Change | Pattern | Example |
|---|---|---|
| Feature | `feat/<name>` | `feat/base-collector` |
| Bug fix | `fix/<name>` | `fix/empty-response` |
| Tooling or maintenance | `chore/<name>` | `chore/sprint-1-tooling` |
| Documentation | `docs/<name>` | `docs/contribution-guide` |
| Tests | `test/<name>` | `test/collector-contract` |

Use lowercase, hyphen-separated names that describe the branch scope.

## Development workflow

Use the following workflow for each task:

1. Understand the requirement and acceptance criteria.
2. Propose the design before implementation when the change affects architecture, tooling, or project policy.
3. Review risks, dependencies, and effects on existing files.
4. Implement only the approved scope.
5. Self-review the resulting diff.
6. Run the applicable quality checks.
7. Commit the focused change.
8. Open a pull request for review.

Do not combine unrelated cleanup, dependency updates, formatting, or refactoring with the requested change.

## Coding standards

Follow the project’s [Engineering Standards](docs/architecture/engineering-standards.md).

In particular:

- Respect `.editorconfig` and `.gitattributes`.
- Use Python type hints for public functions, methods, and class attributes.
- Use Google-style docstrings for public APIs.
- Keep modules and functions focused on one responsibility.
- Prefer dependency injection and configuration over global state and hardcoded values.
- Do not commit credentials, tokens, local `.env` files, or other secrets.
- Do not commit generated crawler data.
- Do not modify protected tooling or architecture files without task approval.

Automated tools complement the Engineering Standards; they do not replace review and engineering judgment.

Runtime configuration must be initialized explicitly at the application
composition root. Do not load settings, create runtime directories, configure
logging, or mutate environment state at import time. Tests that change
environment variables, logging state, correlation context, or runtime paths
must isolate and restore those changes with fixtures such as `monkeypatch` and
`tmp_path`.

## Quality checks

Run the applicable quality commands below before requesting review.

```bash
# Lint
uv run ruff check .

# Verify formatting
uv run ruff format --check .

# Type-check the configured project scope
uv run mypy

# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=aa_crawler
```

Run every check applicable to the change and report the commands that completed successfully.

Run the repository hook suite before committing or requesting review:

```bash
uv run pre-commit run --all-files
```

Do not use automatic fixes or repository-wide formatting unless the task explicitly authorizes them.

## Commit guidance

Use concise, imperative commit messages following the project’s approved commit-message convention:

```text
<type>(<scope>): <summary>
```

Examples:

```text
chore(tooling): add repository editor configuration
docs(contributing): add contributor workflow
test(collector): add base collector contract tests
fix(pipeline): handle empty input batch
feat(collector): add base collector interface
```

Keep the summary at 72 characters or fewer, omit the trailing period, and explain the reason for a non-obvious change in the commit body.

A commit should represent one coherent change.

## Pull request checklist

Before requesting review, confirm:

- [ ] The change has a focused, approved scope.
- [ ] The diff has been self-reviewed.
- [ ] Tests were added or updated when behavior changed.
- [ ] Documentation was updated when behavior, configuration, or architecture changed.
- [ ] Applicable Ruff, mypy, pytest, and coverage checks pass.
- [ ] No secrets, credentials, tokens, or local environment values are included.
- [ ] No generated crawler data or runtime logs are included.
- [ ] No unrelated files were reformatted or normalized.
- [ ] Architectural decisions are documented when required by the Engineering Standards.

Include what changed, why it changed, how it was verified, and any known limitations in the pull request description.

## Repository-specific rules

### Runtime data

Generated runtime data belongs in:

- `data/raw/`
- `data/processed/`
- `data/failed/`

Do not commit files generated in these directories. Their `.gitkeep` files preserve the required directory structure.

### Test fixtures

Deterministic sample data used by tests belongs under:

```text
tests/fixtures/
```

Test fixtures must not contain real credentials, private information, or production data. Do not use the runtime `data/` directories as test-fixture storage.

### Dependency lockfile

`uv.lock` must remain visible to Git and must not be added to `.gitignore`.

Follow the approved Engineering Standards policy:

- Commit `uv.lock` starting in Sprint 1.
- Commit and maintain `uv.lock` whenever approved dependencies change.
- Do not update the lockfile as an unrelated side effect of another change.
