# Persistence Boundary: Exception Categories

On-demand reference. The top rule in `CLAUDE.md` is: `src/synthorg/persistence/` is the **only** place that may import `aiosqlite`, `sqlite3`, `psycopg`, or `psycopg_pool`, or emit raw SQL DDL/DML keywords in string literals. Every durable feature must define a repository Protocol under `persistence/<domain>_protocol.py`, concrete impls under `persistence/{sqlite,postgres}/`, and expose them on `PersistenceBackend`.

## Three sanctioned exception categories

Sanctioned exceptions cover three categories. The authoritative list lives in `_ALLOWLIST` inside `scripts/check_persistence_boundary.py`; any new exception must be added there with a justifying comment.

### 1. Agent-facing DB tools

- `src/synthorg/tools/database/schema_inspect.py`
- `src/synthorg/tools/database/sql_query.py`

### 2. Security / scanning utilities that inspect user-supplied SQL

- e.g. `src/synthorg/security/rules/destructive_op_detector.py`, whose detection payload *is* DDL keyword strings.

### 3. Test fixtures / conformance harnesses

- Hold driver primitives for cross-subsystem setup.

## In-memory fallbacks

In-memory fallbacks in `persistence/integration_stubs.py` are named `InMemoryXRepository` (NOT `StubXRepository`) to signal that they are *working* repositories, just process-local and non-durable. These still require durable SQLite + Postgres counterparts (tracked in issue #1517); the `InMemory*` naming does not relax that obligation.

## Service layer

Controllers and API endpoints access persistence through domain-scoped **service layers** (e.g. `ArtifactService`, `WorkflowService`, `MemoryService`, `CustomRulesService`, `UserService`, `ProjectService`, `SsrfViolationService`, `SettingsService`) rather than reaching into repositories directly.

Services:

- Keep controllers thin (parse / shape / return).
- Centralize `API_*` / `META_*` / `WORKFLOW_DEF_*` audit logging in one place.
- Own cross-repo orchestration (e.g. workflow-definition delete cascading to version snapshots).

Repositories **must not** log mutations themselves (enforced by `scripts/check_persistence_boundary.py`). The service layer is the canonical logging point so audit trails do not duplicate when multiple callers share a repo. Repos may still log fetch telemetry (`*_FETCHED`, `*_LISTED`, `*_COUNTED`) and error paths (`*_SAVE_FAILED`, `*_DELETE_FAILED`, `*_DUPLICATE`); the rule targets entity-mutation audit specifically.

## Migrations

Adding a migration: read `docs/guides/persistence-migrations.md` first. Do not hand-edit SQL in `persistence/{sqlite,postgres}/revisions/`, and do not edit `atlas.sum`. Rehashing via `atlas migrate hash` post-release is blocked by a PreToolUse hook; delete the in-progress migration and regenerate with `atlas migrate diff` instead.

## Per-line opt-out

`# lint-allow: persistence-boundary -- <required justification>` as a trailing comment. The `--` separator is part of the opt-out syntax itself; the justification after it must be non-empty.

## Enforcement

`scripts/check_persistence_boundary.py` (pre-push hook + CI Lint job).
