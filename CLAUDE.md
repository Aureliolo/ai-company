# CLAUDE.md -- SynthOrg

## Project

- **What**: Framework for building synthetic organizations -- autonomous AI agents orchestrated as a virtual company
- **Python**: 3.14+ (PEP 649 native lazy annotations)
- **License**: BUSL-1.1 with narrowed Additional Use Grant (free production use for non-competing small orgs; converts to Apache 2.0 three years after release)
- **Layout**: `src/synthorg/` (src layout), `tests/` (unit/integration/e2e), `web/` (React 19 dashboard), `cli/` (Go CLI binary)
- **Design**: [DESIGN_SPEC.md](docs/DESIGN_SPEC.md) (pointer to `docs/design/` pages)

## Design Spec (MANDATORY)

- **ALWAYS read the relevant `docs/design/` page** before implementing any feature or planning any issue. [DESIGN_SPEC.md](docs/DESIGN_SPEC.md) is a pointer file linking to the 20 design pages.
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

## Diagrams in Documentation

- **D2** (`\`\`\`d2`): architecture diagrams, nested container layouts, complex entity relationships. Rendered at build time via `mkdocs-d2-plugin` (dagre layout). Requires the [D2 CLI](https://d2lang.com/tour/install) on `PATH` locally and in CI (pinned to v0.7.1 via `.github/workflows/pages.yml`).
- **Mermaid** (`\`\`\`mermaid`): flowcharts, sequence diagrams, simple hierarchies, pipelines. Rendered client-side via `pymdownx.superfences`.
- **Markdown tables**: grid/matrix data that is semantically tabular (not diagrams).
- D2 uses theme 200 (Dark Mauve), dark-only render -- configured globally in `mkdocs.yml`.
- Never use `\`\`\`text` blocks with ASCII/Unicode box-drawing characters for diagrams.
- Review agent `diagram-syntax-validator` runs in `/pre-pr-review` and `/aurelio-review-pr` pipelines.

## Quick Commands

```bash
uv sync                                    # install all deps (dev + test)
uv sync --group docs                       # install docs toolchain (zensical + D2 plugins; required before zensical commands on first clone)
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
atlas migrate diff --env sqlite <name>     # generate SQLite migration from schema.sql diff
atlas migrate diff --env postgres <name>   # generate Postgres migration (requires Docker for dev DB)
atlas migrate validate --dir "file://src/synthorg/persistence/sqlite/revisions"    # validate SQLite migration checksums
atlas migrate validate --dir "file://src/synthorg/persistence/postgres/revisions"  # validate Postgres migration checksums
atlas schema diff --env sqlite             # drift detection for SQLite (schema.sql vs revisions)
atlas schema diff --env postgres           # drift detection for Postgres (schema.sql vs revisions)
bash scripts/squash_migrations.sh          # squash old migrations (release-time)
uv run python scripts/export_openapi.py    # export OpenAPI schema (needed before docs build)
uv run python scripts/generate_comparison.py  # generate comparison page (needed before docs build)
PYTHONPATH=. uv run zensical build          # build docs (output: _site/docs/) -- PYTHONPATH=. enables d2_fence.py for D2 rendering
PYTHONPATH=. uv run zensical serve          # local docs preview (http://127.0.0.1:8000)
```

### Web Dashboard

See `web/CLAUDE.md` for commands, design system, and component inventory. The CI-matching full-suite leak check is `npm --prefix web run test -- --coverage --detect-async-leaks` (the `Leaks N leaks` summary must stay at or below the `MAX_ASYNC_LEAKS` ceiling defined in `.github/workflows/ci.yml`; any new store that schedules timers must expose a teardown hook per `web/CLAUDE.md`).

### CLI (Go Binary)

See `cli/CLAUDE.md` for commands, flags, and reference. Key rule: use `go -C cli` (never `cd cli`).

## Reference (load on demand)

See [docs/reference/claude-reference.md](docs/reference/claude-reference.md) for: Documentation layout, Docker commands, Package Structure, Releasing, CI pipelines, Dependencies.

## Web Dashboard Design System (MANDATORY)

See `web/CLAUDE.md` for the full component inventory, design token rules, and post-training references (TS6, Storybook 10). Key rules:
- **ALWAYS reuse** existing components from `web/src/components/ui/` before creating new ones
- **NEVER hardcode** hex colors, font-family, pixel spacing, or Motion transitions -- use design tokens and `@/lib/motion` presets
- **NEVER hardcode** BCP 47 locale strings (e.g. `'en-US'`) or call bare `.toLocaleString()` -- use the helpers in `@/utils/format` which read `getLocale()` from `@/utils/locale`
- A PostToolUse hook (`scripts/check_web_design_system.py`) enforces these rules on every Edit/Write to `web/src/` (colors, fonts, Motion durations, hardcoded locales, bare `.toLocale*String()` calls, missing Storybook stories, duplicate component patterns)

## Regional Defaults (MANDATORY)

No default may privilege a single region, currency, or locale. Every user-facing format resolves from: user/company setting -> browser/system -> neutral fallback.

- **Currency**: never hardcode ISO 4217 codes (`'USD'`, `'EUR'`, `'GBP'`, ...) or symbols (`$`, `€`, `£`) in production code. Backend: use `DEFAULT_CURRENCY` from `synthorg.budget.currency` or read the runtime `budget.currency` setting. Frontend: import `DEFAULT_CURRENCY` from `@/utils/currencies` or read `useSettingsStore().currency`. Allowlisted files: the backend symbol table (`budget/currency.py`), the dropdown options (`web/src/utils/currencies.ts`), and the `DEFAULT_CURRENCY` re-export in `format.ts`.
- **Field naming**: no `_usd` suffix on money fields (backend, API DTOs, TS types, DB columns). The field value is in the operator's configured currency; the type carries the money semantics, not the name.
- **Locale**: never hardcode BCP 47 tags (`'en-US'`, `'de-DE'`, ...) or call bare `.toLocaleString()` / `.toLocaleDateString()` / `.toLocaleTimeString()`. Use helpers in `@/utils/format`, all of which read `getLocale()` from `@/utils/locale`. Frontend fallback is plain `'en'` (neutral English). Backend exposes a `display.locale` setting that overrides the browser default when set.
- **Timezone**: store UTC everywhere; render in the user's browser timezone via `Intl` without passing a `timeZone` option.
- **Date / number format**: always via `Intl`; no `MM/DD/YYYY` / `DD/MM/YYYY` / comma-separator templates.
- **Units**: metric only. Paper size A4 if print flows are ever added.
- **Spelling**: American English is the UI default (`color`, `initialize`). Document deviations; do not mix.

- **Monetary models**: every cost-bearing Pydantic model (``CostRecord``, ``TaskMetricRecord``, ``LlmCalibrationRecord``, ``AgentRuntimeState``) carries ``currency: CurrencyCode`` (ISO 4217, validated against the allowlist in ``synthorg.budget.currency``). Every aggregation site (``CostTracker``, ``ReportGenerator``, ``CostOptimizer``, HR ``WindowMetrics``) enforces a same-currency invariant; mixing currencies raises ``MixedCurrencyAggregationError`` (HTTP 409).

Enforced by `scripts/check_web_design_system.py` (PostToolUse hook on every `web/src/` edit) for the frontend surface, and by `scripts/check_backend_regional_defaults.py` (PostToolUse hook on every `src/synthorg/` edit) for the Python backend. Both hooks flag hardcoded currency codes, currency symbols adjacent to digits (`"$10"`, `"\u20ac50"`), identifiers ending in `_usd`, BCP 47 locale literals (`'en-US'`), and `localhost:<port>` in application code. Legitimate opt-outs use a `# lint-allow: regional-defaults` (Python) or `// lint-allow: regional-defaults` (TS) marker on or above the line. A stricter CI-gated `scripts/check_forbidden_literals.py` runs in pre-push and GitHub Actions to catch the same issues on non-Claude commits.

## Persistence Boundary (MANDATORY)

- `src/synthorg/persistence/` is the **only** place that may import `aiosqlite`, `sqlite3`, `psycopg`, or `psycopg_pool`, or emit raw SQL DDL/DML keywords in string literals.
- Sanctioned exceptions cover three categories: (1) the two agent-facing DB tools (`src/synthorg/tools/database/schema_inspect.py`, `src/synthorg/tools/database/sql_query.py`), (2) security/scanning utilities that inspect user-supplied SQL (e.g. `src/synthorg/security/rules/destructive_op_detector.py`, whose detection payload *is* DDL keyword strings), and (3) test fixtures / conformance harnesses that hold driver primitives for cross-subsystem setup. The authoritative list lives in `_ALLOWLIST` inside `scripts/check_persistence_boundary.py`; any new exception must be added there with a justifying comment.
- Every durable feature MUST define a repository Protocol in `persistence/<domain>_protocol.py`, concrete impls under `persistence/{sqlite,postgres}/`, and be exposed on `PersistenceBackend`.
- **In-memory fallbacks** (`persistence/integration_stubs.py`) are named `InMemoryXRepository` (NOT `StubXRepository`) to signal that they are *working* repositories -- just process-local and non-durable. These still require durable SQLite + Postgres counterparts (tracked in issue #1517); the `InMemory*` naming does not relax that obligation.
- Controllers and API endpoints access persistence through domain-scoped **service layers** (`ArtifactService`, `WorkflowService`, `MemoryService`, `CustomRulesService`, `UserService`) rather than reaching into repositories directly. Services keep controllers thin (parse / shape / return), centralise `PERSISTENCE_*` / `API_USER_*` / `META_CUSTOM_RULE_*` / `WORKFLOW_DEF_*` audit logging in one place, and own cross-repo orchestration (e.g. workflow-definition delete cascading to version snapshots). Repositories should not log mutations themselves -- the service layer is the canonical logging point so audit trails do not duplicate when multiple callers share a repo.
- Adding a migration: read `docs/guides/persistence-migrations.md` first. Do not hand-edit SQL in `persistence/{sqlite,postgres}/revisions/`, and do not edit `atlas.sum`. Rehashing via `atlas migrate hash` post-release is blocked by a PreToolUse hook -- delete the in-progress migration and regenerate with `atlas migrate diff` instead.
- Per-line opt-out: `# lint-allow: persistence-boundary -- <required justification>` as a trailing comment. Justification after `--` must be non-empty.
- Enforced by `scripts/check_persistence_boundary.py` (pre-push hook + CI Lint job).

## Shell Usage

- **NEVER use `cd` in Bash commands** -- the working directory is already set to the project root. Use absolute paths or run commands directly. Do NOT prefix commands with `cd C:/Users/Aurelio/synthorg &&`. Exception: `bash -c "cd <dir> && <cmd>"` is safe (runs in a child process, no cwd side effects). Use this for tools without a `-C` flag -- e.g. `bash -c "cd web && npm install"` since `npm --prefix` is broken for bare `npm install`.
- **NEVER use Bash to write or modify files** -- use the Write or Edit tools. Do not use `cat >`, `cat << EOF`, `echo >`, `echo >>`, `sed -i`, `python -c "open(...).write(...)"`, or `tee` to create or modify files (read-only/inspection uses like piping to stdout are fine). This applies to all files (plan files, config files, source code) and all subagents.

## Code Conventions

- **No `from __future__ import annotations`** -- Python 3.14 has PEP 649
- **PEP 758 except syntax**: use `except A, B:` (no parentheses) when NOT binding to a name -- ruff enforces this on Python 3.14. When binding via `as exc`, parentheses are still required (`except (A, B) as exc:`) because Python 3.14's grammar forbids the unparenthesized form with `as`.
- **Type hints**: all public functions, mypy strict mode
- **Docstrings**: Google style, required on public classes/functions (enforced by ruff D rules)
- **Immutability**: create new objects, never mutate existing ones. For non-Pydantic internal collections (registries, `BaseTool`), use `copy.deepcopy()` at construction + `MappingProxyType` wrapping for read-only enforcement. For `dict`/`list` fields in frozen Pydantic models, rely on `frozen=True` for field reassignment prevention and `copy.deepcopy()` at system boundaries (tool execution, LLM provider serialization, inter-agent delegation, serializing for persistence).
- **Config vs runtime state**: frozen Pydantic models for config/identity; separate mutable-via-copy models (using `model_copy(update=...)`) for runtime state that evolves (e.g. agent execution state, task progress). Never mix static config fields with mutable runtime fields in one model.
- **Models**: Pydantic v2 (`BaseModel`, `model_validator`, `computed_field`, `ConfigDict`). Adopted conventions: use `allow_inf_nan=False` in all `ConfigDict` declarations to reject `NaN`/`Inf` in numeric fields at validation time; use `@computed_field` for derived values instead of storing + validating redundant fields (e.g. `TokenUsage.total_tokens`); use `NotBlankStr` (from `core.types`) for all identifier/name fields -- including optional (`NotBlankStr | None`) and tuple (`tuple[NotBlankStr, ...]`) variants -- instead of manual whitespace validators.
- **Async concurrency**: prefer `asyncio.TaskGroup` for fan-out/fan-in parallel operations in new code (e.g. multiple tool invocations, parallel agent calls). Prefer structured concurrency over bare `create_task`. Existing code is being migrated incrementally. When running multiple tasks inside a `TaskGroup` where one task's failure should NOT cancel the others (independent workers, classification detectors, notification sinks), wrap each task body in a small `async def` helper that catches `Exception` and returns a safe default (re-raising only `MemoryError`/`RecursionError`); never let a single worker abort the whole group.
- **Untrusted-content fences at LLM call sites (SEC-1)**: any attacker-controllable string (task title/description, acceptance criteria, artifact payloads, tool results, code diffs, multi-tenant strategy config) interpolated into an LLM prompt must be wrapped via `wrap_untrusted(tag, content)` from `synthorg.engine.prompt_safety`, and the enclosing system prompt must append `untrusted_content_directive(tags)` so the model is explicitly told those fences contain untrusted data. Standard tags: `TAG_TASK_DATA`, `TAG_TASK_FACT`, `TAG_UNTRUSTED_ARTIFACT`, `TAG_TOOL_RESULT`, `TAG_CODE_DIFF`, `TAG_CONFIG_VALUE`, `TAG_CRITERIA_JSON`. The helper escapes literal `</tag>` in content (case-insensitively, including whitespace-terminated variants like `</tag >` or `</tag\t>`) to prevent fence breakout. Seven existing call sites use this pattern -- see `format_task_instruction`, `TaskLedgerMiddleware`, `LLMRubricGrader._prepare_payload_text`, `_wrap_tool_result`, `build_review_message` (semantic_llm_prompt), `build_strategic_prompt_sections`, and `_encode_decomposer_payload` as references. Tool-result interpolation additionally runs an advisory injection-pattern detector (`TOOL_INJECTION_PATTERN_DETECTED`) covering closing-tag look-alikes for every standard fence (`</task-data>`, `</task-fact>`, `</tool-result>`, `</untrusted-artifact>`, `</code-diff>`, `</config-value>`, `</criteria-json>`) plus common override phrases; the telemetry sample is scrubbed via `scrub_secret_tokens` before logging.
- **HTML parsing (SEC-1)**: never call `lxml.html.fromstring` directly on attacker-controlled input. Use `HTMLParseGuard` in `synthorg.tools.html_parse_guard`, which pre-scans for DOCTYPE with SYSTEM/PUBLIC identifiers and any `<!ENTITY>` declaration (rejecting via `XXEDetectedError`, `is_retryable = False`) before parsing with a module-scope `lxml.html.HTMLParser(no_network=True, remove_blank_text=True, recover=True, huge_tree=False)`. `sanitize()` catches `XXEDetectedError` explicitly so the pre-scan's `TOOL_HTML_PARSE_XXE_DETECTED` event is the single log entry per rejection (no duplicate `TOOL_HTML_PARSE_ERROR`), and generic parse failures log `error=safe_error_description(exc)` without `exc_info=True` so attacker-controlled payload bytes are not serialised via traceback frame locals.
- **Pluggable subsystems**: new cross-cutting subsystems (e.g. classification detectors, context loaders, notification sinks, retention policies, verification graders) follow a protocol + strategy + factory + config discriminator pattern. Define a `Protocol` interface, ship concrete strategies that implement it, register them in a factory keyed by a config discriminator, and plumb the active selection through frozen config. Ship safe defaults so the behaviour is opt-in, never a silent regression. Canonical examples:
  - `engine/classification/protocol.py` (`Detector`, `ScopedContextLoader`, `ClassificationSink`) + `budget/coordination_config.py` dispatcher
  - `engine/quality/decomposer_protocol.py` (`CriteriaDecomposer`) + `engine/quality/grader_protocol.py` (`RubricGrader`) + `engine/quality/verification_factory.py` + `engine/quality/verification_config.py`
  - `meta/chief_of_staff/protocol.py` (`OutcomeStore`, `ConfidenceAdjuster`, `OrgInflectionSink`, `AlertSink`) + `meta/chief_of_staff/config.py` discriminator + `meta/factory.py::build_confidence_adjuster()`
  - `meta/telemetry/protocol.py` (`AnalyticsEmitter`, `AnalyticsCollector`, `RecommendationProvider`) + `meta/telemetry/config.py` discriminator + `meta/telemetry/factory.py::build_analytics_emitter()`
  - `meta/rollout/clock.py` (`Clock`) + `meta/rollout/roster.py` (`OrgRoster`) + `meta/rollout/group_aggregator.py` (`GroupSignalAggregator`) + `meta/rollout/inverse_dispatch.py` (`RollbackHandler` + 4 mutator protocols) + `meta/factory.py::build_rollout_strategies()` + `build_rollback_executor()` -- all plumbed through frozen `SelfImprovementConfig`, with safe defaults (`RealClock`, `NoOpOrgRoster`, null aggregator) so the behaviour is opt-in
  - `api/rate_limits/protocol.py` (`SlidingWindowStore`) + `api/rate_limits/in_memory.py` + `api/rate_limits/config.py::PerOpRateLimitConfig` discriminator + `api/rate_limits/factory.py::build_sliding_window_store()`
  - `api/rate_limits/inflight_protocol.py` (`InflightStore`) + `api/rate_limits/in_memory_inflight.py` + `api/rate_limits/inflight_config.py::PerOpConcurrencyConfig` discriminator + `api/rate_limits/inflight_factory.py::build_inflight_store()` + `api/rate_limits/inflight_middleware.py::PerOpConcurrencyMiddleware` (Litestar middleware that reads `opt[per_op_concurrency]` from each route handler)
  - `communication/conflict_resolution/escalation/protocol.py` (`EscalationQueueStore`, `DecisionProcessor`) + in-memory/SQLite/Postgres implementations + `communication/conflict_resolution/escalation/config.py::EscalationQueueConfig` discriminator + `communication/conflict_resolution/escalation/factory.py::build_escalation_queue_store()`

  Note: the **service layer** in the Persistence Boundary section above is a distinct pattern. A service wraps one or more repositories to keep controllers thin and centralise audit logging, and MAY orchestrate multiple repositories (e.g. `WorkflowService` spans `workflow_definitions` + `workflow_versions`, `MemoryService` spans fine-tune checkpoints + runs + settings). The Protocol + Strategy + Factory + Config pattern applies only to genuinely cross-cutting subsystems that ship multiple interchangeable implementations selectable at runtime; services do not need that machinery because there is exactly one service per domain.
- **Line length**: 88 characters (ruff)
- **Functions**: < 50 lines, files < 800 lines
- **Errors**: handle explicitly, never silently swallow
- **Validate**: at system boundaries (user input, external APIs, config files)

## Logging

- **Every module** with business logic MUST have: `from synthorg.observability import get_logger` then `logger = get_logger(__name__)`
- **Never** use `import logging` / `logging.getLogger()` / `print()` in application code (exception: `observability/setup.py`, `observability/sinks.py`, `observability/syslog_handler.py`, `observability/http_handler.py`, and `observability/otlp_handler.py` may use stdlib `logging` and `print(..., file=sys.stderr)` for handler construction, bootstrap, and error reporting code that runs before or during logging system configuration)
- **Variable name**: always `logger` (not `_logger`, not `log`)
- **Event names**: always use constants from the domain-specific module under `synthorg.observability.events` (e.g., `API_REQUEST_STARTED` from `events.api`, `TOOL_INVOKE_START` from `events.tool`). Each domain has its own module -- see `src/synthorg/observability/events/` for the full inventory of constants. Import directly: `from synthorg.observability.events.<domain> import EVENT_CONSTANT`
- **Structured kwargs**: always `logger.info(EVENT, key=value)` -- never `logger.info("msg %s", val)`
- **All error paths** must log at WARNING or ERROR with context before raising
- **All state transitions** must log at INFO
- **DEBUG** for object creation, internal flow, entry/exit of key functions
- Pure data models, enums, and re-exports do NOT need logging
- **Secret-log redaction (SEC-1)**: on credential-bearing paths (OAuth flows, secret backends, settings encryption, A2A client/gateway, API auth middleware, persistence repos), never use `logger.exception(EVENT, error=str(exc))` -- it attaches a traceback whose serialized frame-locals can leak `client_secret` / `refresh_token` / Fernet ciphertext, and `str(exc)` on httpx errors often embeds the POST body. Use `logger.warning(EVENT, error_type=type(exc).__name__, error=safe_error_description(exc))` instead (`from synthorg.observability import safe_error_description`). Caller-facing detail is preserved via `raise ... from exc`. The `scrub_event_fields` structlog processor provides belt-and-braces masking on every log record (covering escaped-quote JSON values, URL form values with stray `%` bytes, and `Authorization:` headers), and `scripts/check_logger_exception_str_exc.py` is a pre-commit gate that blocks new `logger.exception(..., error=str(exc))` sites above the `scripts/_logger_exception_baseline.json` baseline. The gate matches bare `logger`, attribute-chain loggers (`self._logger`, `audit_logger`, etc.) and `str(...)` of `Name`/`Attribute`/`Subscript` expressions so swapping sites within a file is caught by location diff, not by a count that could tie.

## MCP Handler Layer

SynthOrg exposes 204 tools across 15 domains via its MCP server. Tools are classified by capability action (`read_tool` / `write_tool` / `admin_tool`) via the builders in `src/synthorg/meta/mcp/tool_builder.py`; only the `admin_tool` subset is destructive and subject to the guardrail triple. Adding a new handler means implementing the `ToolHandler` protocol in `src/synthorg/meta/mcp/handlers/<domain>.py`:

- **Signature**: `async def _<tool>(*, app_state, arguments, actor: AgentIdentity | None = None) -> str`. The `actor` kwarg threads calling-agent identity through the invoker so destructive-op guardrails can attribute audit records. Handlers that don't care about identity still accept and ignore it.
- **Envelope**: return a JSON string built by helpers in `src/synthorg/meta/mcp/handlers/common.py` -- `ok(data, pagination=...)` for success, `err(exc)` for caught errors, `not_supported(tool, reason)` when the service facade is not yet wired. Never emit a bare `{"status": "not_implemented"}` payload; `make_placeholder_handler` delegates to `not_supported()` so every unwired tool ships the single agreed envelope.
- **Argument validation**: use `require_arg(arguments, key, ty)` for typed required extraction; catch `ArgumentValidationError` and return `err(exc)` (envelope picks up `domain_code="invalid_argument"`). Never let raw `TypeError`/`ValueError` escape from `int(...)` / enum coercion -- wrap them and call `invalid_argument(name, expected)`.
- **Destructive ops**: call `require_destructive_guardrails(arguments, actor)` first. It enforces non-`None` `actor`, literal `confirm=True`, non-blank `reason`, and raises `GuardrailViolationError` with a typed `violation: Literal["missing_actor","missing_confirm","missing_reason"]`. Emit `MCP_DESTRUCTIVE_OP_EXECUTED` exactly once per successful destructive call for the audit trail. Schema-level reject whitespace reasons with `"minLength": 1, "pattern": r".*\S.*"`.
- **Registries**: export `XXX_HANDLERS: Mapping[str, ToolHandler] = MappingProxyType({...})` so the registry is read-only. `build_handler_map()` aggregates across domains and raises on duplicate keys.
- **Domain codes**: standard wire codes are `invalid_argument`, `guardrail_violated`, `not_supported`, `not_found`, `conflict`. Set custom codes via `err(exc, domain_code="...")` when needed; `err` falls back to `exc.domain_code` automatically on `ArgumentValidationError` / `GuardrailViolationError`.
- **Persistence boundary still applies**: handlers route through service-layer facades (`MemoryService`, etc.), never into `app_state.persistence.*` directly. Reads that need the total count alongside a page should make the service return `(items, total)`.

See `docs/design/tools.md` §"SynthOrg MCP Tool Surface" for the full contract and `docs/design/observability.md` §"MCP handler events" for the event inventory.

## Telemetry (Product)

- **Opt-in, off by default.** Enable with `SYNTHORG_TELEMETRY=true` or the `telemetry.enabled` setting. Delivery backend is Logfire; missing token or extra downgrades to the noop reporter silently.
- **Privacy by allowlist.** Every event property must be explicitly listed in `src/synthorg/telemetry/privacy.py::_ALLOWED_PROPERTIES` keyed by event type. Unknown keys raise `PrivacyViolationError` and are dropped before delivery. Forbidden key patterns (`key`, `token`, `secret`, `password`, `content`, `message`, `prompt`, `description`, `credential`, `bearer`, `auth`) are rejected even if allowlisted. String values are capped at `synthorg.telemetry.config.MAX_STRING_LENGTH` (64 chars).
- **Environment resolution chain** (first match wins, in `synthorg.telemetry.collector._resolve_environment`):
  1. `SYNTHORG_TELEMETRY_ENV` (operator override) -- always wins
  2. CI auto-detection: `CI`, `GITLAB_CI`, `BUILDKITE`, `JENKINS_URL`, any `RUNPOD_*` -> `"ci"`
  3. `SYNTHORG_TELEMETRY_ENV_BAKED` (Dockerfile `ARG DEPLOYMENT_ENV` baked in at build; CI sets `prod` / `pre-release` / `dev`)
  4. `TelemetryConfig.environment` (default `"dev"`)
- **Docker daemon enrichment** at startup via `synthorg.telemetry.host_info.fetch_docker_info` (uses `aiodocker`). Requires `/var/run/docker.sock` bind-mounted (sandbox overlay / `synthorg init --sandbox true`). Allowlisted fields: `docker_server_version`, `docker_operating_system`, `docker_os_type`, `docker_os_version`, `docker_architecture`, `docker_kernel_version`, `docker_storage_driver`, `docker_default_runtime`, `docker_isolation`, `docker_ncpu`, `docker_mem_total`, `docker_gpu_runtime_nvidia_available`. When the socket isn't mounted or the daemon is unreachable, the event carries `docker_info_available=False` + a categorical `docker_info_unavailable_reason`.
- **Adding a new event or property**: keep `host_info._extract()`, the `DockerHostInfo` TypedDict, and the scrubber's `_ALLOWED_PROPERTIES` entry for the event type in sync. New allowlisted keys must not match a forbidden pattern. Never bypass the scrubber.

## Resilience

- **All provider calls** go through `BaseCompletionProvider` which applies retry + rate limiting automatically
- **Never** implement retry logic in driver subclasses or calling code -- it's handled by the base class
- **RetryConfig** and **RateLimiterConfig** are set per-provider in `ProviderConfig`
- **Retryable errors** (`is_retryable=True`): `RateLimitError`, `ProviderTimeoutError`, `ProviderConnectionError`, `ProviderInternalError`
- **Non-retryable errors** raise immediately without retry
- **`RetryExhaustedError`** signals that all retries failed -- the engine layer catches this to trigger fallback chains
- **Rate limiter** respects `RateLimitError.retry_after` from providers -- automatically pauses future requests

## Test Regression (MANDATORY)

When tests fail due to timeout, slowness, or xdist resource contention:
- **NEVER** delete tests, skip tests, or mark them `xfail` to "fix" slowness
- **NEVER** use `--no-verify` to bypass pre-push hooks
- **NEVER** modify `tests/baselines/unit_timing.json` -- baseline updates require explicit user approval (enforced by `scripts/check_no_edit_baseline.sh` PreToolUse hook)
- **FIRST** run: `uv run python -m pytest tests/unit/ -m unit -n 8 --durations=50 --durations-min=0.5 -q --no-header` to identify the slow tests
- **THEN** compare against `tests/baselines/unit_timing.json` (the known-good baseline)
- **IF** suite time exceeds `baseline * 1.3`: this is a **source code regression**, not a test bug -- fix the source code that caused the regression, not the tests
- The `pytest_sessionfinish` hook in `tests/conftest.py` will warn loudly if a regression is detected -- trust the warning

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
- **Pre-commit hooks**: trailing-whitespace, end-of-file-fixer, check-yaml, check-toml, check-json, check-merge-conflict, check-added-large-files, no-commit-to-branch (main), ruff check+format, gitleaks, hadolint (Dockerfile linting), golangci-lint + go vet (CLI, conditional on `cli/**/*.go`), no-em-dashes, no-redundant-timeout, check-single-migration-per-pr (at most 1 new migration per backend per PR), check-no-modify-migration (block editing existing migrations; bypass with `SYNTHORG_MIGRATION_SQUASH=1`). **Note**: `eslint-web` runs at **pre-push only** (see Pre-push hooks below) -- TypeScript project-graph boot is 15-30s, so gating it on every commit penalises backend-only work.
- **Hookify rules** (committed in `.claude/hookify.*.md`):
  - `block-pr-create`: blocks direct `gh pr create` (must use `/pre-pr-review`)
  - `enforce-parallel-tests`: enforces `-n 8` with pytest
  - `no-cd-prefix`: blocks `cd` prefix in Bash commands
  - `no-local-coverage`: blocks `--cov` flags locally (CI handles coverage)
- **Pre-push hooks**: mypy type-check (affected modules only) + pytest unit tests (affected modules only) + golangci-lint + go vet + go test (CLI, conditional on `cli/**/*.go`) + eslint-web (web dashboard) (fast gate before push, skipped in pre-commit.ci -- dedicated CI jobs already run these). Foundational module changes (core, config, observability) or conftest changes trigger full runs.
- **Pre-commit.ci**: autoupdate disabled (`autoupdate_schedule: never`) -- Renovate owns hook version bumps via `pre-commit` manager
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
