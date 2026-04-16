---
description: "Full codebase audit: launches 58 specialized agents to find issues across Python/React/Go, writes findings to _audit/findings/, then triages with user"
argument-hint: "<scope: full | src/ | web/ | cli/ | docs/> [--report-only] [--quick]"
allowed-tools: ["Agent", "Bash", "Read", "Write", "Edit", "Glob", "Grep", "AskUserQuestion", "mcp__github__issue_write", "mcp__github__issue_read", "mcp__github__list_issues", "mcp__github__search_issues"]
---

# /codebase-audit -- Full Codebase Audit

Launch 58 specialized agents to audit the entire codebase (or a targeted scope), write findings to `_audit/findings/`, build an index, and triage with the user.

## Key Principles

1. **File-based output** -- agents write to `_audit/findings/`, not in-session. Scales to 50+ agents.
2. **One concern per agent** -- each agent searches for exactly ONE type of issue.
3. **Architecture context in every prompt** -- no blind agents. All get the Architecture Brief.
4. **Severity-tagged findings** -- critical/high/medium/low/info with file:line references.
5. **Triage together** -- user reviews INDEX.md before any issues are created.
6. **Rerunnable** -- cleans `_audit/` on start.

---

## Phase 0: Parse Arguments & Setup

### Parse scope

| Argument | Directories | Agent Waves |
|----------|-------------|-------------|
| `full` (default) | All | All 10 waves (58 agents) |
| `src/` | `src/synthorg/`, `tests/` | Waves 1-5, 7, 9 (Python-focused) |
| `web/` | `web/src/` | Wave 8 + relevant from 2-3 |
| `cli/` | `cli/` | Wave 10 only |
| `docs/` | `docs/`, `site/` | Wave 4 (TODOs) + spec drift from Wave 9 |

Flags:
- `--report-only` -- skip issue creation, findings files only
- `--quick` -- skip deep-dive on zero-finding categories

### Setup output directory

```bash
rm -rf _audit && mkdir -p _audit/findings
```

Verify `_audit/` is in `.gitignore`. If not, add it.

---

## Phase 1: Build Architecture Brief

Read these files to build context injected into EVERY agent prompt:

1. `src/synthorg/observability/__init__.py` + `_logger.py` -- logging stack
2. `src/synthorg/observability/events/` -- list all event constant modules
3. `src/synthorg/api/auto_wire.py` -- service wiring
4. `src/synthorg/api/app.py` -- route registration
5. `web/src/router/routes.ts` -- frontend routing
6. `web/src/stores/` -- list all stores
7. `docs/DESIGN_SPEC.md` -- spec index
8. Existing open issues: `gh issue list --state open --limit 200 --json number,title,labels`

Produce an **Architecture Brief** (~300 words) covering:
- Logging: `get_logger(__name__)`, structlog, event constants in `observability/events/`, structured kwargs
- Wiring: `auto_wire.py` phases, controller registration, factory pattern
- Frontend: router structure, Zustand stores, API layer
- Conventions: immutability, frozen Pydantic, `NotBlankStr`, vendor-agnostic naming, error hierarchy
- Testing: markers, xdist, async auto mode, Hypothesis

This brief is a string variable reused in all agent prompts below.

---

## Phase 2: Launch Agents

### Finding File Format

Every agent MUST write its output file using this exact format:

```markdown
# [Agent Title]

**Scope**: [directories/files searched]
**Files scanned**: [approximate count]
**Findings**: [count]

## Findings

### [critical|high|medium|low|info] path/to/file.py:LINE

Description of the issue.

**Suggestion**: How to fix it.

---
```

Severity definitions:
- **critical**: Security hole, data loss risk, silent corruption
- **high**: Logic error, broken feature, missing safety check
- **medium**: Dead code, missing wiring, inconsistency, hardcoded value that should be configurable
- **low**: Code quality, convention violation, missing docs
- **info**: TODO/deferred work, improvement opportunity

If zero findings, still create the file with `**Findings**: 0` and a brief note on what was checked.

### Agent Prompt Template

Every agent gets this structure (fill in the blanks per agent):

```
You are auditing the SynthOrg codebase for ONE specific concern: {FOCUS}.

## Architecture Context
{ARCHITECTURE_BRIEF}

## Existing Open Issues (do NOT duplicate these)
{ISSUE_LIST}

## Your Task
{DETAILED_INSTRUCTIONS}

## Output
Write ALL findings to: _audit/findings/{FILENAME}

Use this exact format for each finding:
### [severity] path/to/file:LINE
Description.
**Suggestion**: Fix.
---

Rules:
- Be thorough -- check EVERY relevant file in scope
- Only report REAL issues with file:line references
- If zero issues, still create the file and note what you checked
- Do NOT fix anything -- audit only
- Do NOT use Bash to write files -- use the Write tool
```

### Batch Execution

Launch agents in 6 batches of ~10 each. All agents within a batch run in parallel (`run_in_background: true`). Wait for each batch to complete before launching the next.

| Batch | Agent #s | Count |
|-------|----------|-------|
| A | 01-10 | 10 |
| B | 11-20 | 10 |
| C | 21-30 | 10 |
| D | 31-40 | 10 |
| E | 41-50 | 10 |
| F | 51-58 | 8 |

Report to user after each batch: "Batch X complete (N/58 agents done)."

---

## Agent Roster

### Wave 1: Observability & Logging (7 agents)

**Agent 01 -- missing-logger** (haiku)
File: `_audit/findings/01-missing-logger.md`
```
Search every .py file in src/synthorg/ for modules that contain business logic
but do NOT have `logger = get_logger(__name__)`.

Skip these (they legitimately don't need loggers):
- __init__.py files that only re-export
- Files containing ONLY: type aliases, enums, constants, Pydantic model definitions
- Files under observability/ (they ARE the logging system)

For each missing logger, report severity=low with the file path.
If a file has business logic (functions with if/try/for/while, service methods,
handlers) but no logger, that's a finding.
```

**Agent 02 -- wrong-logger-pattern** (haiku)
File: `_audit/findings/02-wrong-logger-pattern.md`
```
Search ALL .py files in src/synthorg/ and tests/ for forbidden logging patterns:

1. `import logging` (except in observability/setup.py, observability/sinks.py,
   observability/syslog_handler.py, observability/http_handler.py,
   observability/otlp_handler.py)
2. `logging.getLogger` (same exceptions)
3. `print(` in application code (except observability/ exceptions above and
   tests/). print() in test helpers is fine.
4. Logger variable named anything other than `logger` (e.g. `_logger`, `log`,
   `LOG`)

Severity: medium for app code, low for test code.
```

**Agent 03 -- missing-event-constants** (sonnet)
File: `_audit/findings/03-missing-event-constants.md`
```
The project requires all logger calls to use event constants from
src/synthorg/observability/events/ modules (e.g. API_REQUEST_STARTED from
events.api, TOOL_INVOKE_START from events.tool).

Search ALL logger.info/warning/error/debug/critical calls in src/synthorg/
(excluding observability/ itself). Flag calls where the first argument is:
- A string literal ("something happened")
- An f-string (f"processing {x}")
- A %-format string ("processing %s")

These should instead use a constant from observability/events/.

First, list all event constant modules in observability/events/ to understand
what's available. Then check every logger call.

Severity: low.
```

**Agent 04 -- unstructured-logging** (haiku)
File: `_audit/findings/04-unstructured-logging.md`
```
Search ALL logger calls in src/synthorg/ for unstructured formatting:

WRONG: logger.info("Processing user %s", user_id)
WRONG: logger.info(f"Processing user {user_id}")
WRONG: logger.info("Processing user " + user_id)
RIGHT: logger.info(EVENT_CONSTANT, user_id=user_id)

Flag any logger.info/warning/error/debug call that uses %s, %d, %f formatting,
f-strings, or string concatenation as arguments.

Severity: low.
```

**Agent 05 -- missing-error-logging** (sonnet)
File: `_audit/findings/05-missing-error-logging.md`
```
Project convention: "All error paths must log at WARNING or ERROR with context
before raising."

Search src/synthorg/ for `raise` statements that are NOT preceded (within the
same function, within ~10 lines above) by a logger.warning() or logger.error()
call.

Exceptions to skip:
- `raise` inside `__init__` for validation errors (Pydantic handles these)
- Re-raising with bare `raise` in except blocks (the original error was
  presumably already logged)
- `raise NotImplementedError` in abstract/protocol methods
- `raise StopIteration` / `raise StopAsyncIteration`

Severity: medium for service/engine code, low for model validation.
```

**Agent 06 -- missing-state-transition-log** (sonnet)
File: `_audit/findings/06-missing-state-transition-log.md`
```
Project convention: "All state transitions must log at INFO."

Focus on these domains where state machines matter:
- engine/ (agent state transitions: idle, running, paused, completed, failed)
- hr/ (hiring, onboarding, evaluation, promotion, offboarding)
- core/task.py + core/task_transitions.py (task status changes)
- engine/workflow/ (workflow execution state changes)
- workers/ (worker claim/dispatch state)
- security/autonomy/ (autonomy level changes)

For each domain, find where status/state fields are modified and check if
there's an INFO-level log call nearby. Missing transitions are severity=medium.
```

**Agent 07 -- observability-completeness** (sonnet)
File: `_audit/findings/07-observability-completeness.md`
```
Check whether key operations have full observability coverage:

1. Prometheus metrics (src/synthorg/observability/prometheus_collector.py):
   - Are all API endpoints instrumented? (request count, latency, error rate)
   - Are LLM provider calls tracked? (token usage, cost, latency per provider)
   - Are task/workflow state transitions counted?

2. OTLP traces (observability/otlp_handler.py):
   - Are spans created for LLM calls, tool invocations, task execution?

3. Audit chain (observability/audit_chain/):
   - Are security-sensitive operations (auth, permission changes, config
     changes) captured in the audit trail?

For each gap, describe what operation is missing coverage and suggest which
metric/trace/event to add. Severity: medium for missing metrics on key paths,
low for nice-to-have.
```

### Wave 2: Wiring & Integration (8 agents)

**Agent 08 -- unwired-api-controllers** (sonnet)
File: `_audit/findings/08-unwired-api-controllers.md`
```
Check api/controllers/ for controller classes not registered in auto_wire.py
or app.py. Also check for route handler methods that exist but are not mapped
to any HTTP route. Severity: high (unreachable code).
```

**Agent 09 -- unwired-web-stores** (sonnet)
File: `_audit/findings/09-unwired-web-stores.md`
```
Check every Zustand store file in web/src/stores/. For each store, grep the
entire web/src/ directory for imports of that store. If a store is imported by
zero pages or components, it's dead. Severity: medium.
```

**Agent 10 -- unwired-web-pages** (sonnet)
File: `_audit/findings/10-unwired-web-pages.md`
```
Check every page component in web/src/pages/. Cross-reference with
web/src/router/routes.ts. Pages not in the router are unreachable.
Severity: medium.
```

**Agent 11 -- unwired-settings** (sonnet)
File: `_audit/findings/11-unwired-settings.md`
```
Check settings/definitions/ for setting definitions. For each, check if it is:
(a) subscribed to via settings/subscribers/, AND
(b) exposed via an API endpoint in api/controllers/settings.py.
Settings defined but never consumed are dead config. Severity: medium.
```

**Agent 12 -- unwired-tools** (sonnet)
File: `_audit/findings/12-unwired-tools.md`
```
Check tool classes in tools/ subdirectories. For each tool class that extends
BaseTool, verify it is registered in tools/factory.py or tools/registry.py.
Unregistered tools are dead code. Severity: medium.
```

**Agent 13 -- unwired-protocols** (sonnet)
File: `_audit/findings/13-unwired-protocols.md`
```
Find all Protocol classes in src/synthorg/. For each, find concrete
implementations (classes that implement the protocol). Then check if those
implementations are registered in their factory. Report:
- Protocols with zero implementations (severity: medium)
- Implementations not registered in any factory (severity: medium)
```

**Agent 14 -- unwired-notifications** (sonnet)
File: `_audit/findings/14-unwired-notifications.md`
```
Check notifications/adapters/ for adapter classes. Verify each is registered
in notifications/factory.py. Also check if notification events are dispatched
from business logic. Report adapters with no factory registration and
notification types never dispatched. Severity: medium.
```

**Agent 15 -- frontend-backend-mismatch** (sonnet)
File: `_audit/findings/15-frontend-backend-mismatch.md`
```
Cross-reference web/src/api/ and web/src/services/ API calls with backend
api/controllers/ endpoints. Report:
- Frontend calls targeting endpoints that don't exist in backend (high)
- Backend endpoints with zero frontend consumers (low -- may be API-only)
```

### Wave 3: Dead Code & Unused (6 agents)

**Agent 16 -- unused-python-exports** (sonnet)
File: `_audit/findings/16-unused-python-exports.md`
```
Find public functions and classes in src/synthorg/ that are not imported by
any other module, not re-exported in __init__.py, and not referenced in tests/.
Focus on non-trivial code (skip dataclass fields, enum members). Severity: medium.
```

**Agent 17 -- unused-web-components** (sonnet)
File: `_audit/findings/17-unused-web-components.md`
```
Check every component file in web/src/components/ (excluding .stories.tsx).
Grep web/src/ for imports of each component. Components imported by zero
consumers are dead code. Severity: medium.
```

**Agent 18 -- unused-web-hooks** (haiku)
File: `_audit/findings/18-unused-web-hooks.md`
```
Check every hook file in web/src/hooks/. Grep web/src/ for imports of each
hook. Hooks imported by zero files are dead code. Severity: medium.
```

**Agent 19 -- unused-web-utils** (haiku)
File: `_audit/findings/19-unused-web-utils.md`
```
Check exported functions in web/src/utils/ and web/src/lib/. Grep web/src/
for imports. Unused exports are dead code. Severity: low.
```

**Agent 20 -- unused-dto-fields** (sonnet)
File: `_audit/findings/20-unused-dto-fields.md`
```
Compare DTO classes in api/dto*.py with frontend TypeScript types in
web/src/types/. Flag fields present in backend DTOs but absent from frontend
types (or vice versa). This suggests unused serialization. Severity: low.
```

**Agent 21 -- orphan-test-helpers** (sonnet)
File: `_audit/findings/21-orphan-test-helpers.md`
```
Check all conftest.py files in tests/ for fixtures and helper functions.
Grep tests/ for usage of each. Unused fixtures/helpers are dead test code.
Severity: low.
```

### Wave 4: TODOs & Deferred (4 agents)

**Agent 22 -- todo-comments** (haiku)
File: `_audit/findings/22-todo-comments.md`
```
Grep ALL source files (src/, tests/, web/src/, cli/) for TODO, FIXME, HACK,
XXX, TEMPORARY, WORKAROUND comments. List each with file:line and the full
comment text. Severity: info.
```

**Agent 23 -- not-implemented** (haiku)
File: `_audit/findings/23-not-implemented.md`
```
Grep src/synthorg/ and cli/ for: NotImplementedError, pass-only function
bodies (def/async def with only pass), and Ellipsis (...) as sole function
body. Severity: info for abstract methods, medium for concrete stubs.
```

**Agent 24 -- placeholder-stubs** (sonnet)
File: `_audit/findings/24-placeholder-stubs.md`
```
Find functions that return hardcoded dummy values, empty lists/dicts, or have
"placeholder", "stub", "temporary", "mock" in their comments/docstrings.
These suggest incomplete implementations. Severity: medium.
```

**Agent 25 -- deferred-features** (sonnet)
File: `_audit/findings/25-deferred-features.md`
```
Read docs/design/ pages and cross-reference with src/synthorg/. Find features
described in the design spec that have no corresponding implementation.
Focus on major features (not minor details). Severity: info.
```

### Wave 5: Safety & Security (7 agents)

**Agent 26 -- silent-exception-swallow** (sonnet)
File: `_audit/findings/26-silent-exception-swallow.md`
```
Find except blocks that swallow exceptions silently: bare `except:`,
`except Exception: pass`, `except Exception as e:` with only DEBUG logging
(should be WARNING+), catching too broadly. Skip intentional patterns like
graceful shutdown cleanup. Severity: high for business logic, medium for cleanup.
```

**Agent 27 -- input-validation-gaps** (sonnet)
File: `_audit/findings/27-input-validation-gaps.md`
```
Check API controller methods for user input that bypasses validation. Look for
path/query parameters used directly without Pydantic validation, raw request
body access, and missing type coercion. Severity: high.
```

**Agent 28 -- sql-injection-risk** (sonnet)
File: `_audit/findings/28-sql-injection-risk.md`
```
Search persistence/ and any file using SQL for string concatenation or f-strings
in SQL queries instead of parameterized queries. Severity: critical.
```

**Agent 29 -- missing-auth-checks** (sonnet)
File: `_audit/findings/29-missing-auth-checks.md`
```
Check API controllers for endpoints missing auth guards. Compare with auth
middleware/dependency injection. Public endpoints should be explicitly marked.
Severity: high for data-mutating endpoints, medium for read-only.
```

**Agent 30 -- unsafe-deserialization** (haiku)
File: `_audit/findings/30-unsafe-deserialization.md`
```
Grep for yaml.load() without SafeLoader, pickle.loads, eval(), exec(),
compile() with user input. Severity: critical.
```

**Agent 31 -- hardcoded-secrets** (haiku)
File: `_audit/findings/31-hardcoded-secrets.md`
```
Grep for patterns suggesting hardcoded secrets: password=", api_key=",
token=", secret=", followed by string literals. Skip test files and .env
examples. Severity: critical.
```

**Agent 32 -- missing-rate-limiting** (sonnet)
File: `_audit/findings/32-missing-rate-limiting.md`
```
Check public-facing API endpoints for rate limiting. Check expensive operations
(LLM calls, bulk DB writes, file uploads) for throttling. Severity: medium.
```

### Wave 6: Configuration & Hardcoding (6 agents)

**Agent 33 -- hardcoded-urls-ports** (haiku)
File: `_audit/findings/33-hardcoded-urls-ports.md`
```
Grep src/, web/src/, cli/ for hardcoded URLs, ports, hostnames, IP addresses
that should come from config or env vars. Skip test files and documentation.
Severity: medium.
```

**Agent 34 -- hardcoded-timeouts-limits** (haiku)
File: `_audit/findings/34-hardcoded-timeouts-limits.md`
```
Grep src/synthorg/ for hardcoded timeout values (seconds/ms), retry counts,
batch sizes, max limits that should be configurable. Look for bare numeric
literals in asyncio.wait_for, sleep, timeout parameters. Severity: low.
```

**Agent 35 -- hardcoded-magic-numbers** (haiku)
File: `_audit/findings/35-hardcoded-magic-numbers.md`
```
Find magic numbers in business logic: bare numeric literals (not 0, 1, -1)
without named constants. Focus on src/synthorg/ business logic, skip tests
and config defaults. Severity: low.
```

**Agent 36 -- vendor-name-leaks** (haiku)
File: `_audit/findings/36-vendor-name-leaks.md`
```
Grep for real vendor names: Anthropic, OpenAI, Claude, GPT, Gemini, Mistral
in project-owned code. ALLOWED exceptions (do NOT flag):
- providers/presets.py (user-facing runtime data)
- .claude/ directory files
- Third-party import paths (litellm.types.llms.openai etc)
- docs/design/operations.md provider list
Everything else is a violation. Severity: low.
```

**Agent 37 -- hardcoded-display-values** (sonnet)
File: `_audit/findings/37-hardcoded-display-values.md`
```
Find hardcoded currencies (should default EUR not USD), date formats, number
formats, locale-specific strings in both src/synthorg/ and web/src/.
Severity: medium for USD defaults, low for format strings.
```

**Agent 38 -- missing-settings-bridge** (sonnet)
File: `_audit/findings/38-missing-settings-bridge.md`
```
Cross-reference hardcoded values in src/synthorg/ with settings definitions in
settings/definitions/. Find values that SHOULD be configurable but are hardcoded,
and settings defined but never consumed by any code. Severity: medium.
```

### Wave 7: Code Quality & Conventions (7 agents)

**Agent 39 -- long-functions** (haiku)
File: `_audit/findings/39-long-functions.md`
```
Find functions exceeding line limits: Python over 50 lines, Go over 80 lines,
TypeScript over 60 lines. Report file:line of function def and line count.
Severity: low.
```

**Agent 40 -- long-files** (haiku)
File: `_audit/findings/40-long-files.md`
```
Find files exceeding size limits: Python over 800 lines, TypeScript over 600
lines, Go over 1000 lines. Report file path and line count. Severity: low.
```

**Agent 41 -- model-convention-violations** (sonnet)
File: `_audit/findings/41-model-convention-violations.md`
```
Check Pydantic models in src/synthorg/ for convention violations:
- Missing frozen=True in ConfigDict (config/identity models must be frozen)
- Missing allow_inf_nan=False in ConfigDict
- Identifier/name fields not using NotBlankStr type
- Mutable runtime fields mixed with config fields in one model
Severity: medium.
```

**Agent 42 -- missing-immutability** (sonnet)
File: `_audit/findings/42-missing-immutability.md`
```
Find violations of immutability conventions:
- dict/list exposed without MappingProxyType wrapping (non-Pydantic)
- Mutable default arguments (def f(x=[]))
- In-place mutations of frozen model instances
- Missing copy.deepcopy at system boundaries
Severity: medium.
```

**Agent 43 -- async-antipatterns** (sonnet)
File: `_audit/findings/43-async-antipatterns.md`
```
Find async antipatterns in src/synthorg/:
- Bare asyncio.create_task without TaskGroup
- Missing await on coroutine calls
- Blocking I/O (open(), requests.) in async functions
- Fire-and-forget tasks with no error handling
- sync sleep() in async context
Severity: high for missing await, medium for others.
```

**Agent 44 -- error-handling-consistency** (sonnet)
File: `_audit/findings/44-error-handling-consistency.md`
```
Check error handling conventions:
- Custom exceptions not inheriting from project error hierarchy
- API error responses not using RFC 9457 structured format
- Missing error mapping in controllers (raw exceptions leaking to clients)
- Inconsistent error response shapes across endpoints
Severity: medium.
```

**Agent 45 -- future-annotations-leak** (haiku)
File: `_audit/findings/45-future-annotations-leak.md`
```
Grep for "from __future__ import annotations" in ALL Python files. This is
forbidden on Python 3.14 (PEP 649 native). Severity: low.
```

### Wave 8: Frontend Quality (5 agents)

**Agent 46 -- missing-accessibility** (sonnet)
File: `_audit/findings/46-missing-accessibility.md`
```
Check web/src/components/ and web/src/pages/ for accessibility issues:
missing aria-label on interactive elements, missing role attributes, missing
keyboard navigation (onKeyDown handlers), missing focus management after
navigation, images without alt text. Severity: medium.
```

**Agent 47 -- missing-loading-states** (sonnet)
File: `_audit/findings/47-missing-loading-states.md`
```
Check pages/components that fetch data (useQuery, useEffect with fetch) for
missing loading skeletons/spinners, missing empty states when data is [],
and missing error boundaries around async content. Severity: medium.
```

**Agent 48 -- hardcoded-frontend-strings** (haiku)
File: `_audit/findings/48-hardcoded-frontend-strings.md`
```
Find user-facing strings hardcoded directly in TSX files. Look for text
content in JSX elements that should be centralized for i18n readiness.
Skip component prop names and technical strings. Severity: info.
```

**Agent 49 -- design-token-violations** (sonnet)
File: `_audit/findings/49-design-token-violations.md`
```
Check web/src/ for design system violations: hardcoded hex colors (#xxx),
hardcoded px values for spacing/padding/margins, raw font-family declarations,
raw CSS transition/animation values instead of @/lib/motion presets.
Severity: medium.
```

**Agent 50 -- missing-error-handling-fe** (sonnet)
File: `_audit/findings/50-missing-error-handling-fe.md`
```
Check web/src/ for API calls without error handling: missing .catch() or
try/catch, missing toast/notification on failure, optimistic updates without
rollback on error, console.error without user feedback. Severity: medium.
```

### Wave 9: Logic & Architecture (4 agents)

**Agent 51 -- race-conditions** (sonnet)
File: `_audit/findings/51-race-conditions.md`
```
Find potential race conditions: shared mutable state without locks/mutexes,
TOCTOU patterns (check-then-act without atomicity), concurrent dict/list
modification, DB read-modify-write without transactions. Severity: high.
```

**Agent 52 -- resource-leaks** (sonnet)
File: `_audit/findings/52-resource-leaks.md`
```
Find unclosed resources: HTTP clients/sessions not using async with,
file handles not in with blocks, DB connections not properly returned to pool,
aiohttp sessions created but not closed. Severity: high.
```

**Agent 53 -- circular-dependencies** (sonnet)
File: `_audit/findings/53-circular-dependencies.md`
```
Find import cycles between src/synthorg/ packages. Check for circular
references that could cause runtime ImportError or require deferred imports.
Also check for TYPE_CHECKING guards that hide real circular deps. Severity: medium.
```

**Agent 54 -- design-spec-drift** (sonnet)
File: `_audit/findings/54-design-spec-drift.md`
```
Compare implementation in src/synthorg/ with docs/design/ specs. Find
behaviors, models, or flows that diverge from what the spec describes without
documented rationale. Focus on major architectural decisions. Severity: medium.
```

### Wave 10: Go CLI (4 agents)

**Agent 55 -- go-error-handling** (sonnet)
File: `_audit/findings/55-go-error-handling.md`
```
Check cli/ Go code for: ignored error returns (assigned to _), missing error
wrapping (fmt.Errorf with %w), bare log.Fatal instead of returning errors,
os.Exit in non-main functions. Severity: medium.
```

**Agent 56 -- go-resource-leaks** (sonnet)
File: `_audit/findings/56-go-resource-leaks.md`
```
Check cli/ for unclosed resources: Docker clients without defer Close(),
HTTP response bodies not closed, file handles without defer Close(),
context cancellation not propagated. Severity: high.
```

**Agent 57 -- go-hardcoded-values** (haiku)
File: `_audit/findings/57-go-hardcoded-values.md`
```
Grep cli/ for hardcoded Docker image tags, ports, paths, timeouts that should
be configurable via flags or config. Severity: low.
```

**Agent 58 -- go-cli-wiring** (sonnet)
File: `_audit/findings/58-go-cli-wiring.md`
```
Check cobra command registration in cli/cmd/. Find commands registered but
non-functional, flags defined but never read, subcommands with no RunE.
Severity: medium.
```

---

## Phase 3: Validate Findings (sonnet agents)

**MANDATORY. Never skip this phase.**

After all 58 audit agents complete, launch validation agents to verify findings.

### Process

1. Read all 58 finding files from `_audit/findings/`
2. Collect all critical + high severity findings into a validation queue
3. Split the queue into batches of ~12 findings each
4. Launch one **sonnet** validation agent per batch (in parallel, `run_in_background: true`)

### Validation Agent Prompt

```
You are validating audit findings by reading the ACTUAL SOURCE CODE.

For each finding below, do:
1. Read the file at the reported line number
2. Quote the actual code (2-5 lines)
3. Check if the issue is real or a false positive
4. Check if it's intentional (read surrounding comments, docstrings)
5. Give a verdict: CONFIRMED, FALSE_POSITIVE, or INTENTIONAL

Write results to: _audit/findings/validate-batch-{N}.md

Format per finding:
### [original-file]:[line] -- [CONFIRMED|FALSE_POSITIVE|INTENTIONAL]
**Original**: [description from audit agent]
**Actual code**: [quoted code]
**Verdict**: [explanation]
---

Findings to validate:
{BATCH_OF_FINDINGS}
```

### After Validation

1. Read all `validate-batch-*.md` files
2. Remove FALSE_POSITIVE findings from the audit files (edit in place)
3. Mark INTENTIONAL findings as excluded (keep in file but prefix with `[INTENTIONAL]`)
4. Report: "Validated N findings. Removed M false positives (X%)."

Skip validation for `--quick` runs or if total critical+high findings are under 5.

---

## Phase 4: Build INDEX.md

After validation, read all finding files and build `_audit/INDEX.md`:

```markdown
# Codebase Audit Index

**Date**: {date}
**Scope**: {scope}
**Agents**: 58
**Total findings**: {count}
**False positives removed**: {count} ({percent}%)

## By Severity

| Severity | Count |
|----------|-------|
| critical | N |
| high | N |
| medium | N |
| low | N |
| info | N |

## By Wave

| Wave | Findings | Top Issue |
|------|----------|-----------|
| 1. Observability | N | ... |
| 2. Wiring | N | ... |
| ... | ... | ... |

## Top 20 Critical + High Findings

| # | Severity | File:Line | Issue | Agent |
|---|----------|-----------|-------|-------|
| 1 | critical | ... | ... | ... |
| ... | ... | ... | ... | ... |

## Zero-Finding Categories

These agents found nothing (may warrant deeper investigation):
- ...

## Finding Files

- [01-missing-logger.md](findings/01-missing-logger.md) (N findings)
- [02-wrong-logger-pattern.md](findings/02-wrong-logger-pattern.md) (N findings)
- ...
```

---

## Phase 5: Triage with User

Present INDEX.md to the user. Walk through:

1. Critical + high findings first
2. Zero-finding categories (suspicious?)
3. Group related findings into potential GitHub issues by code proximity

Use AskUserQuestion to confirm:
- Which findings to create issues for
- How to group them (by module? by wave? by severity?)
- Whether to create issues now or export report only

If `--report-only`, skip this phase entirely.

---

## Rules

1. **Every agent writes to `_audit/findings/`** using the Write tool, not Bash
2. **Architecture brief in every prompt** -- no blind agents
3. **Validation is mandatory** for critical+high findings
4. **Batch execution** -- ~10 agents per batch, wait between batches
5. **Sonnet for analysis, Haiku for pattern matching** -- never Opus for audit agents
6. **Do NOT fix anything** -- audit only, findings only
7. **Rerunnable** -- clean `_audit/` at start of every run
8. **Never use em-dashes** in any output files (project convention)
9. **Report progress** after each batch completes
