# CLAUDE.md -- SynthOrg

## Project

- **What**: Framework for building synthetic organizations -- autonomous AI agents orchestrated as a virtual company
- **Python**: 3.14+ (PEP 649 native lazy annotations)
- **License**: BUSL-1.1 with narrowed Additional Use Grant (free production use for non-competing small orgs; converts to Apache 2.0 three years after release)
- **Layout**: `src/synthorg/` (src layout), `tests/` (unit/integration/e2e), `web/` (React 19 dashboard), `cli/` (Go CLI binary)
- **Design**: [DESIGN_SPEC.md](docs/DESIGN_SPEC.md) (pointer to `docs/design/` pages)

## Design Spec (MANDATORY)

- **ALWAYS read the relevant `docs/design/` page** before implementing any feature or planning any issue. [DESIGN_SPEC.md](docs/DESIGN_SPEC.md) is a pointer file linking to the 12 design pages.
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
uv run python -m pytest tests/ -m unit -n 8            # unit tests only
uv run python -m pytest tests/ -m integration -n 8     # integration tests only
uv run python -m pytest tests/ -m e2e -n 8             # e2e tests only
uv run python -m pytest tests/ -n 8 --cov=synthorg --cov-fail-under=80  # full suite + coverage
HYPOTHESIS_PROFILE=dev uv run python -m pytest tests/ -m unit -n 8 -k properties   # property tests (dev, 1000 examples)
HYPOTHESIS_PROFILE=fuzz uv run python -m pytest tests/ -m unit -n 8 --timeout=0    # deep fuzzing (10,000 examples, no deadline, all @given tests)
uv run pre-commit run --all-files          # all pre-commit hooks
uv run python scripts/export_openapi.py    # export OpenAPI schema (needed before docs build)
uv run python scripts/generate_comparison.py  # generate comparison page (needed before docs build)
uv run zensical build                      # build docs (output: _site/docs/) -- no --strict until zensical/backlog#72
uv run zensical serve                      # local docs preview (http://127.0.0.1:8000)
```

### Web Dashboard

See `web/CLAUDE.md` for commands, design system, and component inventory.

### CLI (Go Binary)

See `cli/CLAUDE.md` for commands, flags, and reference. Key rule: use `go -C cli` (never `cd cli`).

## Reference (load on demand)

See [docs/reference/claude-reference.md](docs/reference/claude-reference.md) for: Documentation layout, Docker commands, Package Structure, Releasing, CI pipelines, Dependencies.

## Web Dashboard Design System (MANDATORY)

See `web/CLAUDE.md` for the full component inventory, design token rules, and post-training references (TS6, Storybook 10). Key rules:
- **ALWAYS reuse** existing components from `web/src/components/ui/` before creating new ones
- **NEVER hardcode** hex colors, font-family, pixel spacing, or Framer Motion transitions -- use design tokens and `@/lib/motion` presets
- A PostToolUse hook (`scripts/check_web_design_system.py`) enforces these rules on every Edit/Write to `web/src/`

## Shell Usage

- **NEVER use `cd` in Bash commands** -- the working directory is already set to the project root. Use absolute paths or run commands directly. Do NOT prefix commands with `cd C:/Users/Aurelio/synthorg &&`. Exception: `bash -c "cd <dir> && <cmd>"` is safe (runs in a child process, no cwd side effects). Use this for tools without a `-C` flag -- e.g. `bash -c "cd web && npm install"` since `npm --prefix` is broken for bare `npm install`.
- **NEVER use Bash to write or modify files** -- use the Write or Edit tools. Do not use `cat >`, `cat << EOF`, `echo >`, `echo >>`, `sed -i`, `python -c "open(...).write(...)"`, or `tee` to create or modify files (read-only/inspection uses like piping to stdout are fine). This applies to all files (plan files, config files, source code) and all subagents.

## Code Conventions

- **No `from __future__ import annotations`** -- Python 3.14 has PEP 649
- **PEP 758 except syntax**: use `except A, B:` (no parentheses) -- ruff enforces this on Python 3.14
- **Type hints**: all public functions, mypy strict mode
- **Docstrings**: Google style, required on public classes/functions (enforced by ruff D rules)
- **Immutability**: create new objects, never mutate existing ones. For non-Pydantic internal collections (registries, `BaseTool`), use `copy.deepcopy()` at construction + `MappingProxyType` wrapping for read-only enforcement. For `dict`/`list` fields in frozen Pydantic models, rely on `frozen=True` for field reassignment prevention and `copy.deepcopy()` at system boundaries (tool execution, LLM provider serialization, inter-agent delegation, serializing for persistence).
- **Config vs runtime state**: frozen Pydantic models for config/identity; separate mutable-via-copy models (using `model_copy(update=...)`) for runtime state that evolves (e.g. agent execution state, task progress). Never mix static config fields with mutable runtime fields in one model.
- **Models**: Pydantic v2 (`BaseModel`, `model_validator`, `computed_field`, `ConfigDict`). Adopted conventions: use `allow_inf_nan=False` in all `ConfigDict` declarations to reject `NaN`/`Inf` in numeric fields at validation time; use `@computed_field` for derived values instead of storing + validating redundant fields (e.g. `TokenUsage.total_tokens`); use `NotBlankStr` (from `core.types`) for all identifier/name fields -- including optional (`NotBlankStr | None`) and tuple (`tuple[NotBlankStr, ...]`) variants -- instead of manual whitespace validators.
- **Async concurrency**: prefer `asyncio.TaskGroup` for fan-out/fan-in parallel operations in new code (e.g. multiple tool invocations, parallel agent calls). Prefer structured concurrency over bare `create_task`. Existing code is being migrated incrementally.
- **Line length**: 88 characters (ruff)
- **Functions**: < 50 lines, files < 800 lines
- **Errors**: handle explicitly, never silently swallow
- **Validate**: at system boundaries (user input, external APIs, config files)

## Logging

- **Every module** with business logic MUST have: `from synthorg.observability import get_logger` then `logger = get_logger(__name__)`
- **Never** use `import logging` / `logging.getLogger()` / `print()` in application code (exception: `observability/setup.py`, `observability/sinks.py`, `observability/syslog_handler.py`, `observability/http_handler.py`, and `observability/otlp_handler.py` may use stdlib `logging` and `print(..., file=sys.stderr)` for handler construction, bootstrap, and error reporting code that runs before or during logging system configuration)
- **Variable name**: always `logger` (not `_logger`, not `log`)
- **Event names**: always use constants from the domain-specific module under `synthorg.observability.events` (e.g., `API_REQUEST_STARTED` from `events.api`, `TOOL_INVOKE_START` from `events.tool`, `GIT_COMMAND_START` from `events.git`, `CONTEXT_BUDGET_FILL_UPDATED`, `CONTEXT_BUDGET_COMPACTION_STARTED`, `CONTEXT_BUDGET_COMPACTION_COMPLETED`, `CONTEXT_BUDGET_COMPACTION_FAILED`, `CONTEXT_BUDGET_COMPACTION_SKIPPED`, `CONTEXT_BUDGET_COMPACTION_FALLBACK`, `CONTEXT_BUDGET_INDICATOR_INJECTED`, `CONTEXT_BUDGET_AGENT_COMPACTION_REQUESTED`, `CONTEXT_BUDGET_EPISTEMIC_MARKERS_PRESERVED` from `events.context_budget`, `BACKUP_STARTED` from `events.backup`, `SETUP_COMPLETED` from `events.setup`, `ROUTING_CANDIDATE_SELECTED` from `events.routing`, `SHIPPING_HTTP_BATCH_SENT` from `events.shipping`, `EVAL_REPORT_COMPUTED` from `events.evaluation`, `PROMPT_PROFILE_SELECTED` from `events.prompt`, `PROCEDURAL_MEMORY_START` from `events.procedural_memory`, `PERF_LLM_JUDGE_STARTED` from `events.performance`, `TASK_ENGINE_OBSERVER_FAILED` from `events.task_engine`, `TASK_ASSIGNMENT_PROJECT_FILTERED` and `TASK_ASSIGNMENT_PROJECT_NO_ELIGIBLE` from `events.task_assignment`, `EXECUTION_SHUTDOWN_IMMEDIATE_CANCEL`, `EXECUTION_SHUTDOWN_TOOL_WAIT`, `EXECUTION_SHUTDOWN_CHECKPOINT_SAVE`, `EXECUTION_SHUTDOWN_CHECKPOINT_FAILED`, and `EXECUTION_PROJECT_VALIDATION_FAILED` from `events.execution`, `WORKFLOW_EXEC_COMPLETED` from `events.workflow_execution`, `BLUEPRINT_INSTANTIATE_START` from `events.blueprint`, `WORKFLOW_DEF_ROLLED_BACK` from `events.workflow_definition`, `WORKFLOW_VERSION_SAVED` from `events.workflow_version`, `MEMORY_FINE_TUNE_STARTED`, `MEMORY_SELF_EDIT_TOOL_EXECUTE`, `MEMORY_SELF_EDIT_CORE_READ`, `MEMORY_SELF_EDIT_CORE_WRITE`, `MEMORY_SELF_EDIT_CORE_WRITE_REJECTED`, `MEMORY_SELF_EDIT_ARCHIVAL_SEARCH`, `MEMORY_SELF_EDIT_ARCHIVAL_WRITE`, `MEMORY_SELF_EDIT_RECALL_READ`, `MEMORY_SELF_EDIT_RECALL_WRITE`, `MEMORY_SELF_EDIT_WRITE_FAILED` from `events.memory`, `REPORTING_GENERATION_STARTED` from `events.reporting`, `RISK_BUDGET_SCORE_COMPUTED` from `events.risk_budget`, `BUDGET_PROJECT_COST_QUERIED`, `BUDGET_PROJECT_RECORDS_QUERIED`, `BUDGET_PROJECT_BUDGET_EXCEEDED`, `BUDGET_PROJECT_ENFORCEMENT_CHECK`, `BUDGET_PROJECT_COST_AGGREGATED`, `BUDGET_PROJECT_COST_AGGREGATION_FAILED`, and `BUDGET_PROJECT_BASELINE_SOURCE` from `events.budget`, `LLM_STRATEGY_SYNTHESIZED` and `DISTILLATION_CAPTURED` from `events.consolidation`, `MEMORY_DIVERSITY_RERANKED`, `MEMORY_DIVERSITY_RERANK_FAILED`, and `MEMORY_REFORMULATION_ROUND` from `events.memory`, `NOTIFICATION_DISPATCHED` and `NOTIFICATION_DISPATCH_FAILED` from `events.notification`, `QUALITY_STEP_CLASSIFIED` from `events.quality`, `HEALTH_TICKET_EMITTED` from `events.health`, `TRAJECTORY_SCORING_START` from `events.trajectory`, `COORD_METRICS_AMDAHL_COMPUTED` from `events.coordination_metrics`, `COORDINATION_STARTED`, `COORDINATION_COMPLETED`, `COORDINATION_FAILED`, `COORDINATION_PHASE_STARTED`, `COORDINATION_PHASE_COMPLETED`, `COORDINATION_PHASE_FAILED`, `COORDINATION_WAVE_STARTED`, `COORDINATION_WAVE_COMPLETED`, `COORDINATION_TOPOLOGY_RESOLVED`, `COORDINATION_CLEANUP_STARTED`, `COORDINATION_CLEANUP_COMPLETED`, `COORDINATION_CLEANUP_FAILED`, `COORDINATION_WAVE_BUILT`, `COORDINATION_FACTORY_BUILT`, and `COORDINATION_ATTRIBUTION_BUILT` from `events.coordination`, `WEB_REQUEST_START` and `WEB_SSRF_BLOCKED` from `events.web`, `DB_QUERY_START` and `DB_WRITE_BLOCKED` from `events.database`, `TERMINAL_COMMAND_START` and `TERMINAL_COMMAND_BLOCKED` from `events.terminal`, `SUB_CONSTRAINT_RESOLVED` and `SUB_CONSTRAINT_DENIED` from `events.sub_constraint`, `VERSION_SAVED` and `VERSION_SNAPSHOT_FAILED` from `events.versioning`, `ANALYTICS_AGGREGATION_COMPUTED` and `ANALYTICS_RETRY_RATE_ALERT` from `events.analytics`, `CALL_CLASSIFICATION_COMPUTED` from `events.call_classification`, `QUOTA_THRESHOLD_ALERT` and `QUOTA_POLL_FAILED` from `events.quota`, `CONFLICT_DEBATE_EVALUATOR_FAILED` from `events.conflict`, `DELEGATION_LOOP_CIRCUIT_BACKOFF` and `DELEGATION_LOOP_CIRCUIT_PERSIST_FAILED` from `events.delegation`, `MEETING_EVENT_COOLDOWN_SKIPPED` and `MEETING_TASKS_CAPPED` from `events.meeting`, `PERSISTENCE_CIRCUIT_BREAKER_SAVED`, `PERSISTENCE_CIRCUIT_BREAKER_SAVE_FAILED`, `PERSISTENCE_CIRCUIT_BREAKER_LOADED`, `PERSISTENCE_CIRCUIT_BREAKER_LOAD_FAILED`, `PERSISTENCE_CIRCUIT_BREAKER_DELETED`, `PERSISTENCE_CIRCUIT_BREAKER_DELETE_FAILED`, `PERSISTENCE_PROJECT_COST_AGG_INCREMENTED`, `PERSISTENCE_PROJECT_COST_AGG_INCREMENT_FAILED`, `PERSISTENCE_PROJECT_COST_AGG_FETCHED`, `PERSISTENCE_PROJECT_COST_AGG_FETCH_FAILED`, and `PERSISTENCE_PROJECT_COST_AGG_DESERIALIZE_FAILED` from `events.persistence`, `METRICS_SCRAPE_COMPLETED`, `METRICS_SCRAPE_FAILED`, `METRICS_COLLECTOR_INITIALIZED`, `METRICS_COORDINATION_RECORDED`, `METRICS_OTLP_EXPORT_COMPLETED` and `METRICS_OTLP_FLUSHER_STOPPED` from `events.metrics`, `ORG_MEMORY_QUERY_START`, `ORG_MEMORY_QUERY_COMPLETE`, `ORG_MEMORY_QUERY_FAILED`, `ORG_MEMORY_WRITE_START`, `ORG_MEMORY_WRITE_COMPLETE`, `ORG_MEMORY_WRITE_DENIED`, `ORG_MEMORY_WRITE_FAILED`, `ORG_MEMORY_POLICIES_LISTED`, `ORG_MEMORY_BACKEND_CREATED`, `ORG_MEMORY_CONNECT_FAILED`, `ORG_MEMORY_DISCONNECT_FAILED`, `ORG_MEMORY_NOT_CONNECTED`, `ORG_MEMORY_ROW_PARSE_FAILED`, `ORG_MEMORY_CONFIG_INVALID`, `ORG_MEMORY_MODEL_INVALID`, `ORG_MEMORY_MVCC_PUBLISH_APPENDED`, `ORG_MEMORY_MVCC_RETRACT_APPENDED`, `ORG_MEMORY_MVCC_SNAPSHOT_AT_QUERIED`, and `ORG_MEMORY_MVCC_LOG_QUERIED` from `events.org_memory`). Each domain has its own module -- see `src/synthorg/observability/events/` for the full inventory of constants. Import directly: `from synthorg.observability.events.<domain> import EVENT_CONSTANT`
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
- **Parallelism**: `pytest-xdist` via `-n 8` -- **ALWAYS** include `-n 8` when running pytest locally, never run tests sequentially. CI uses `-n auto` (fewer cores on runners).
- **Parametrize**: Prefer `@pytest.mark.parametrize` for testing similar cases
- **Vendor-agnostic everywhere**: NEVER use real vendor names (Anthropic, OpenAI, Claude, GPT, etc.) in project-owned code, docstrings, comments, tests, or config examples. Use generic names: `example-provider`, `example-large-001`, `example-medium-001`, `example-small-001`, `large`/`medium`/`small` as aliases. Vendor names may only appear in: (1) Operations design page provider list (`docs/design/operations.md`), (2) `.claude/` skill/agent files, (3) third-party import paths/module names (e.g. `litellm.types.llms.openai`), (4) provider presets (`src/synthorg/providers/presets.py`) which are user-facing runtime data. Tests must use `test-provider`, `test-small-001`, etc.
- **Property-based testing**: Python uses [Hypothesis](https://hypothesis.readthedocs.io/) (`@given` + `@settings`), React uses [fast-check](https://fast-check.dev/) (`fc.assert` + `fc.property`), Go uses native `testing.F` fuzz functions (`Fuzz*`). Hypothesis profiles configured in `tests/conftest.py`: `ci` (deterministic, `max_examples=10` + `derandomize=True` -- fixed seed per test, same inputs every run), `dev` (1000 examples), `fuzz` (10,000 examples, no deadline -- for dedicated fuzzing sessions), `extreme` (500,000 examples, no deadline -- overnight deep fuzzing). Controlled via `HYPOTHESIS_PROFILE` env var. `.hypothesis/` is gitignored. Failing examples are persisted to `~/.synthorg/hypothesis-examples/` (write-only shared DB, survives worktree deletion) via `_WriteOnlyDatabase` in `tests/conftest.py`.
- **Hypothesis workflow**: CI runs 10 deterministic examples per property test (`derandomize=True` -- same inputs every run, no flakes). Random fuzzing runs locally: `HYPOTHESIS_PROFILE=dev uv run python -m pytest tests/ -m unit -n 8 -k properties` (quick, 1000 examples) or `HYPOTHESIS_PROFILE=fuzz uv run python -m pytest tests/ -m unit -n 8 --timeout=0` (deep, 10,000 examples, no deadline, all `@given` tests -- `--timeout=0` disables the 30s per-test limit that would kill long-running property tests; `-k properties` is intentionally omitted to cover all 46 files with `@given`, not just the 12 `*_properties.py` files). When Hypothesis finds a failure, it is a **real bug** -- the shrunk example is saved to `~/.synthorg/hypothesis-examples/` for analysis but is **not replayed** automatically (that would block all test runs). Do NOT just rerun and move on. Read the failing example from the output, fix the underlying bug, and add an explicit `@example(...)` decorator to the test so the case is permanently covered in CI.
- **Flaky tests**: NEVER skip, dismiss, or ignore flaky tests -- always fix them fully and fundamentally. For timing-sensitive tests, mock `time.monotonic()` and `asyncio.sleep()` to make them deterministic instead of widening timing margins. For tasks that must block indefinitely until cancelled (e.g. simulating a slow provider or stubborn coroutine), use `asyncio.Event().wait()` instead of `asyncio.sleep(large_number)` -- it is cancellation-safe and carries no timing assumptions.

## Git

- **Commits**: `<type>: <description>` -- types: feat, fix, refactor, docs, test, chore, perf, ci
- **Enforced by**: commitizen (commit-msg hook)
- **Signed commits**: required on `main` via branch protection -- all commits must be GPG/SSH signed
- **Branches**: `<type>/<slug>` from main
- **Pre-commit hooks**: trailing-whitespace, end-of-file-fixer, check-yaml, check-toml, check-json, check-merge-conflict, check-added-large-files, no-commit-to-branch (main), ruff check+format, gitleaks, hadolint (Dockerfile linting), golangci-lint + go vet (CLI, conditional on `cli/**/*.go`), no-em-dashes, no-redundant-timeout, eslint-web (web dashboard, zero warnings, conditional on `web/src/**/*.{ts,tsx}`)
- **Hookify rules** (committed in `.claude/hookify.*.md`):
  - `block-pr-create`: blocks direct `gh pr create` (must use `/pre-pr-review`)
  - `enforce-parallel-tests`: enforces `-n 8` with pytest
  - `no-cd-prefix`: blocks `cd` prefix in Bash commands
  - `no-local-coverage`: blocks `--cov` flags locally (CI handles coverage)
- **Pre-push hooks**: mypy type-check (affected modules only) + pytest unit tests (affected modules only) + golangci-lint + go vet + go test (CLI, conditional on `cli/**/*.go`) + eslint-web (web dashboard) (fast gate before push, skipped in pre-commit.ci -- dedicated CI jobs already run these). Foundational module changes (core, config, observability) or conftest changes trigger full runs.
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
