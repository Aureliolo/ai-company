# CLAUDE.md -- SynthOrg

## Project

- **What**: Framework for building synthetic organizations -- autonomous AI agents orchestrated as a virtual company
- **Python**: 3.14+ (PEP 649 native lazy annotations)
- **License**: BUSL-1.1 with narrowed Additional Use Grant (free production use for non-competing small orgs; converts to Apache 2.0 three years after release)
- **Layout**: `src/synthorg/` (src layout), `tests/` (unit/integration/e2e), `web/` (React 19 dashboard), `cli/` (Go CLI binary)
- **Design**: [DESIGN_SPEC.md](docs/DESIGN_SPEC.md) (pointer to `docs/design/` pages)

## Design Spec (MANDATORY)

- **ALWAYS read the relevant `docs/design/` page** before implementing any feature or planning any issue. [DESIGN_SPEC.md](docs/DESIGN_SPEC.md) is a pointer file linking to the 11 design pages.
- The design spec is the **starting point** for architecture, data models, and behavior
- If implementation deviates from the spec (better approach found, scope evolved, etc.), **alert the user and explain why** -- user decides whether to proceed or update the spec
- Do NOT silently diverge -- every deviation needs explicit user approval
- When a spec topic is referenced (e.g. "the Agents page" or "the Engine page's Crash Recovery section"), read the relevant `docs/design/` page before coding
- When approved deviations occur, update the relevant `docs/design/` page to reflect the new reality

## Planning (MANDATORY)

- Every implementation plan must be **presented to the user** for accept/deny before coding starts
- At **every phase** of planning and implementation, be critical -- actively look for ways to improve the design in the spirit of what we're building (robustness, correctness, simplicity, future-proofing where it's free)
- Surface improvements as suggestions, not silent changes -- user decides
- **Prioritize issues by dependency order**, not priority labels -- unblocked dependencies come first

## Quick Commands

```bash
uv sync                                    # install all deps (dev + test)
uv sync --group docs                       # install docs toolchain
uv run ruff check src/ tests/              # lint
uv run ruff check src/ tests/ --fix        # lint + auto-fix
uv run ruff format src/ tests/             # format
uv run mypy src/ tests/                    # type-check (strict)
uv run python -m pytest tests/ -m unit -n auto        # unit tests only
uv run python -m pytest tests/ -m integration -n auto # integration tests only
uv run python -m pytest tests/ -m e2e -n auto         # e2e tests only
uv run python -m pytest tests/ -n auto --cov=synthorg --cov-fail-under=80  # full suite + coverage
HYPOTHESIS_PROFILE=dev uv run python -m pytest tests/ -m unit -n auto -k properties  # property tests (dev profile, 1000 examples)
uv run pre-commit run --all-files          # all pre-commit hooks
uv run python scripts/export_openapi.py    # export OpenAPI schema (needed before docs build)
uv run zensical build                      # build docs (output: _site/docs/) -- no --strict until zensical/backlog#72
uv run zensical serve                      # local docs preview (http://127.0.0.1:8000)
```

### Web Dashboard

```bash
npm --prefix web install                   # install frontend deps
npm --prefix web run dev                   # dev server (http://localhost:5173)
npm --prefix web run build                 # production build
npm --prefix web run lint                  # ESLint (zero warnings enforced)
npm --prefix web run type-check            # TypeScript type checking
npm --prefix web run test                  # Vitest unit tests (coverage scoped to files changed vs origin/main)
npm --prefix web run storybook             # Storybook dev server (http://localhost:6006)
npm --prefix web run storybook:build       # Storybook production build
```

### CLI (Go Binary)

Note: Go tooling requires the module root as cwd. Use `go -C cli` which changes directory internally without affecting the shell. Never use `cd cli` -- it poisons the cwd for all subsequent Bash calls. golangci-lint is registered as a `tool` in `cli/go.mod` so it runs via `go -C cli tool golangci-lint`.

```bash
go -C cli build -o synthorg ./main.go                                  # build CLI
go -C cli test ./...                                                   # run tests (fuzz targets run seed corpus only without -fuzz flag)
go -C cli vet ./...                                                    # vet
go -C cli tool golangci-lint run                                       # lint
go -C cli test -fuzz=FuzzYamlStr -fuzztime=30s ./internal/compose/     # fuzz example
```

#### Global Flags

All commands accept these persistent flags (precedence: flag > env var > config > default):

| Flag | Short | Env Var | Description |
|------|-------|---------|-------------|
| `--data-dir` | | `SYNTHORG_DATA_DIR` | Data directory (default: platform-appropriate) |
| `--skip-verify` | | `SYNTHORG_NO_VERIFY` / `SYNTHORG_SKIP_VERIFY` | Skip image signature verification |
| `--quiet` | `-q` | `SYNTHORG_QUIET` | Errors only, no spinners/hints/boxes |
| `--verbose` | `-v` | | Increase verbosity (`-v`=verbose, `-vv`=trace) |
| `--no-color` | | `NO_COLOR`, `CLICOLOR=0`, `TERM=dumb` | Disable ANSI color output |
| `--plain` | | | ASCII-only output (no Unicode, no spinners) |
| `--json` | | | Machine-readable JSON output |
| `--yes` | `-y` | `SYNTHORG_YES` | Auto-accept all prompts (non-interactive) |
| `--help-all` | | | Show help for all commands (recursive) |

Config-driven overrides (set via `synthorg config set`): `color never` implies `--no-color`, `color always` forces color on non-TTYs, `output json` implies `--json`, `hints` mode is config-only (always/auto/never).

#### Hint Tiers

The CLI uses four hint tiers with different visibility rules per `hints` mode. When adding hints, choose the tier that matches the intent:

| Tier | `always` | `auto` | `never` | `--quiet` | Use for |
|------|----------|--------|---------|-----------|---------|
| `HintError` | shown | shown | shown | suppressed | Error recovery (always visible unless quiet) |
| `HintNextStep` | shown | shown | shown | suppressed | Natural next action, destructive-action feedback |
| `HintTip` | shown | once/session | suppressed | suppressed | Config automation suggestions (e.g. `auto_pull`) |
| `HintGuidance` | shown | suppressed | suppressed | suppressed | Flag/feature discovery (e.g. `--watch`, `--keep N`) |

`HintTip` deduplicates within a session (same message shown at most once). `HintGuidance` is invisible in the default `auto` mode -- only users who opt in with `synthorg config set hints always` see it.

Additional env vars (no corresponding flag -- settable via env var or `config set`):

| Env Var | Description |
|---------|-------------|
| `SYNTHORG_LOG_LEVEL` | Override backend log level |
| `SYNTHORG_BACKEND_PORT` | Override backend API port |
| `SYNTHORG_WEB_PORT` | Override web dashboard port |
| `SYNTHORG_CHANNEL` | Override release channel (stable/dev) |
| `SYNTHORG_IMAGE_TAG` | Override container image tag |
| `SYNTHORG_AUTO_UPDATE_CLI` | Auto-accept CLI self-updates |
| `SYNTHORG_AUTO_PULL` | Auto-accept container image pulls |
| `SYNTHORG_AUTO_RESTART` | Auto-restart containers after update |

#### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Runtime error |
| 2 | Usage error (bad arguments) |
| 3 | Unhealthy (backend/containers) |
| 4 | Unreachable (Docker not available) |
| 10 | Updates available (`--check`) |

#### Config Subcommands

`synthorg config <subcommand>`:

| Subcommand | Description |
|------------|-------------|
| `show` | Display all current settings (default when no subcommand) |
| `get <key>` | Get a single config value (19 gettable keys) |
| `set <key> <value>` | Set a config value (17 settable keys, compose-affecting keys trigger regeneration) |
| `unset <key>` | Reset a key to its default value |
| `list` | Show all keys with resolved value and source (env/config/default) |
| `path` | Print the config file path |
| `edit` | Open config file in $VISUAL/$EDITOR |

Settable keys: `auto_apply_compose`, `auto_cleanup`, `auto_pull`, `auto_restart`, `auto_start_after_wipe`, `auto_update_cli`, `backend_port`, `channel`, `color`, `docker_sock`, `hints`, `image_tag`, `log_level`, `output`, `sandbox`, `timestamps`, `web_port`. Keys that affect Docker compose (`backend_port`, `web_port`, `sandbox`, `docker_sock`, `image_tag`, `log_level`) trigger automatic `compose.yml` regeneration.

#### Per-Command Flags

| Command | Flags |
|---------|-------|
| `init` | `--backend-port`, `--web-port`, `--sandbox`, `--image-tag`, `--channel`, `--log-level` (all flags = non-interactive mode) |
| `start` | `--no-wait`, `--timeout`, `--no-pull`, `--dry-run`, `--no-detach`, `--no-verify` |
| `stop` | `--timeout`/`-t`, `--volumes` |
| `status` | `--watch`/`-w`, `--interval`, `--wide`, `--no-trunc`, `--services`, `--check` |
| `logs` | `--follow`/`-f`, `--tail`, `--since`, `--until`, `--timestamps`/`-t`, `--no-log-prefix` |
| `update` | `--dry-run`, `--no-restart`, `--timeout`, `--cli-only`, `--images-only`, `--check` |
| `cleanup` | `--dry-run`, `--all`, `--keep N` |
| `backup create` | `--output`/`-o`, `--timeout` |
| `backup list` | `--limit`/`-n`, `--sort` |
| `backup restore` | `--confirm`, `--dry-run`, `--no-restart`, `--timeout` |
| `wipe` | `--dry-run`, `--no-backup`, `--keep-images` |
| `doctor` | `--checks`, `--fix` |
| `version` | `--short` |
| `uninstall` | `--keep-data`, `--keep-images` |

## Documentation

- **Docs**: `docs/` (Markdown, built with Zensical, config: `mkdocs.yml`)
- **Design spec**: `docs/design/` (11 pages), **Architecture**: `docs/architecture/`, **Roadmap**: `docs/roadmap/`
- **Security**: `docs/security.md`, **Licensing**: `docs/licensing.md`, **Reference**: `docs/reference/`
- **REST API reference**: `docs/rest-api.md` + `docs/_generated/api-reference.html` (generated by `scripts/export_openapi.py`)
- **Library reference**: `docs/api/` (auto-generated via mkdocstrings + Griffe, AST-based)
- **Scripts**: `scripts/` -- CI/build utilities and development-time validation hooks (relaxed ruff rules: `print` and deferred imports allowed)
- **Landing page**: `site/` (Astro). Includes `/get/` CLI install page, contact form, SEO
- **Deps**: `docs` group in `pyproject.toml` (`zensical`, `mkdocstrings[python]`, `griffe-pydantic`)

## Docker

```bash
# Build and run (from repo root)
cp docker/.env.example docker/.env        # configure env vars
docker compose -f docker/compose.yml build
docker compose -f docker/compose.yml up -d
docker compose -f docker/compose.yml down

# Verify
curl http://localhost:3001/api/v1/health   # backend (direct)
curl http://localhost:3000/api/v1/health   # backend (via web proxy)
```

- **Images**: backend (Chainguard distroless, non-root), web (nginx-unprivileged, SPA + API proxy), sandbox (Python + Node.js, non-root)
- **Config**: all Docker files in `docker/` -- Dockerfiles, compose, `.env.example`. Single root `.dockerignore` (all images build with `context: .`)
- **Verification**: CLI verifies cosign signatures + SLSA provenance at pull time; bypass with `--skip-verify`
- **Tags**: version from `pyproject.toml`, semver, SHA, plus dev tags (`v0.4.7-dev.3`, `dev` rolling) for dev channel builds

## Package Structure

```text
src/synthorg/
  api/            # Litestar REST + WebSocket API, RFC 9457 errors, setup wizard, auth/, guards (role-based access control), user management, auto-wiring, lifecycle, bootstrap (agent registry init from config)
  backup/         # Backup/restore orchestrator, scheduler, retention, handlers/
  budget/         # Cost tracking, budget enforcement, quota degradation, CFO optimization, trend analysis, budget forecasting, configurable currency formatting
  cli/            # Python CLI module (superseded by top-level cli/ Go binary)
  communication/  # Message bus, dispatcher, channels, delegation, conflict resolution, meeting/
  config/         # YAML company config loading and validation
  core/           # Shared domain models, base classes, resilience config
  engine/         # Orchestration, execution loops, task engine, coordination, checkpoint recovery, approval/review gates, stagnation detection, context budget, compaction, hybrid loop, workspace/ (git worktree isolation, merge orchestration, semantic conflict detection)
  hr/             # Hiring, firing, onboarding, agent registry, performance tracking, activity timeline, career history, promotion/demotion
  memory/         # Pluggable MemoryBackend, retrieval pipeline, org memory, consolidation
  persistence/    # Pluggable PersistenceBackend, SQLite, settings + user repositories
  observability/  # Structured logging, correlation tracking, redaction, third-party logger taming, events/
  providers/      # LLM provider abstraction, presets, model auto-discovery, runtime CRUD (management/), provider families, discovery SSRF allowlist, health tracking
  settings/       # Runtime-editable settings (DB > env > YAML > code), Fernet encryption, ConfigResolver, definitions/, subscribers/
  security/       # Rule engine, audit log, output scanner, progressive trust, autonomy levels, timeout policies, LLM fallback evaluator, custom policy rules
  templates/      # Pre-built company templates, personality presets, model requirements, tier-to-model matching, locale-aware name generation
  tools/          # Tool registry, built-in tools, git SSRF prevention, MCP bridge, sandbox factory, invocation tracking

web/src/          # React 19 + shadcn/ui + Tailwind CSS dashboard
  api/            # Axios client, endpoint modules (19 domains), shared types
  components/     # React components: ui/ (shadcn primitives + SynthOrg core components), layout/ (app shell, sidebar, status bar); feature dirs added as pages are built
  hooks/          # React hooks (auth, login lockout, WebSocket, polling, optimistic updates, command palette, flash effects, status transitions, page data composition)
  lib/            # Utilities (cn() class merging, semantic color mappers, etc.)
  pages/          # Lazy-loaded page components (one per route); page-scoped sub-components in pages/<page-name>/ subdirs (e.g. tasks/, org-edit/, settings/)
  router/         # React Router config, route constants, auth/setup guards
  stores/         # Zustand stores (auth, WebSocket, toast, analytics, setup wizard, company, agents, budget, tasks, settings, providers, and per-domain stores for each page)
  styles/         # Design tokens (--so-* CSS custom properties, single source of truth) and Tailwind theme bridge
  utils/          # Constants, error handling, formatting, logging
  __tests__/      # Vitest unit + property tests (mirrors src/ structure)

cli/              # Go CLI binary (cross-platform, manages Docker lifecycle)
  cmd/            # Cobra commands (init, start, stop, status, logs, doctor, update, cleanup, wipe, config, etc.), global options, exit codes, env var constants
  internal/       # version, config, docker, compose, health, diagnostics, images, selfupdate, completion, ui, verify

site/             # Astro landing page (synthorg.io)
```

## Web Dashboard Design System (MANDATORY)

### Component Reuse

**ALWAYS reuse existing components from `web/src/components/ui/`** before creating new ones. These are the shared building blocks -- every page composes from them:

| Component | Import | Use for |
|-----------|--------|---------|
| `StatusBadge` | `@/components/ui/status-badge` | Agent/task/system status indicators (colored dot + optional built-in label toggle) |
| `MetricCard` | `@/components/ui/metric-card` | Numeric KPIs with sparkline, change badge, progress bar |
| `Sparkline` | `@/components/ui/sparkline` | Inline SVG trend lines with `color?` and `animated?` props (used inside MetricCard or standalone) |
| `SectionCard` | `@/components/ui/section-card` | Titled card wrapper with icon and action slot |
| `AgentCard` | `@/components/ui/agent-card` | Agent display: avatar, name, role, status, current task |
| `DeptHealthBar` | `@/components/ui/dept-health-bar` | Department health: animated fill bar + `health?` (optional, shows N/A when null) + `agentCount` (required) + `taskCount?` (optional) |
| `ProgressGauge` | `@/components/ui/progress-gauge` | Circular gauge for budget/utilization (`max?` defaults to 100) |
| `StatPill` | `@/components/ui/stat-pill` | Compact inline label + value pair |
| `Avatar` | `@/components/ui/avatar` | Circular initials avatar with optional `borderColor?` prop |
| `Button` | `@/components/ui/button` | Standard button (shadcn) |
| `Toast` / `ToastContainer` | `@/components/ui/toast` | Success/error/warning/info notifications with auto-dismiss queue (mount `ToastContainer` once in AppLayout) |
| `Skeleton` / `SkeletonCard` / `SkeletonMetric` / `SkeletonTable` / `SkeletonText` | `@/components/ui/skeleton` | Loading placeholders matching component shapes (shimmer animation, respects `prefers-reduced-motion`) |
| `EmptyState` | `@/components/ui/empty-state` | No-data / no-results placeholder with icon, title, description, optional action button |
| `ErrorBoundary` | `@/components/ui/error-boundary` | React error boundary with retry -- `level` prop: `page` / `section` / `component` |
| `ConfirmDialog` | `@/components/ui/confirm-dialog` | Confirmation modal (Radix AlertDialog) with `default` / `destructive` variants and `loading` state |
| `CommandPalette` | `@/components/ui/command-palette` | Global Cmd+K search (cmdk + React Router) -- mount once in AppLayout, register commands via `useCommandPalette` hook |
| `InlineEdit` | `@/components/ui/inline-edit` | Click-to-edit text with Enter/Escape, validation, optimistic save with rollback |
| `AnimatedPresence` | `@/components/ui/animated-presence` | Page transition wrapper (Framer Motion AnimatePresence keyed by route) |
| `StaggerGroup` / `StaggerItem` | `@/components/ui/stagger-group` | Card entrance stagger container with configurable delay |
| `Drawer` | `@/components/ui/drawer` | Right-side slide-in panel with overlay, spring animation, focus trap, Escape-to-close |
| `InputField` | `@/components/ui/input-field` | Labeled text input with error/hint display, optional multiline textarea mode |
| `SelectField` | `@/components/ui/select-field` | Labeled select dropdown with error/hint and placeholder support |
| `SliderField` | `@/components/ui/slider-field` | Labeled range slider with custom value formatter and aria-live display |
| `ToggleField` | `@/components/ui/toggle-field` | Labeled toggle switch (role="switch") with optional description text |
| `TaskStatusIndicator` | `@/components/ui/task-status-indicator` | Task status dot with optional label and pulse animation (accepts `TaskStatus`) |
| `PriorityBadge` | `@/components/ui/task-status-indicator` | Task priority colored pill badge (critical/high/medium/low) |
| `ProviderHealthBadge` | `@/components/ui/provider-health-badge` | Provider health status indicator (up/degraded/down colored dot + optional label) |
| `TokenUsageBar` | `@/components/ui/token-usage-bar` | Segmented horizontal meter bar for token usage (multi-segment with auto-colors, `role="meter"`, animated transitions) |

### Design Token Rules

- **Colors**: use Tailwind semantic classes (`text-foreground`, `bg-card`, `text-accent`, `text-success`, `bg-danger`, etc.) or CSS variables (`var(--so-accent)`). NEVER hardcode hex values in `.tsx`/`.ts` files.
- **Typography**: use `font-sans` or `font-mono` (maps to Geist tokens). NEVER set `fontFamily` directly.
- **Spacing**: use density-aware tokens (`p-card`, `gap-section-gap`, `gap-grid-gap`) or standard Tailwind spacing. NEVER hardcode pixel values for layout spacing.
- **Shadows/Borders**: use token variables (`var(--so-shadow-card-hover)`, `border-border`, `border-bright`).

### Creating New Components

When a new shared component is needed (not covered by the inventory above):
1. Place it in `web/src/components/ui/` with a descriptive kebab-case filename
2. Create a `.stories.tsx` file alongside it with all states (default, hover, loading, error, empty)
3. Export props as a TypeScript interface
4. Use design tokens exclusively -- no hardcoded colors, fonts, or spacing
5. Import `cn` from `@/lib/utils` for conditional class merging

### What NOT to Do

- **Do NOT** recreate status dots inline -- use `<StatusBadge>`
- **Do NOT** build card-with-header layouts from scratch -- use `<SectionCard>`
- **Do NOT** create metric displays with `text-metric font-bold` -- use `<MetricCard>`
- **Do NOT** render initials circles manually -- use `<Avatar>`
- **Do NOT** create complex (>8 line) JSX inside `.map()` -- extract to a shared component
- **Do NOT** use `rgba()` with hardcoded values -- use design token variables

### Enforcement

A PostToolUse hook (`scripts/check_web_design_system.py`) runs automatically on every Edit/Write to `web/src/` files. It catches:
- Hardcoded hex colors and rgba values
- Hardcoded font-family declarations
- New components without Storybook stories
- Duplicate patterns that should use existing shared components
- Complex `.map()` blocks that should be extracted

Fix all violations before proceeding -- do not suppress or ignore hook output.

## Shell Usage

- **NEVER use `cd` in Bash commands** -- the working directory is already set to the project root. Use absolute paths or run commands directly. Do NOT prefix commands with `cd C:/Users/Aurelio/synthorg &&`.

## Code Conventions

- **No `from __future__ import annotations`** -- Python 3.14 has PEP 649
- **PEP 758 except syntax**: use `except A, B:` (no parentheses) -- ruff enforces this on Python 3.14
- **Type hints**: all public functions, mypy strict mode
- **Docstrings**: Google style, required on public classes/functions (enforced by ruff D rules)
- **Immutability**: create new objects, never mutate existing ones. For non-Pydantic internal collections (registries, `BaseTool`), use `copy.deepcopy()` at construction + `MappingProxyType` wrapping for read-only enforcement. For `dict`/`list` fields in frozen Pydantic models, rely on `frozen=True` for field reassignment prevention and `copy.deepcopy()` at system boundaries (tool execution, LLM provider serialization, inter-agent delegation, serializing for persistence).
- **Config vs runtime state**: frozen Pydantic models for config/identity; separate mutable-via-copy models (using `model_copy(update=...)`) for runtime state that evolves (e.g. agent execution state, task progress). Never mix static config fields with mutable runtime fields in one model.
- **Models**: Pydantic v2 (`BaseModel`, `model_validator`, `computed_field`, `ConfigDict`). Adopted conventions: use `@computed_field` for derived values instead of storing + validating redundant fields (e.g. `TokenUsage.total_tokens`); use `NotBlankStr` (from `core.types`) for all identifier/name fields -- including optional (`NotBlankStr | None`) and tuple (`tuple[NotBlankStr, ...]`) variants -- instead of manual whitespace validators.
- **Async concurrency**: prefer `asyncio.TaskGroup` for fan-out/fan-in parallel operations in new code (e.g. multiple tool invocations, parallel agent calls). Prefer structured concurrency over bare `create_task`. Existing code is being migrated incrementally.
- **Line length**: 88 characters (ruff)
- **Functions**: < 50 lines, files < 800 lines
- **Errors**: handle explicitly, never silently swallow
- **Validate**: at system boundaries (user input, external APIs, config files)

## Logging

- **Every module** with business logic MUST have: `from synthorg.observability import get_logger` then `logger = get_logger(__name__)`
- **Never** use `import logging` / `logging.getLogger()` / `print()` in application code (exception: `observability/setup.py` and `observability/sinks.py` may use stdlib `logging` and `print(..., file=sys.stderr)` for bootstrap and handler-cleanup code that runs before or during logging system configuration)
- **Variable name**: always `logger` (not `_logger`, not `log`)
- **Event names**: always use constants from the domain-specific module under `synthorg.observability.events` (e.g., `API_REQUEST_STARTED` from `events.api`, `TOOL_INVOKE_START` from `events.tool`, `GIT_COMMAND_START` from `events.git`, `CONTEXT_BUDGET_FILL_UPDATED` from `events.context_budget`, `BACKUP_STARTED` from `events.backup`, `SETUP_COMPLETED` from `events.setup`). Each domain has its own module -- see `src/synthorg/observability/events/` for the full inventory of constants. Import directly: `from synthorg.observability.events.<domain> import EVENT_CONSTANT`
- **Structured kwargs**: always `logger.info(EVENT, key=value)` -- never `logger.info("msg %s", val)`
- **All error paths** must log at WARNING or ERROR with context before raising
- **All state transitions** must log at INFO
- **DEBUG** for object creation, internal flow, entry/exit of key functions
- Pure data models, enums, and re-exports do NOT need logging

## Resilience

- **All provider calls** go through `BaseCompletionProvider` which applies retry + rate limiting automatically
- **Never** implement retry logic in driver subclasses or calling code -- it's handled by the base class
- **RetryConfig** and **RateLimiterConfig** are set per-provider in `ProviderConfig`
- **Retryable errors** (`is_retryable=True`): `RateLimitError`, `ProviderTimeoutError`, `ProviderConnectionError`, `ProviderInternalError`
- **Non-retryable errors** raise immediately without retry
- **`RetryExhaustedError`** signals that all retries failed -- the engine layer catches this to trigger fallback chains
- **Rate limiter** respects `RateLimitError.retry_after` from providers -- automatically pauses future requests

## Testing

- **Markers**: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.e2e`, `@pytest.mark.slow`
- **Coverage**: 80% minimum (enforced in CI)
- **Async**: `asyncio_mode = "auto"` -- no manual `@pytest.mark.asyncio` needed
- **Timeout**: 30 seconds per test (global in `pyproject.toml` -- do not add per-file `pytest.mark.timeout(30)` markers; non-default overrides like `timeout(60)` are allowed)
- **Parallelism**: `pytest-xdist` via `-n auto` -- **ALWAYS** include `-n auto` when running pytest, never run tests sequentially
- **Parametrize**: Prefer `@pytest.mark.parametrize` for testing similar cases
- **Vendor-agnostic everywhere**: NEVER use real vendor names (Anthropic, OpenAI, Claude, GPT, etc.) in project-owned code, docstrings, comments, tests, or config examples. Use generic names: `example-provider`, `example-large-001`, `example-medium-001`, `example-small-001`, `large`/`medium`/`small` as aliases. Vendor names may only appear in: (1) Operations design page provider list (`docs/design/operations.md`), (2) `.claude/` skill/agent files, (3) third-party import paths/module names (e.g. `litellm.types.llms.openai`), (4) provider presets (`src/synthorg/providers/presets.py`) which are user-facing runtime data. Tests must use `test-provider`, `test-small-001`, etc.
- **Property-based testing**: Python uses [Hypothesis](https://hypothesis.readthedocs.io/) (`@given` + `@settings`), React uses [fast-check](https://fast-check.dev/) (`fc.assert` + `fc.property`), Go uses native `testing.F` fuzz functions (`Fuzz*`). Hypothesis profiles: `ci` (50 examples, default) and `dev` (1000 examples), controlled via `HYPOTHESIS_PROFILE` env var. Run dev profile: `HYPOTHESIS_PROFILE=dev uv run python -m pytest tests/ -m unit -n auto -k properties`. `.hypothesis/` is gitignored.
- **Flaky tests**: NEVER skip, dismiss, or ignore flaky tests -- always fix them fully and fundamentally. For timing-sensitive tests, mock `time.monotonic()` and `asyncio.sleep()` to make them deterministic instead of widening timing margins. For tasks that must block indefinitely until cancelled (e.g. simulating a slow provider or stubborn coroutine), use `asyncio.Event().wait()` instead of `asyncio.sleep(large_number)` -- it is cancellation-safe and carries no timing assumptions.

## Git

- **Commits**: `<type>: <description>` -- types: feat, fix, refactor, docs, test, chore, perf, ci
- **Enforced by**: commitizen (commit-msg hook)
- **Signed commits**: required on `main` via branch protection -- all commits must be GPG/SSH signed
- **Branches**: `<type>/<slug>` from main
- **Pre-commit hooks**: trailing-whitespace, end-of-file-fixer, check-yaml, check-toml, check-json, check-merge-conflict, check-added-large-files, no-commit-to-branch (main), ruff check+format, gitleaks, hadolint (Dockerfile linting), golangci-lint + go vet (CLI, conditional on `cli/**/*.go`), no-em-dashes, no-redundant-timeout, eslint-web (web dashboard, zero warnings, conditional on `web/src/**/*.{ts,tsx}`)
- **Pre-push hooks**: mypy type-check + pytest unit tests + golangci-lint + go vet + go test (CLI, conditional on `cli/**/*.go`) + eslint-web (web dashboard) (fast gate before push, skipped in pre-commit.ci -- dedicated CI jobs already run these)
- **Pre-commit.ci**: autoupdate disabled (`autoupdate_schedule: never`) -- Dependabot owns hook version bumps via `pre-commit` ecosystem
- **GitHub issue queries**: use `gh issue list` via Bash (not MCP tools) -- MCP `list_issues` has unreliable field data
- **Merge strategy**: squash merge -- PR body becomes the squash commit message on main. Trailers (e.g. `Release-As`, `Closes #N`) must be in the PR body to land in the final commit.
- **PR issue references**: preserve existing `Closes #NNN` references -- never remove unless explicitly asked

## Post-Implementation (MANDATORY)

- **After finishing an issue implementation**: always create a feature branch (`<type>/<slug>`), commit, and push -- do NOT create a PR automatically
- Do NOT leave work uncommitted on main -- branch, commit, push immediately after finishing

## Pre-PR Review (MANDATORY)

- **NEVER create a PR directly** -- `gh pr create` is blocked by hookify
- **ALWAYS use `/pre-pr-review`** to create PRs -- it runs automated checks + review agents + fixes before creating the PR
- For trivial/docs-only changes: `/pre-pr-review quick` skips agents but still runs automated checks
- After the PR exists, use `/aurelio-review-pr` to handle external reviewer feedback
- The `/commit-push-pr` command is effectively blocked (it calls `gh pr create` internally)
- **Fix everything valid -- never skip**: When review agents find valid issues (including pre-existing issues in surrounding code, suggestions, and findings adjacent to the PR's changes), fix them all. No deferring, no "out of scope" skipping.

## Releasing

- **Automated by Release Please**: every push to `main` creates/updates a release PR with changelog
- **Version bumping** (pre-1.0): `fix:`/`feat:` = patch, `feat!:`/`BREAKING CHANGE` = minor. Post-1.0: standard semver
- **`Release-As` trailer**: add `Release-As: 0.4.0` as the **final paragraph** of the PR body (separated by blank line). Mid-body placement is silently ignored.
- **Release flow**: merge release PR -> draft Release + tag -> Docker + CLI workflows attach assets -> finalize-release publishes
- **Dev channel**: every push to `main` (except Release Please bumps) creates a dev pre-release (e.g. `v0.4.7-dev.3`) via `dev-release.yml`. Users opt in with `synthorg config set channel dev`. Dev releases flow through the same Docker + CLI pipelines as stable releases. All dev releases and tags are deleted when a stable release is published.
- **Config**: `.github/release-please-config.json`, `.github/.release-please-manifest.json` (do not edit manually)
- **Changelog**: `.github/CHANGELOG.md` (auto-generated, do not edit)
- **Version locations**: `pyproject.toml` (`[tool.commitizen].version`), `src/synthorg/__init__.py` (`__version__`)

## CI

- **Path filtering**: `dorny/paths-filter` -- jobs only run when their domain is affected. CLI has its own workflow (`cli.yml`).
- **Jobs**: lint (ruff) + type-check (mypy) + test (pytest + coverage) + python-audit (pip-audit) + dockerfile-lint (hadolint) + dashboard (lint/type-check/test with `--detect-async-leaks`/build/storybook-build/audit) run in parallel -> ci-pass gate
- **Pages**: `pages.yml` -- version extraction from `pyproject.toml`, OpenAPI export, Astro + Zensical docs build (with version banner), GitHub Pages deploy on push to main
- **PR Preview**: `pages-preview.yml` -- Cloudflare Pages deploy per PR (`pr-<number>.synthorg-pr-preview.pages.dev`), cleanup on PR close
- **Docker**: `docker.yml` -- build + Trivy/Grype scan + push to GHCR + cosign sign + SLSA L3 provenance. CVE triage: `.github/.trivyignore.yaml`, `.github/.grype.yaml`
- **CLI**: `cli.yml` -- Go lint/test/build (cross-compile) + govulncheck + fuzz. GoReleaser release on `v*` tags with cosign signing + SLSA provenance
- **Dependabot**: daily updates (uv, github-actions, npm, pre-commit, docker, gomod), all updates grouped into 1 PR per ecosystem, no auto-merge. Use `/review-dep-pr` before merging
- **Security scanning**: gitleaks (push/PR + weekly), zizmor (workflow analysis), OSSF Scorecard (weekly), Socket.dev (PR supply chain), ZAP DAST (weekly + manual, rules: `.github/zap-rules.tsv`)
- **Coverage**: Codecov (best-effort, CI not gated on availability)
- **Dependency review**: `dependency-review.yml` -- license allow-list (permissive + weak-copyleft), per-package GPL exemptions for dev-only tool deps (golangci-lint), PR comment summaries
- **CLA**: `cla.yml` -- contributor-assistant check on PRs, signatures in `.github/cla-signatures.json`
- **Release**: `release.yml` -- Release Please creates draft release PR. Uses `RELEASE_PLEASE_TOKEN` (PAT)
- **Dev Release**: `dev-release.yml` -- creates semver dev tags (e.g. `v0.4.7-dev.3`) and draft pre-releases on every push to main (skips Release Please version-bump commits). Tags trigger existing Docker + CLI workflows for full build/scan/sign pipeline. Incrementally prunes old dev pre-releases (keeps 5 most recent); finalize-release deletes all remaining when a stable release is published.
- **Finalize Release**: `finalize-release.yml` -- publishes draft after Docker + CLI workflows succeed for tag. Immutable releases enabled. Handles both stable and dev releases. Deletes all dev pre-releases and tags when a stable release is published.

## Dependencies

- **Pinned**: all versions use `==` in `pyproject.toml`
- **Groups**: `test` (pytest + plugins, hypothesis), `dev` (includes test + ruff, mypy, pre-commit, commitizen, pip-audit)
- **Required**: `mem0ai` (Mem0 memory backend -- the default and currently only backend), `cryptography` (Fernet encryption for sensitive settings at rest), `faker` (multi-locale agent name generation for templates and setup wizard)
- **Install**: `uv sync` installs everything (dev group is default)
- **Web dashboard**: Node.js 22+, TypeScript 6.0+, dependencies in `web/package.json` (React 19, react-router, shadcn/ui, Radix UI, Tailwind CSS 4, Zustand, @tanstack/react-query, @xyflow/react, @dagrejs/dagre, @dnd-kit, Recharts, Framer Motion, cmdk, js-yaml, Axios, Lucide React, @fontsource-variable/geist, @fontsource-variable/geist-mono, Storybook 10, Vitest, @vitest/coverage-v8, @testing-library/react, fast-check, ESLint, @eslint-react/eslint-plugin, eslint-plugin-security)
- **CLI**: Go 1.26+, dependencies in `cli/go.mod` (Cobra, charmbracelet/huh, charmbracelet/lipgloss, sigstore-go, go-containerregistry, go-tuf)

## Post-Training Reference (TypeScript 6 & Storybook 10)

These tools were released after Claude's training cutoff. Key facts for correct code generation:

### TypeScript 6.0 (https://aka.ms/ts6)

- **`baseUrl` deprecated** -- will stop working in TS 7. Remove it; `paths` entries are relative to the tsconfig directory
- **`esModuleInterop` always true** -- cannot be set to `false`; remove explicit `"esModuleInterop": true` to avoid deprecation warning
- **`types` defaults to `[]`** -- no longer auto-discovers `@types/*`; must explicitly list needed types (e.g. `"types": ["vitest/globals"]`)
- **`DOM.Iterable` merged into `DOM`** -- `"lib": ["ES2025", "DOM"]` is sufficient, no separate `DOM.Iterable`
- **`moduleResolution: "classic"` and `"node10"` removed** -- use `"bundler"` or `"nodenext"`
- **`strict` defaults to `true`** -- explicit `"strict": true` is redundant but harmless
- **`noUncheckedSideEffectImports` defaults to `true`** -- CSS side-effect imports need type declarations (Vite's `/// <reference types="vite/client" />` covers this)
- **Last JS-based TypeScript** -- TS 7.0 will be rewritten in Go. Migration tool: `npx @andrewbranch/ts5to6`

### Storybook 10 (https://storybook.js.org/docs/releases/migration-guide)

- **ESM-only** -- all CJS support removed
- **Packages removed** -- `@storybook/addon-essentials`, `@storybook/addon-interactions`, `@storybook/test`, `@storybook/blocks` no longer published. Essentials (backgrounds, controls, viewport, actions, toolbars, measure, outline) and interactions are built into core `storybook`
- **`@storybook/addon-docs` is separate** -- must be installed and added to addons if using `tags: ['autodocs']` or MDX
- **Import paths changed** -- use `storybook/test` (not `@storybook/test`), `storybook/actions` (not `@storybook/addon-actions`)
- **Type-safe config** -- use `defineMain` from `@storybook/react-vite/node` and `definePreview` from `@storybook/react-vite` (must still include explicit `framework` field)
- **Backgrounds API changed** -- use `parameters.backgrounds.options` (object keyed by name) + `initialGlobals.backgrounds.value` (replaces old `default` + `values` array)
- **a11y testing** -- use `parameters.a11y.test: 'error' | 'todo' | 'off'` (replaces old `.element` and `.manual`). Set globally in `preview.tsx` to enforce WCAG compliance on all stories
- **Minimum versions** -- Node 20.19+, Vite 5+, Vitest 3+, TypeScript 4.9+
