---
description: "Full codebase audit: launches 123 specialized agents to find issues across Python/React/Go/docs/website, writes findings to _audit/findings/, then triages with user"
argument-hint: "<scope: full | src/ | web/ | cli/ | docs/> [--report-only] [--quick]"
allowed-tools: ["Agent", "Bash", "Read", "Write", "Edit", "Glob", "Grep", "AskUserQuestion", "mcp__github__issue_write", "mcp__github__issue_read", "mcp__github__list_issues", "mcp__github__search_issues"]
---

# /codebase-audit -- Full Codebase Audit

Launch 123 specialized agents to audit the entire codebase (or a targeted scope), write findings to `_audit/findings/`, build an index, and triage with the user.

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

| Argument | Directories | Agents |
|----------|-------------|-------------|
| `full` (default) | All | 01-123 |
| `src/` | `src/synthorg/`, `tests/`, `web/src/types/`, `docs/design/` | 01-06, 09-15, 16-34, 39-42, 48-51, 55, 58-80, 87-100, 102-108, 110-123 |
| `web/` | `web/src/`, `src/synthorg/api/controllers/` | 07-08, 13, 17, 35-38, 45-47, 52-54, 57-59, 97, 100-101, 107-109, 111-112, 120-121, 123 |
| `cli/` | `cli/` | 17, 18, 43-44, 56, 67, 78, 89, 107-108, 115-119, 122-123 |
| `docs/` | `docs/`, `site/`, `src/synthorg/` | 17, 20, 42, 48-51, 73-86, 103-104, 107-108, 123 |

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

Produce an **Architecture Brief** (~400 words) covering:
- Logging: `get_logger(__name__)`, structlog, event constants in `observability/events/`, structured kwargs
- Wiring: `auto_wire.py` phases, controller registration, factory pattern
- Frontend: router structure, Zustand stores, API layer
- Conventions: immutability, frozen Pydantic, `NotBlankStr`, vendor-agnostic naming
- Error hierarchy: custom exceptions inherit from project base, RFC 9457 responses
- Providers: all LLM calls through `BaseCompletionProvider` (auto-retry, rate limit)
- Pluggable subsystems: Protocol + concrete implementations + factory + config discriminator
- Database: SQLite + Postgres dual-backend, Atlas migrations in `persistence/*/revisions/`
- Async: `asyncio.TaskGroup` preferred, never bare `create_task`
- Testing: markers, xdist, async auto mode, Hypothesis profiles

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

```text
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

Launch agents in 13 batches of ~10 each. All agents within a batch run in parallel (`run_in_background: true`). Wait for each batch to complete before launching the next.

| Batch | Agents |
|-------|----------|
| A | 01-10 |
| B | 11-20 |
| C | 21-30 |
| D | 31-40 |
| E | 41-50 |
| F | 51-60 |
| G | 61-70 |
| H | 71-80 |
| I | 81-90 |
| J | 91-100 |
| K | 101-110 |
| L | 111-120 |
| M | 121-123 |

Report to user after each batch: "Batch X complete (N/{AGENTS_LAUNCHED} agents done)." where `{AGENTS_LAUNCHED}` is the total number of agents launched for the current scope (123 for `full`, fewer for scoped runs).

---

## Agent Roster

### Wave 1: Observability & Logging (5 agents)

**Agent 01 -- missing-logger** (haiku)
File: `_audit/findings/01-missing-logger.md`

```text
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

**Agent 02 -- missing-event-constants** (sonnet)
File: `_audit/findings/02-missing-event-constants.md`

```text
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

**Agent 03 -- missing-error-logging** (sonnet)
File: `_audit/findings/03-missing-error-logging.md`

```text
Project convention: "All error paths must log at WARNING or ERROR with context
before raising."

Search src/synthorg/ for `raise` statements that are NOT preceded by a
logger.warning() or logger.error() call anywhere in the same function before
the raise. If a function has multiple raises, each must have its own preceding
log call or be inside an except block that already logged.

Exceptions to skip:
- `raise` inside `__init__` for validation errors (Pydantic handles these)
- Re-raising with bare `raise` in except blocks (the original error was
  presumably already logged)
- `raise NotImplementedError` in abstract/protocol methods
- `raise StopIteration` / `raise StopAsyncIteration`

Severity: medium for service/engine code, low for model validation.

```

**Agent 04 -- missing-state-transition-log** (sonnet)
File: `_audit/findings/04-missing-state-transition-log.md`

```text
Project convention: "All state transitions must log at INFO."

Focus on these domains where state machines matter:
- engine/ (agent state transitions: idle, running, paused, completed, failed)
- hr/ (hiring, onboarding, evaluation, promotion, offboarding)
- core/task.py + core/task_transitions.py (task status changes)
- engine/workflow/ (workflow execution state changes)
- workers/ (worker claim/dispatch state)
- security/autonomy/ (autonomy level changes)
- api/ (request lifecycle, startup/shutdown phases)
- notifications/ (delivery state changes)
- persistence/ (connection state, transaction state)
- backup/ (backup job state)
If you find state machines in other modules, include them too.

For each domain, find where status/state fields are modified and check if
there's an INFO-level log call nearby. Missing transitions are severity=medium.

```

**Agent 05 -- observability-completeness** (sonnet)
File: `_audit/findings/05-observability-completeness.md`

```text
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

**Agent 06 -- unwired-api-controllers** (sonnet)
File: `_audit/findings/06-unwired-api-controllers.md`

```text
Check api/controllers/ for controller classes not registered in auto_wire.py
or app.py. Also check for route handler methods that exist but are not mapped
to any HTTP route. Do NOT check frontend-to-backend connectivity (Agent 13
owns that). Severity: high (unreachable code).

```

**Agent 07 -- unwired-web-stores** (sonnet)
File: `_audit/findings/07-unwired-web-stores.md`

```text
Check every Zustand store file in web/src/stores/. For each store, grep the
entire web/src/ directory for imports of that store. If a store is imported by
zero pages or components, it's dead. Severity: medium.

```

**Agent 08 -- unwired-web-pages** (sonnet)
File: `_audit/findings/08-unwired-web-pages.md`

```text
Find all .tsx files in web/src/pages/ that are NOT imported by any other file
(not by routes.ts, not by another page as a nested layout). Pages with no
route AND no parent import are unreachable. Severity: medium.

```

**Agent 09 -- unwired-settings** (sonnet)
File: `_audit/findings/09-unwired-settings.md`

```text
Check settings/definitions/ for setting definitions. For each, check if it is:
(a) subscribed to via settings/subscribers/, AND
(b) exposed via an API endpoint in api/controllers/settings.py.
Settings defined but never consumed are dead config. Severity: medium.

```

**Agent 10 -- unwired-tools** (sonnet)
File: `_audit/findings/10-unwired-tools.md`

```text
Check tool classes in tools/ subdirectories. For each tool class that extends
BaseTool, verify it is registered in tools/factory.py or tools/registry.py.
Unregistered tools are dead code. Severity: medium.

```

**Agent 11 -- unwired-protocols** (sonnet)
File: `_audit/findings/11-unwired-protocols.md`

```text
Find all Protocol classes in src/synthorg/. For each, find concrete
implementations (classes that implement the protocol). Then check if those
implementations are registered in their factory. Report:
- Protocols with zero implementations (severity: medium)
- Implementations not registered in any factory (severity: medium)

```

**Agent 12 -- unwired-notifications** (sonnet)
File: `_audit/findings/12-unwired-notifications.md`

```text
Check notifications/adapters/ for adapter classes. Verify each is registered
in notifications/factory.py. Also check if notification events are dispatched
from business logic. Report adapters with no factory registration and
notification types never dispatched. Severity: medium.

```

**Agent 13 -- frontend-backend-mismatch** (sonnet)
File: `_audit/findings/13-frontend-backend-mismatch.md`

```text
Cross-reference web/src/api/ and web/src/services/ API calls with backend
api/controllers/ endpoints. Report:
- Frontend calls targeting endpoints that don't exist in backend (high)
- Backend endpoints with zero frontend consumers (low -- may be API-only)

```

### Wave 3: Dead Code & Unused (3 agents)

**Agent 14 -- unused-python-exports** (sonnet)
File: `_audit/findings/14-unused-python-exports.md`

```text
Find public functions and classes in src/synthorg/ that are not imported by
any other module, not re-exported in __init__.py, and not referenced in tests/.
Exclude: __init__ methods, property descriptors, __repr__/__str__, metaclass
methods, enum members, Pydantic field definitions. Severity: medium.

```

**Agent 15 -- unused-dto-fields** (sonnet)
File: `_audit/findings/15-unused-dto-fields.md`

```text
Compare DTO classes in api/dto*.py with frontend TypeScript types in
web/src/types/. Flag fields present in backend DTOs but absent from frontend
types (or vice versa). This suggests unused serialization. Severity: low.
Runs for `full`, `src/`, or `web/` scope (requires both backend and frontend).

```

**Agent 16 -- orphan-test-helpers** (sonnet)
File: `_audit/findings/16-orphan-test-helpers.md`

```text
Check all conftest.py files in tests/ for fixtures and helper functions.
Grep tests/ for usage of each. Unused fixtures/helpers are dead test code.
Severity: low.

```

### Wave 4: TODOs & Deferred (4 agents)

**Agent 17 -- todo-comments** (haiku)
File: `_audit/findings/17-todo-comments.md`

```text
Grep source files in the provided scope for TODO, FIXME, HACK,
XXX, TEMPORARY, WORKAROUND comments. List each with file:line and the full
comment text. Severity: info.

```

**Agent 18 -- not-implemented** (haiku)
File: `_audit/findings/18-not-implemented.md`

```text
Grep src/synthorg/ and cli/ for: NotImplementedError, pass-only function
bodies (def/async def with only pass), and Ellipsis (...) as sole function
body. Severity: info for abstract methods, medium for concrete stubs.

```

**Agent 19 -- placeholder-stubs** (sonnet)
File: `_audit/findings/19-placeholder-stubs.md`

```text
Find functions that return hardcoded dummy values, empty lists/dicts, or have
"placeholder", "stub", "temporary", "mock" in their comments/docstrings.
These suggest incomplete implementations. Severity: medium.

```

**Agent 20 -- deferred-features** (sonnet)
File: `_audit/findings/20-deferred-features.md`

```text
Read docs/design/ pages and cross-reference with src/synthorg/. Find features
described in the design spec that have no corresponding implementation.
Focus on major features (not minor details). Severity: info.

```

### Wave 5: Safety & Security (6 agents)

**Agent 21 -- silent-exception-swallow** (sonnet)
File: `_audit/findings/21-silent-exception-swallow.md`

```text
Find except blocks that swallow exceptions silently: bare `except:`,
`except Exception: pass`, `except Exception as e:` with only DEBUG logging
(should be WARNING+), catching too broadly. Skip intentional patterns like
graceful shutdown cleanup. Severity: high for business logic, medium for cleanup.

```

**Agent 22 -- input-validation-gaps** (sonnet)
File: `_audit/findings/22-input-validation-gaps.md`

```text
Check API controller methods for user input that bypasses validation. Look for
path/query parameters used directly without Pydantic validation, raw request
body access, and missing type coercion. Severity: high.

```

**Agent 23 -- sql-injection-risk** (sonnet)
File: `_audit/findings/23-sql-injection-risk.md`

```text
Search persistence/ and any file using SQL for string concatenation or f-strings
in SQL queries instead of parameterized queries. Severity: critical.

```

**Agent 24 -- missing-auth-checks** (sonnet)
File: `_audit/findings/24-missing-auth-checks.md`

```text
Check API controllers for endpoints missing auth guards. Compare with auth
middleware/dependency injection. Public endpoints should be explicitly marked.
Severity: high for data-mutating endpoints, medium for read-only.

```

**Agent 25 -- unsafe-deserialization** (haiku)
File: `_audit/findings/25-unsafe-deserialization.md`

```text
Flag ANY use of yaml.load (even with Loader parameter -- verify SafeLoader),
pickle.loads, eval(), exec(). Flag compile() ONLY if the argument contains a
variable or function parameter (not a string literal). Severity: critical.

```

**Agent 26 -- missing-rate-limiting** (sonnet)
File: `_audit/findings/26-missing-rate-limiting.md`

```text
Check public-facing API endpoints for rate limiting. Check expensive operations
(LLM calls, bulk DB writes, file uploads) for throttling. Severity: medium.

```

### Wave 6: Configuration & Hardcoding (4 agents)

**Agent 27 -- hardcoded-urls-ports** (haiku)
File: `_audit/findings/27-hardcoded-urls-ports.md`

```text
Grep files in the provided scope for hardcoded URLs, ports, hostnames, IP
addresses that should come from config or env vars. Skip test files and
documentation. Severity: medium.

```

**Agent 28 -- hardcoded-timeouts-limits** (haiku)
File: `_audit/findings/28-hardcoded-timeouts-limits.md`

```text
Grep src/synthorg/ for hardcoded timeout values (seconds/ms), retry counts,
batch sizes, max limits that should be configurable. Look for bare numeric
literals in asyncio.wait_for, sleep, timeout parameters. Severity: low.
```

**Agent 29 -- hardcoded-magic-numbers** (haiku)
File: `_audit/findings/29-hardcoded-magic-numbers.md`

```text
Find magic numbers in business logic: bare numeric literals (not 0, 1, -1)
without named constants. Focus on src/synthorg/ business logic, skip tests
and config defaults. Severity: low.

```

**Agent 30 -- missing-settings-bridge** (sonnet)
File: `_audit/findings/30-missing-settings-bridge.md`

```text
Cross-reference hardcoded values in src/synthorg/ with settings definitions in
settings/definitions/. Find values that SHOULD be configurable but are hardcoded,
and settings defined but never consumed by any code. Severity: medium.

```

### Wave 7: Code Quality & Conventions (4 agents)

**Agent 31 -- model-convention-violations** (sonnet)
File: `_audit/findings/31-model-convention-violations.md`

```text
Check Pydantic models in src/synthorg/ for convention violations:
- Missing frozen=True in ConfigDict (config/identity models must be frozen)
- Missing allow_inf_nan=False in ConfigDict
- Identifier/name fields not using NotBlankStr type
- Mutable runtime fields mixed with config fields in one model
Severity: medium.

```

**Agent 32 -- missing-immutability** (sonnet)
File: `_audit/findings/32-missing-immutability.md`

```text
Find violations of immutability conventions:
- dict/list exposed without MappingProxyType wrapping (non-Pydantic)
- Mutable default arguments (def f(x=[]))
- In-place mutations of frozen model instances
- Missing copy.deepcopy at system boundaries
Severity: medium.

```

**Agent 33 -- async-antipatterns** (sonnet)
File: `_audit/findings/33-async-antipatterns.md`

```text
Find async antipatterns in src/synthorg/:
- Bare asyncio.create_task without TaskGroup
- Missing await on coroutine calls
- Blocking I/O (open(), requests.) in async functions
- Fire-and-forget tasks with no error handling
- sync sleep() in async context
Severity: high for missing await, medium for others.

```

**Agent 34 -- error-handling-consistency** (sonnet)
File: `_audit/findings/34-error-handling-consistency.md`

```text
Check error handling conventions:
- Custom exceptions not inheriting from project error hierarchy
- API error responses not using RFC 9457 structured format
- Missing error mapping in controllers (raw exceptions leaking to clients)
- Inconsistent error response shapes across endpoints
Severity: medium.

```

### Wave 8: Frontend Quality (4 agents)

**Agent 35 -- missing-accessibility** (sonnet)
File: `_audit/findings/35-missing-accessibility.md`

```text
Check web/src/components/ and web/src/pages/ for accessibility issues:
missing aria-label on interactive elements, missing role attributes, missing
keyboard navigation (onKeyDown handlers), missing focus management after
navigation, images without alt text. Severity: medium.

```

**Agent 36 -- missing-loading-states** (sonnet)
File: `_audit/findings/36-missing-loading-states.md`

```text
Check pages/components that fetch data (useQuery, useEffect with fetch) for
missing loading skeletons/spinners, missing empty states when data is [],
and missing error boundaries around async content. Severity: medium.

```

**Agent 37 -- hardcoded-frontend-strings** (haiku)
File: `_audit/findings/37-hardcoded-frontend-strings.md`

```text
Find user-facing strings hardcoded directly in TSX files. Look for text
content in JSX elements that should be centralized for i18n readiness.
Skip component prop names and technical strings. Severity: info.

```

**Agent 38 -- missing-error-handling-fe** (sonnet)
File: `_audit/findings/38-missing-error-handling-fe.md`

```text
Check web/src/ for API calls without error handling: missing .catch() or
try/catch, missing toast/notification on failure, optimistic updates without
rollback on error, console.error without user feedback. Severity: medium.

```

### Wave 9: Logic & Architecture (4 agents)

**Agent 39 -- race-conditions** (sonnet)
File: `_audit/findings/39-race-conditions.md`

```text
Find potential race conditions: shared mutable state without locks/mutexes,
TOCTOU patterns (check-then-act without atomicity), concurrent dict/list
modification, DB read-modify-write without transactions. Severity: high.

```

**Agent 40 -- resource-leaks** (sonnet)
File: `_audit/findings/40-resource-leaks.md`

```text
Find unclosed resources: HTTP clients/sessions not using async with,
file handles not in with blocks, DB connections not properly returned to pool,
aiohttp sessions created but not closed. Severity: high.

```

**Agent 41 -- circular-dependencies** (sonnet)
File: `_audit/findings/41-circular-dependencies.md`

```text
Find import cycles between src/synthorg/ packages. Check for circular
references that could cause runtime ImportError or require deferred imports.
Also check for TYPE_CHECKING guards that hide real circular deps. Severity: medium.

```

**Agent 42 -- design-spec-drift** (sonnet)
File: `_audit/findings/42-design-spec-drift.md`

```text
Compare implementation in src/synthorg/ with docs/design/ specs. Find
behaviors, models, or flows that diverge from what the spec describes without
documented rationale. Focus on major architectural decisions. Severity: medium.

```

### Wave 10: Go CLI (2 agents)

**Agent 43 -- go-hardcoded-values** (haiku)
File: `_audit/findings/43-go-hardcoded-values.md`

```text
Grep cli/ for hardcoded Docker image tags, ports, paths, timeouts that should
be configurable via flags or config. Severity: low.

```

**Agent 44 -- go-cli-wiring** (sonnet)
File: `_audit/findings/44-go-cli-wiring.md`

```text
Check cobra command registration in cli/cmd/. Find commands registered but
non-functional, flags defined but never read, subcommands with no RunE.
Severity: medium.

```

### Wave 11: Dashboard Completeness (3 agents)

**Agent 45 -- dashboard-api-coverage** (sonnet)
File: `_audit/findings/45-dashboard-api-coverage.md`

```text
Cross-reference every backend API endpoint (from all controllers in
api/controllers/) with the web dashboard. For each endpoint, check whether
the dashboard exposes the functionality to the user in SOME way -- a page,
a button, a settings panel, a dialog, etc. Report endpoints that exist in
the backend but have no corresponding UI surface. Severity: medium.

```

**Agent 46 -- dashboard-settings-completeness** (sonnet)
File: `_audit/findings/46-dashboard-settings-completeness.md`

```text
Cross-reference every setting definition in src/synthorg/settings/definitions/ with the
Settings page in the dashboard (web/src/pages/settings/). For each setting,
check whether it is editable/visible in the UI. Also check ConfigDict fields
in src/synthorg/config/ that are user-facing but have no settings UI.
Report settings that exist but are not exposed. Severity: medium.

```

**Agent 47 -- dashboard-ux-improvements** (sonnet)
File: `_audit/findings/47-dashboard-ux-improvements.md`

```text
Review the web dashboard pages for UX improvement opportunities. Look for:
- Pages with no sorting/filtering when data lists can grow large
- Missing pagination on list views
- Missing search/filter on pages with many items
- Missing breadcrumb navigation on detail pages
- Missing confirmation dialogs on destructive actions
- Missing keyboard shortcuts for common actions
- Missing bulk selection/actions on list views
- Inconsistent page layouts (some pages have sidebars, some don't)
- Missing contextual help or tooltips on complex features
- Missing progress indicators on long-running operations
Focus on the most impactful improvements. Severity: medium for missing
core UX patterns, low for polish.
```

### Wave 12: Documentation Quality (4 agents)

**Agent 48 -- docs-accuracy** (sonnet)
File: `_audit/findings/48-docs-accuracy.md`

```text
Check docs/ pages for factual accuracy. Read key documentation pages
(architecture, tech-stack, decisions, design pages) and verify claims
against actual code. Look for:
- Outdated technology versions or library references
- Features described as "implemented" that are actually stubs
- Code examples that don't match actual API signatures
- Removed features still documented
- Incorrect file paths or module references
Severity: medium for misleading docs, low for minor inaccuracies.

```

**Agent 49 -- docs-completeness** (sonnet)
File: `_audit/findings/49-docs-completeness.md`

```text
Check for documentation gaps. Look for:
- Major features with no documentation page
- API endpoints with no usage examples in docs
- Configuration options with no documentation
- Architecture decisions made but not recorded in decisions.md
- Missing "getting started" or onboarding content
- Design pages referenced in DESIGN_SPEC.md that don't exist
Cross-reference docs/design/ index with actual pages.
Severity: medium for missing feature docs, low for missing examples.

```

**Agent 50 -- readme-website-accuracy** (sonnet)
File: `_audit/findings/50-readme-website-accuracy.md`

```text
Check README.md and any public-facing content (landing page content in
docs/, comparison page, etc.) for:
- Outdated version numbers or release dates
- Feature claims that don't match current implementation status
- Broken badges or status indicators
- Competitor comparisons with outdated information
- Missing or incorrect installation instructions
- Outdated screenshots or diagrams
Severity: medium for public-facing inaccuracies.

```

**Agent 51 -- docs-diagram-quality** (sonnet)
File: `_audit/findings/51-docs-diagram-quality.md`

```text
Check all D2 and Mermaid diagrams in docs/ for:
- Diagrams that reference modules/classes that no longer exist
- Diagrams that are missing recently added major components
- Inconsistent naming between diagram labels and actual code names
- Diagrams using ASCII/Unicode box-drawing (forbidden by convention)
- Missing diagrams for complex subsystems that would benefit from visuals
Cross-reference diagram content with actual source structure.
Severity: low.

```

### Wave 13: UX & Content Quality (8 agents)

**Agent 52 -- ux-consistency** (sonnet)
File: `_audit/findings/52-ux-consistency.md`

```text
Check dashboard pages for visual and interaction consistency:
- Pages using different card layouts for similar data
- Inconsistent button placement (some pages put actions top-right,
  others bottom)
- Inconsistent status indicator styles across pages
- Pages with different table/list component choices for similar data
- Inconsistent empty state messaging tone/style
- Inconsistent date/time display formats across pages
Severity: medium for jarring inconsistencies, low for minor.

```

**Agent 53 -- ux-responsiveness** (sonnet)
File: `_audit/findings/53-ux-responsiveness.md`

```text
Check dashboard for responsive design issues. The dashboard shows a
MobileUnsupportedOverlay below the 768px breakpoint, but check for:
- Content overflow or horizontal scrolling on narrow screens (768-1024px)
- Tables that don't adapt (no horizontal scroll wrapper)
- Fixed-width layouts that don't flex
- Charts/graphs that don't resize properly
- Modals/drawers that overflow on smaller screens
Severity: medium.

```

**Agent 54 -- ux-performance-patterns** (sonnet)
File: `_audit/findings/54-ux-performance-patterns.md`

```text
Check dashboard for performance antipatterns:
- Large component re-renders (components that subscribe to entire store
  instead of selectors)
- Missing React.memo on list item components
- Missing useMemo/useCallback on expensive computations passed as props
- Unnecessary re-fetching (polling without stale-time checks)
- Large bundle imports that should be lazy-loaded
- Images without width/height (causing layout shift)
Severity: medium.

```

**Agent 55 -- api-docs-openapi** (sonnet)
File: `_audit/findings/55-api-docs-openapi.md`

```text
Check the OpenAPI/Scalar API documentation for completeness:
- Endpoints missing descriptions or summaries
- Request/response schemas missing field descriptions
- Missing example values in schemas
- Endpoints with undocumented error responses
- Missing authentication requirements in endpoint docs
Check by reading controller decorators and Pydantic model docstrings.
Severity: low.

```

**Agent 56 -- cli-docs-help** (haiku)
File: `_audit/findings/56-cli-docs-help.md`

```text
Check Go CLI commands for documentation completeness:
- Commands missing Long descriptions
- Flags missing usage text
- Missing examples in command help
- Inconsistent flag naming conventions
- Commands without --help output verification
Check cli/cmd/*.go for cobra.Command fields. Severity: low.

```

**Agent 57 -- storybook-coverage** (sonnet)
File: `_audit/findings/57-storybook-coverage.md`

```text
Check web/src/components/ui/ for Storybook story coverage. Every shared
component should have a .stories.tsx file. For existing stories, check:
- Missing story variants (default, loading, error, empty states)
- Stories that don't cover all major props/variants
- Components in ui/ without any story file
Severity: low for missing stories, medium for shared components with
zero coverage.

```

**Agent 58 -- error-messages-ux** (sonnet)
File: `_audit/findings/58-error-messages-ux.md`

```text
Check error messages shown to users (toast notifications, error states,
API error responses, form validation messages) for quality:
- Generic "Something went wrong" without actionable guidance
- Technical jargon exposed to end users (stack traces, error codes
  without explanation)
- Missing retry suggestions on transient errors
- Inconsistent error message tone across the app
- Error messages that don't tell the user what to do next
Check both frontend toast calls and backend API error messages.
Severity: medium for unhelpful errors, low for tone inconsistencies.

```

**Agent 59 -- onboarding-flow** (sonnet)
File: `_audit/findings/59-onboarding-flow.md`

```text
Check the setup wizard and first-run experience:
- Setup steps that can fail silently
- Missing validation on setup inputs
- Unclear or missing help text during setup
- Missing progress indicators during setup operations
- Post-setup state that leaves features half-configured
- Missing guidance on what to do after setup completes
Check web/src/pages/setup/ and src/synthorg/api/controllers/setup.py.
Severity: medium.

```

### Wave 14: Abstraction Boundaries & Backend Parity (13 agents)

**Agent 60 -- dual-backend-protocol-parity** (sonnet)
File: `_audit/findings/60-dual-backend-protocol-parity.md`

```text
Every repository Protocol in src/synthorg/persistence/*_protocol.py must have
concrete implementations in BOTH src/synthorg/persistence/sqlite/ AND
src/synthorg/persistence/postgres/. For each Protocol, verify both impls exist
and implement every method with matching signatures.

Flag:
- Protocols with SQLite-only or Postgres-only impls
- Methods present on one backend but not the other
- Signature drift (parameter names, types, return types diverging)

Severity: high for missing impl, medium for signature drift.

```

**Agent 61 -- migration-parity** (sonnet)
File: `_audit/findings/61-migration-parity.md`

```text
Migrations in src/synthorg/persistence/sqlite/revisions/ and
src/synthorg/persistence/postgres/revisions/ must stay in semantic parity.

For each recent migration, verify the same schema change exists in the other
backend. Compare schema.sql files in both backends for table/column drift.

Flag:
- Migrations added to one backend only
- Tables/columns in one schema but not the other
- Column type mismatches (TEXT vs VARCHAR, INTEGER vs BIGINT) implying drift

Severity: high.

```

**Agent 62 -- dual-backend-test-parity** (sonnet)
File: `_audit/findings/62-dual-backend-test-parity.md`

```text
Every repository implementation in src/synthorg/persistence/sqlite/ and
src/synthorg/persistence/postgres/ must have test coverage on BOTH backends
(parametrized fixtures or mirrored test files).

Flag:
- Repo impls with tests on only one backend
- Integration suites that don't run against both backends
- Conftest fixtures defaulting to one backend with no parametrized counterpart

Severity: medium.

```

**Agent 63 -- persistence-boundary-deep** (sonnet)
File: `_audit/findings/63-persistence-boundary-deep.md`

```text
scripts/check_persistence_boundary.py (PreToolUse hook) catches import-level
leaks. This agent does deeper analysis.

Outside src/synthorg/persistence/ and the allowlisted exceptions in the hook's
_ALLOWLIST, find:
- Raw SQL DDL/DML in multi-line strings (CREATE TABLE, INSERT INTO, UPDATE,
  DELETE, ALTER, DROP)
- f-string or template-rendered SQL
- Dynamic query builders
- ORM session or transaction boundary management

Severity: high.

```

**Agent 64 -- provider-boundary-leaks** (sonnet)
File: `_audit/findings/64-provider-boundary-leaks.md`

```text
All LLM calls must go through BaseCompletionProvider in src/synthorg/providers/.

Outside src/synthorg/providers/, find:
- Direct litellm.completion / litellm.acompletion calls
- Raw openai / anthropic / mistralai / google.generativeai SDK imports or instantiation
- HTTP calls to /v1/chat/completions or similar provider endpoints
- Anything bypassing the retry + rate-limit + fallback infrastructure

Severity: high.
```

**Agent 65 -- memory-boundary-leaks** (sonnet)
File: `_audit/findings/65-memory-boundary-leaks.md`

```text
All memory/recall operations must go through src/synthorg/memory/.

Outside src/synthorg/memory/, find:
- Direct mem0 SDK calls
- qdrant_client imports or usage
- Raw vector store client instantiation
- Embedding API calls bypassing the memory abstraction

Severity: medium.

```

**Agent 66 -- queue-boundary-leaks** (sonnet)
File: `_audit/findings/66-queue-boundary-leaks.md`

```text
Inter-component messaging must go through the project's event bus / message
bus abstraction.

Find:
- Direct nats / nats.aio client usage outside the messaging module
- Bare asyncio.Queue used for cross-subsystem communication (single-function
  use is fine)
- Redis pub/sub or similar bypassing the abstraction

Severity: medium.

```

**Agent 67 -- process-spawn-leaks** (sonnet)
File: `_audit/findings/67-process-spawn-leaks.md`

```text
Process spawning and container orchestration must go through the sandbox /
orchestration layer.

Outside sandbox / execution / CLI orchestrator modules, find:
- subprocess.run / Popen
- asyncio.create_subprocess_exec / asyncio.create_subprocess_shell
- docker.DockerClient / aiodocker.Docker instantiation
- os.system or similar shell-outs

Severity: high for arbitrary code paths, medium for admin tools.

```

**Agent 68 -- state-mutation-leaks** (sonnet)
File: `_audit/findings/68-state-mutation-leaks.md`

```text
API controllers should delegate to service-layer methods, not reach into
persistence internals.

In src/synthorg/api/controllers/, find:
- Direct repository method calls for write operations (should go through a service)
- Raw DB session access
- Transaction management inside controllers
- Anything bypassing the service layer to mutate state

Severity: medium.
```

**Agent 69 -- hardcoded-backend-selection** (haiku)
File: `_audit/findings/69-hardcoded-backend-selection.md`

```text
Backend choices must be driven by config factories, not hardcoded in business
logic.

Outside config/, settings/, and factory modules, grep for string literals used
in branching logic: "sqlite", "postgres", "nats", "mem0", "qdrant",
"in_memory", "in-process". Flag patterns like `if backend == "sqlite":` in
business code.

Severity: medium.
```

**Agent 70 -- pluggable-impl-coverage** (sonnet)
File: `_audit/findings/70-pluggable-impl-coverage.md`

```text
Per CLAUDE.md, every pluggable subsystem uses Protocol + concrete strategies +
factory + config discriminator.

For every *_protocol.py, *_factory.py, and *_config.py discriminator in
src/synthorg/:
1. Enumerate all discriminator values (enum members or Literal types)
2. Verify each value has a registered factory mapping
3. Verify each value has at least one test case
4. Verify the discriminator is documented

Flag:
- Discriminator values with no factory entry
- Factory entries with no impl
- Impls with no test

Severity: medium.
```

**Agent 71 -- abstraction-swap-readiness** (sonnet)
File: `_audit/findings/71-abstraction-swap-readiness.md`

```text
Adding a new backend should require zero changes outside the owning module.

Find code that would break that invariant:
- isinstance() checks against concrete backend classes in business logic
- `if backend_type == "X":` branches outside factories
- Concrete impl type hints (e.g. SQLiteRepo) leaking into public APIs where
  the Protocol type should be used
- Direct instantiation of concrete impls outside factories

Severity: medium.
```

**Agent 72 -- dependency-inversion-violations** (sonnet)
File: `_audit/findings/72-dependency-inversion-violations.md`

```text
High-level modules (engine, api, communication) should depend on Protocol
types, not concrete impls.

For each imported symbol in src/synthorg/engine/, src/synthorg/api/, and
src/synthorg/communication/, check if it's a concrete class when a Protocol
exists for the same role. Flag imports of concrete classes where a Protocol
type is available and would satisfy the call site.

Severity: low.
```

### Wave 15: Documentation Truth & Freshness (9 agents)

**Agent 73 -- roadmap-currency** (sonnet)
File: `_audit/findings/73-roadmap-currency.md`

```text
Cross-reference roadmap.md / docs/roadmap*.md with `gh issue list` (open +
closed by version label) and `gh release list`.

Flag:
- Version themes listing issues already closed as open work
- Shipped work still described as future
- Version numbers on the roadmap not matching released tags in pyproject.toml
- Missing entries for versions that have shipped

Severity: medium.
```

**Agent 74 -- comparison-page-accuracy** (sonnet)
File: `_audit/findings/74-comparison-page-accuracy.md`

```text
Read docs/comparison*.md and scripts/generate_comparison.py. For every feature
we claim to support, verify the claim against actual code in src/synthorg/.

Flag:
- Checkmarks for features with no implementation
- Missing checkmarks for features we do implement
- Competitor feature claims without cited sources
- "We support X" statements without the supporting code

Severity: medium for inaccurate self-claims, low for competitor drift.

```

**Agent 75 -- landing-page-metrics** (sonnet)
File: `_audit/findings/75-landing-page-metrics.md`

```text
Check numeric claims on public-facing pages (README, landing, comparison,
docs index). For each number, verify against live source:
- Test count via pytest --collect-only
- Provider count via providers/presets.py
- Backend count via persistence/ subdirectories
- Tool count via tools/registry.py
- Supported model count
- Line count / file count claims

Flag every stale number.

Severity: medium.
```

**Agent 76 -- superseded-decisions** (sonnet)
File: `_audit/findings/76-superseded-decisions.md`

```text
Read docs/decisions*.md, ADR files, and docs/design/ pages. For each accepted
decision, check: was it later reversed or superseded?

Flag:
- Decisions marked "accepted" that code no longer follows
- ADRs without status updates (missing "Superseded by" cross-link)
- "Decided to use X" claims where code now uses Y
- Contradicting decisions across multiple ADRs with no resolution

Severity: medium.
```

**Agent 77 -- config-reference-drift** (sonnet)
File: `_audit/findings/77-config-reference-drift.md`

```text
Compare docs/reference/*.md env var / settings reference against
src/synthorg/settings/definitions/ and src/synthorg/config/.

Flag:
- Documented settings that don't exist in code
- Real settings with no doc entry
- Default values in docs that disagree with code defaults
- Type / validation mismatches

Severity: medium.
```

**Agent 78 -- cli-reference-drift** (sonnet)
File: `_audit/findings/78-cli-reference-drift.md`

```text
Compare CLI reference pages in docs/reference/ (and cli/CLAUDE.md command
listings) against actual cobra definitions in cli/cmd/*.go.

Flag:
- Documented flags or commands that don't exist
- Real flags or commands with no docs entry
- Description drift between docs and cobra Long / Short fields

Severity: medium.
```

**Agent 79 -- api-reference-drift** (sonnet)
File: `_audit/findings/79-api-reference-drift.md`

```text
Compare API reference pages (docs/reference/api*.md, if present) against
actual Litestar routes in src/synthorg/api/controllers/.

Flag:
- Documented endpoints not registered in code
- Registered endpoints with no reference docs
- Request / response shape drift between docs and DTOs

Severity: medium.
```

**Agent 80 -- example-config-validity** (sonnet)
File: `_audit/findings/80-example-config-validity.md`

```text
For every fenced code block in docs/ tagged yaml / toml / json / env / dotenv
that looks like a config example, validate it against the current Pydantic
schema.

Flag:
- Snippets with deprecated keys
- Missing required fields
- Type mismatches
- Keys no longer recognized by the schema

Severity: medium.
```

**Agent 81 -- design-spec-contradictions** (sonnet)
File: `_audit/findings/81-design-spec-contradictions.md`

```text
Cross-reference pages in docs/design/. Find internal contradictions.

Flag:
- Two pages making contradictory claims about the same subsystem (e.g. page A
  says "all writes go through the engine", page B says "workers write directly")
- Terminology drift (same concept named differently across pages)
- `§cross-references` to sections that no longer exist

Severity: medium.
```

### Wave 16: Docs Scope & Rot (5 agents)

**Agent 82 -- docs-scope-creep** (sonnet)
File: `_audit/findings/82-docs-scope-creep.md`

```text
Read each docs/ page and assess whether it has grown beyond its stated purpose.

Flag:
- Pages whose scope (as described in their intro) doesn't match the actual
  content (e.g. architecture page full of HR details)
- Topics that should live on a dedicated page
- Pages over 800 lines mixing unrelated subjects

Severity: low.
```

**Agent 83 -- stale-code-examples** (sonnet)
File: `_audit/findings/83-stale-code-examples.md`

```text
For every fenced code block in docs/ tagged python / typescript / javascript /
go / bash that calls project code, verify the APIs referenced still exist
with the same signatures.

Flag:
- Renamed functions or classes
- Moved imports
- Changed parameter names or types
- Removed methods

Severity: medium.
```

**Agent 84 -- removed-features-still-mentioned** (sonnet)
File: `_audit/findings/84-removed-features-still-mentioned.md`

```text
Read docs/ narrative prose for feature / module / concept names. For each
reference, verify the named thing still exists in code.

Flag:
- "How it works" sections describing subsystems that have been deleted
- Feature walkthroughs for removed capabilities
- Prose referencing renamed modules by their old names

Severity: medium.
```

**Agent 85 -- docs-seo-freshness** (haiku)
File: `_audit/findings/85-docs-seo-freshness.md`

```text
Check page titles, meta descriptions (front matter), and opening paragraphs
in docs/ for:
- Outdated version numbers (e.g. "as of v0.5")
- Dates that have passed (e.g. "coming in Q1 2026")
- "Latest version" claims pointing to a version no longer latest

Severity: low.
```

**Agent 86 -- issue-pr-link-rot** (haiku)
File: `_audit/findings/86-issue-pr-link-rot.md`

```text
Grep docs/ for `#NNN` references to GitHub issues / PRs. For each, verify via
`gh issue view` / `gh pr view` that the reference is still valid.

Flag:
- Deleted issues / PRs
- Renamed issues where the cited title no longer matches
- Links to issues reassigned under a different scope

Severity: low.
```

### Wave 17: Security Deep-Dive (6 agents)

**Agent 87 -- http-security-headers** (sonnet)
File: `_audit/findings/87-http-security-headers.md`

```text
Check HTTP responses for missing security headers: Content-Security-Policy,
Strict-Transport-Security (HSTS), X-Frame-Options, X-Content-Type-Options,
Referrer-Policy, Permissions-Policy.

Scope: api/app.py middleware, Litestar response plugins, reverse proxy configs.

Severity: medium.
```

**Agent 88 -- cookie-auth-security** (sonnet)
File: `_audit/findings/88-cookie-auth-security.md`

```text
Audit authentication and cookie hygiene:
- Cookies without HttpOnly / Secure / SameSite flags
- JWT usage without alg/exp/iss/aud validation
- OAuth flows missing state/nonce parameters
- CSRF protection gaps on state-mutating endpoints

Severity: high.
```

**Agent 89 -- crypto-hygiene** (sonnet)
File: `_audit/findings/89-crypto-hygiene.md`

```text
Find cryptographic anti-patterns:
- `random` / `random.choice` for security-sensitive randomness (should be `secrets`)
- `==` comparison on secrets/tokens (should use `hmac.compare_digest`)
- Weak hash algorithms (MD5, SHA-1) for security
- Hardcoded IVs / nonces

Severity: high.
```

**Agent 90 -- secrets-in-logs** (sonnet)
File: `_audit/findings/90-secrets-in-logs.md`

```text
Check the telemetry privacy allowlist in `src/synthorg/telemetry/privacy.py`
against actual `logger.*` calls. Flag:
- Logger kwargs that could leak PII, tokens, passwords, API keys
- Field names matching forbidden patterns (key, token, secret, password,
  bearer, auth, credential) being logged without scrubbing
- Exception messages that may contain sensitive context logged verbatim

Severity: high.
```

**Agent 91 -- path-traversal-ssrf-xxe-redos** (sonnet)
File: `_audit/findings/91-path-traversal-ssrf-xxe-redos.md`

```text
Find injection-class vulnerabilities:
- Path traversal: user input passed to `open()` / `Path()` without sanitization
- SSRF: user-supplied URLs fetched without an allowlist
- XXE: XML parsing with external entity resolution enabled
- ReDoS: user-supplied strings matched against catastrophic-backtracking regexes

Severity: high.
```

**Agent 92 -- prompt-injection-defenses** (sonnet)
File: `_audit/findings/92-prompt-injection-defenses.md`

```text
Audit LLM prompt handling:
- System prompts concatenated with user input without delimiters/tagging
- LLM output used as tool arguments without schema validation
- Agent-to-agent message content treated as trusted
- Missing `<untrusted-*>` tag wrapping for external content in prompts
- Output schema validation on LLM responses

Severity: high.
```

### Wave 18: Performance & Resource Efficiency (5 agents)

**Agent 93 -- n-plus-one-queries** (sonnet)
File: `_audit/findings/93-n-plus-one-queries.md`

```text
Find N+1 query patterns in persistence and service layers: loops that call
repository methods per item instead of batch loads, per-row fetches in render
paths, missing eager-load joins for related entities.

Severity: high.
```

**Agent 94 -- missing-indices** (sonnet)
File: `_audit/findings/94-missing-indices.md`

```text
Cross-reference WHERE / JOIN / ORDER BY columns in persistence queries with
schema indices. Flag query patterns that would benefit from an index that
doesn't exist. Check both SQLite and Postgres schemas.

Severity: medium.
```

**Agent 95 -- missing-pagination** (sonnet)
File: `_audit/findings/95-missing-pagination.md`

```text
Find API endpoints and repository methods that return unbounded lists.
Everything that can grow should accept cursor/offset+limit parameters.

Severity: medium.
```

**Agent 96 -- blocking-io-hot-paths** (sonnet)
File: `_audit/findings/96-blocking-io-hot-paths.md`

```text
Find blocking I/O inside async hot paths:
- Sync `open()` / `requests.*` / `subprocess.run` in async functions
- CPU-bound work without `run_in_executor`
- Missing gzip/brotli compression on large payload endpoints
- Missing ETag / Cache-Control on cacheable responses

Severity: high.
```

**Agent 97 -- memory-leak-patterns** (sonnet)
File: `_audit/findings/97-memory-leak-patterns.md`

```text
Find leak patterns:
- Event listeners / subscriptions added without teardown
- Zustand stores scheduling timers without cleanup
- Closures holding references to large objects
- Unclosed async generators / contextvars

Scope: src/synthorg/ AND web/src/.

Severity: high.
```

### Wave 19: Test Quality (4 agents)

**Agent 98 -- tests-without-assertions** (sonnet)
File: `_audit/findings/98-tests-without-assertions.md`

```text
Find test functions in tests/ (Python) and web/src/__tests__/ (TS) that have
no assert / expect / raises call. These "tests" pass regardless of behavior
and give false coverage confidence.

Severity: high.
```

**Agent 99 -- tests-with-sleeps** (haiku)
File: `_audit/findings/99-tests-with-sleeps.md`

```text
Grep tests/ and web/src/__tests__/ for hardcoded sleeps / setTimeout /
asyncio.sleep in tests. These indicate timing-dependent tests that should
use deterministic waits (Event, condition variables, fake clocks).

Severity: medium.
```

**Agent 100 -- mock-drift** (sonnet)
File: `_audit/findings/100-mock-drift.md`

```text
Compare mock shapes (MagicMock, unittest.mock patches, vi.mock) against the
real interfaces they stand in for. Flag method names, signatures, or return
types on mocks that don't match the real class/function today.

Severity: medium.
```

**Agent 101 -- e2e-critical-flow-gaps** (sonnet)
File: `_audit/findings/101-e2e-critical-flow-gaps.md`

```text
Identify critical user flows (setup wizard, agent creation, workflow run,
budget check, approval, memory recall) and verify each has at least one E2E
test in web/e2e/ or tests/e2e/. Flag missing coverage.

Severity: medium.
```

### Wave 20: Operational & Data Readiness (5 agents)

**Agent 102 -- graceful-shutdown** (sonnet)
File: `_audit/findings/102-graceful-shutdown.md`

```text
Check shutdown path:
- SIGTERM handler installed?
- In-flight HTTP requests drained?
- Background tasks cancelled with timeout?
- Provider / DB connections closed cleanly?
- Atlas/Postgres connection pools shutdown?

Severity: high.
```

**Agent 103 -- data-retention-gdpr** (sonnet)
File: `_audit/findings/103-data-retention-gdpr.md`

```text
Find PII/user-data fields in Pydantic models and persistence schemas and
check:
- Retention policy documented?
- Deletion flow exists?
- Audit trail for PII reads?

Severity: medium.
```

**Agent 104 -- monitoring-dashboards** (sonnet)
File: `_audit/findings/104-monitoring-dashboards.md`

```text
Check Prometheus metrics emitted by the code against documented Grafana /
Logfire dashboards. Flag metrics without dashboards and dashboards referring
to metrics that no longer exist.

Severity: medium.
```

**Agent 105 -- prompt-eval-coverage** (sonnet)
File: `_audit/findings/105-prompt-eval-coverage.md`

```text
List LLM prompts in src/synthorg/ (agents, tools, quality graders, etc.) and
check each has:
- An eval suite with before/after examples
- Explicit model version pinning
- Temperature / top_p set explicitly (not model default)

Severity: medium.
```

**Agent 106 -- health-readiness-probes** (sonnet)
File: `_audit/findings/106-health-readiness-probes.md`

```text
Verify the API exposes `/healthz` (liveness) and `/readyz` (readiness) with
distinct semantics. Readiness should check DB / provider / queue connectivity;
liveness should only confirm the process is alive.

Severity: medium.
```

### Wave 21: Developer Experience & Reproducibility (2 agents)

**Agent 107 -- slow-precommit-hooks** (haiku)
File: `_audit/findings/107-slow-precommit-hooks.md`

```text
Profile `.pre-commit-config.yaml` hooks by measuring runtime. Flag hooks
taking >3s on a typical `git commit`. Suggest moving expensive ones to
pre-push or CI.

Severity: low.
```

**Agent 108 -- claude-md-reproducibility** (sonnet)
File: `_audit/findings/108-claude-md-reproducibility.md`

```text
For every fenced command in CLAUDE.md, web/CLAUDE.md, cli/CLAUDE.md, and
`.claude/skills/*/SKILL.md`, verify the command actually works today. Flag
commands referencing removed scripts, changed flag names, or missing tools.

Severity: medium.
```

### Wave 22: Code Quality & Duplication (6 agents)

**Agent 109 -- typescript-strictness** (sonnet)
File: `_audit/findings/109-typescript-strictness.md`

```text
In web/src/, count and flag: `any` type usage, `@ts-ignore` / `@ts-expect-error`
comments, non-null assertions (`!`), and type assertions (`as X`) where a type
guard would be safer. Verify tsconfig `strict` is fully enabled.

Severity: medium.
```

**Agent 110 -- duplicate-business-logic** (sonnet)
File: `_audit/findings/110-duplicate-business-logic.md`

```text
Find blocks of business logic duplicated across 2+ modules. Focus on
substantive duplication (>10 lines of non-trivial code), not boilerplate.

Severity: medium.
```

**Agent 111 -- duplicate-types** (sonnet)
File: `_audit/findings/111-duplicate-types.md`

```text
Find types defined on both backend (Pydantic models / dataclasses) and
frontend (TypeScript types / interfaces) that should be generated from a
single source instead. Focus on DTOs, API request/response shapes, and
shared enums.

Severity: medium.
```

**Agent 112 -- duplicate-error-codes** (sonnet)
File: `_audit/findings/112-duplicate-error-codes.md`

```text
Cross-reference custom exception names, RFC 9457 error `type` fields, and
frontend error code enums. Flag the same conceptual error defined in multiple
places.

Severity: medium.
```

**Agent 113 -- feature-flag-coverage** (sonnet)
File: `_audit/findings/113-feature-flag-coverage.md`

```text
Find feature flags / settings that gate risky behavior. Flag:
- Risky features with no kill-switch
- Flags that are always-on or always-off (dead flags)
- Flags referenced in code but not defined in settings

Severity: medium.
```

**Agent 114 -- default-config-sanity** (sonnet)
File: `_audit/findings/114-default-config-sanity.md`

```text
Review default values across `src/synthorg/config/` and
`settings/definitions/`. Flag defaults that are unsafe for production or
surprise the user (debug=True, verbose logging, open CORS, etc.).

Severity: medium.
```

### Wave 23: CI & Supply Chain (5 agents)

**Agent 115 -- workflow-permissions** (sonnet)
File: `_audit/findings/115-workflow-permissions.md`

```text
Audit `.github/workflows/*.yml` for:
- Over-broad `GITHUB_TOKEN` permissions (should be least-privilege per job)
- Missing `permissions:` block (inherits repo default, usually too broad)
- Missing environment protection rules on prod deploys

Severity: high.
```

**Agent 116 -- ci-flakiness** (sonnet)
File: `_audit/findings/116-ci-flakiness.md`

```text
Analyze recent CI run history (via `gh run list`) for patterns:
- Tests failing intermittently on unchanged code
- Jobs hitting timeout consistently
- Cache misses that slow runs significantly

Severity: medium.
```

**Agent 117 -- unused-deps** (sonnet)
File: `_audit/findings/117-unused-deps.md`

```text
Cross-reference dependencies declared in `pyproject.toml`, `web/package.json`,
and `cli/go.mod` with actual import statements. Flag deps that are declared
but never imported anywhere.

Severity: medium.
```

**Agent 118 -- duplicate-deps** (sonnet)
File: `_audit/findings/118-duplicate-deps.md`

```text
Find redundant libraries doing the same job (e.g. lodash + ramda, axios +
fetch wrappers, multiple date libraries). Recommend consolidation.

Severity: low.
```

**Agent 119 -- license-compat** (sonnet)
File: `_audit/findings/119-license-compat.md`

```text
Check dependency licenses against project BUSL-1.1 license. Flag deps with
GPL, AGPL, or other copyleft licenses that conflict with the project license
grant.

Severity: high.
```

### Wave 24: Client Robustness (2 agents)

**Agent 120 -- rate-limit-client** (sonnet)
File: `_audit/findings/120-rate-limit-client.md`

```text
Audit client-side handling of HTTP 429 responses:
- Web dashboard: retry-with-backoff on API calls?
- Python SDK / provider clients: retry-after header respected?
- CLI: graceful degradation on rate-limited endpoints?

Severity: medium.
```

**Agent 121 -- ws-sse-robustness** (sonnet)
File: `_audit/findings/121-ws-sse-robustness.md`

```text
Check WebSocket and Server-Sent Events implementations:
- Reconnection logic with exponential backoff
- Heartbeat / ping-pong to detect stalled connections
- Backpressure handling when client can't keep up
- Message schema versioning
- Graceful fallback if WS/SSE is blocked by proxies

Severity: medium.
```

### Wave 25: Git History & Drift (2 agents)

**Agent 122 -- git-history-secrets-and-bloat** (sonnet)
File: `_audit/findings/122-git-history-secrets-and-bloat.md`

```text
Two narrow checks on full git history (not just current tree):
1. Run `gitleaks detect --log-opts=--all` over full history. Pre-commit
   gitleaks only covers the current commit; this catches secrets that slipped
   in before the hook existed.
2. List top-20 largest blobs in git via
   `git rev-list --objects --all | git cat-file --batch-check='%(objectsize) %(objectname) %(rest)' | sort -rn | head -20`.
   Flag blobs >1MB that should be in LFS or removed.

Severity: critical for secrets, medium for bloat.
```

**Agent 123 -- temporal-drift-wording** (sonnet)
File: `_audit/findings/123-temporal-drift-wording.md`

```text
Scan docs/, CLAUDE.md, web/CLAUDE.md, cli/CLAUDE.md, README.md, and
.claude/skills/*/SKILL.md for temporal / reference-drift wording that will
go stale or is already stale:
- "new in vX.Y", "added in version X", "recently added"
- "as of <date>", "as of <version>"
- "coming soon", "in the next release"
- "the new X" when X is now baseline
- "legacy" markers for code that's now the only implementation
- "temporary" / "workaround" that persisted
- "TODO: remove after <date>" where date has passed
- Positional references like "above", "below", "this here" that rot after reorganisation
- `#NNN` issue references that no longer match the cited topic

Severity: low for stylistic drift, medium for misleading claims.

```

### Retired Agents

These concerns are already enforced by hooks, linters, or external tooling today instead of an audit agent. Do NOT launch these agents; check the "Now enforced by" column if a related concern needs attention.

| Retired agent | Now enforced by |
|---|---|
| hardcoded-secrets | `gitleaks` pre-commit + CI |
| hardcoded-display-values | `scripts/check_web_design_system.py` + `scripts/check_backend_regional_defaults.py` PostToolUse hooks |
| design-token-violations | `scripts/check_web_design_system.py` PostToolUse hook |
| go-error-handling | `golangci-lint` (errcheck, wrapcheck, errorlint) pre-commit + CI |
| go-resource-leaks | `golangci-lint` + `go vet` pre-commit + CI |
| changelog-release-notes | `release-please` (automated) |
| changelog-releases-parity | `release-please` (automated) |

### Planned Retirements

These concerns have a planned hook, linter, or external-tool replacement, but the enforcement is not fully wired yet. Keep launching these audit agents until the replacement is enabled; once the TODO ships, move the row up to the Retired Agents table.

| Agent to keep active for now | Planned enforcement |
|---|---|
| wrong-logger-pattern | Custom ruff rule or pre-commit regex hook (TODO: add) |
| unstructured-logging | Custom ruff rule (TODO: add) |
| unused-web-components | `knip` in CI (TODO: wire) |
| unused-web-hooks | `knip` in CI (TODO: wire) |
| unused-web-utils | `knip` / `ts-prune` in CI (TODO: wire) |
| vendor-name-leaks | Extend `scripts/check_forbidden_literals.py` (TODO) |
| long-functions | Ruff `C901` / `PLR0915` + eslint `max-lines-per-function` (TODO: enable) |
| long-files | Ruff + eslint `max-lines` (TODO: enable) |
| future-annotations-leak | Ruff `FA100` / `FA102` (TODO: enable) |
| docs-links-refs | `lychee` in CI (TODO: wire) |

---

## Phase 3: Validate Findings (sonnet agents)

**Required for standard runs.** For `--quick` runs or when fewer than 5 critical+high findings exist, validation may be skipped.

After all launched audit agents complete, launch validation agents to verify findings. The number of agents depends on scope (123 for `full`, fewer for scoped runs).

### Process

1. Read all finding files present in `_audit/findings/`
2. Collect all critical + high severity findings into a validation queue
3. If queue exceeds 50 findings, prioritize by clustering related findings (same file/module)
4. Split the queue into batches of ~12 findings each
5. Launch one **sonnet** validation agent per batch (in parallel, `run_in_background: true`)

### Validation Agent Prompt

```text
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
2. Delete FALSE_POSITIVE findings entirely from the audit files (edit in place)
3. Mark INTENTIONAL findings as excluded (keep in file but prefix with `[INTENTIONAL]`)
4. Report: "Validated N findings. Removed M false positives (X%)."

Validation may be skipped when `--quick` is set or when fewer than 5 critical+high findings exist.

---

## Phase 4: Build INDEX.md

After validation, read all finding files and build `_audit/INDEX.md`:

```markdown
# Codebase Audit Index

**Date**: {date}
**Scope**: {scope}
**Agents**: {agents_launched}
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

| Wave | Findings | Top Issue (highest severity finding) |
|------|----------|--------------------------------------|
| 1. Observability | N | ... |
| 2. Wiring | N | ... |
| ... | ... | ... |

## Top 20 Critical + High Findings

| # | Severity | File:Line | Issue | Agent |
|---|----------|-----------|-------|-------|
| 1 | critical | ... | ... | ... |
| ... | ... | ... | ... | ... |

## Zero-Finding Categories

These agents found no issues. Review the agent prompt to understand what was
checked -- this may indicate code quality in that area, or the search pattern
may not match the codebase's conventions:
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
3. **Validation is required** for critical+high findings on standard runs (may be skipped with `--quick` or fewer than 5 findings)
4. **Batch execution** -- ~10 agents per batch, wait between batches
5. **Sonnet for analysis, Haiku for pattern matching** -- never Opus for audit agents
6. **Do NOT fix anything** -- audit only, findings only
7. **Rerunnable** -- clean `_audit/` at start of every run
8. **Never use em-dashes** in any output files (project convention)
9. **Report progress** after each batch completes
