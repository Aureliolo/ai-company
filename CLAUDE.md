# CLAUDE.md — AI Company

## Project

- **What**: Framework for orchestrating autonomous AI agents within a virtual company structure
- **Python**: 3.14+ (PEP 649 native lazy annotations)
- **License**: BUSL-1.1 (converts to Apache 2.0 on 2030-02-27)
- **Layout**: `src/ai_company/` (src layout), `tests/` (unit/integration/e2e)
- **Design**: [DESIGN_SPEC.md](DESIGN_SPEC.md) (full high-level spec)

## Quick Commands

```bash
uv sync                                    # install all deps (dev + test)
uv run ruff check src/ tests/              # lint
uv run ruff check src/ tests/ --fix        # lint + auto-fix
uv run ruff format src/ tests/             # format
uv run mypy src/                           # type-check (strict)
uv run pytest tests/ -m unit               # unit tests only
uv run pytest tests/ -m integration        # integration tests only
uv run pytest tests/ -n auto --cov=ai_company --cov-fail-under=80  # full suite + coverage
pre-commit run --all-files                 # all pre-commit hooks
```

## Package Structure

```
src/ai_company/
  api/            # FastAPI REST + WebSocket routes
  budget/         # Per-agent cost tracking and spending controls
  cli/            # Typer CLI commands
  communication/  # Inter-agent message bus and channels
  config/         # YAML company config loading and validation
  core/           # Shared domain models and base classes
  engine/         # Agent execution engine and task lifecycle
  memory/         # Persistent agent memory (Mem0 adapter)
  providers/      # LLM provider abstraction (LiteLLM adapter)
  security/       # SecOps agent, approval gates, sandboxing
  templates/      # Pre-built company templates and builder
  tools/          # Tool registry, MCP integration, role-based access
```

## Code Conventions

- **No `from __future__ import annotations`** — Python 3.14 has PEP 649
- **Type hints**: all public functions, mypy strict mode
- **Docstrings**: Google style, required on public classes/functions (enforced by ruff D rules)
- **Immutability**: create new objects, never mutate existing ones
- **Models**: Pydantic v2 (`BaseModel`, `model_validator`, `ConfigDict`)
- **Line length**: 88 characters (ruff)
- **Functions**: < 50 lines, files < 800 lines
- **Errors**: handle explicitly, never silently swallow
- **Validate**: at system boundaries (user input, external APIs, config files)

## Testing

- **Markers**: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.e2e`, `@pytest.mark.slow`
- **Coverage**: 80% minimum (enforced in CI)
- **Async**: `asyncio_mode = "auto"` — no manual `@pytest.mark.asyncio` needed
- **Timeout**: 30 seconds per test
- **Parallelism**: `pytest-xdist` via `-n auto`

## Git

- **Commits**: `<type>: <description>` — types: feat, fix, refactor, docs, test, chore, perf, ci
- **Enforced by**: commitizen (commit-msg hook)
- **Branches**: `<type>/<slug>` from main
- **Pre-commit hooks**: trailing-whitespace, end-of-file-fixer, check-yaml, check-toml, check-json, check-merge-conflict, check-added-large-files, no-commit-to-branch (main), ruff check+format, gitleaks

## CI

- **Jobs**: lint (ruff) → type-check (mypy) → test (pytest + coverage) → ci-pass (gate)
- **Matrix**: Python 3.14
- **Dependabot**: weekly pip + github-actions updates, auto-merge for patch/minor

## Dependencies

- **Pinned**: all versions use `==` in `pyproject.toml`
- **Groups**: `test` (pytest + plugins), `dev` (includes test + ruff, mypy, pre-commit, commitizen, pydantic)
- **Install**: `uv sync` installs everything (dev group is default)
