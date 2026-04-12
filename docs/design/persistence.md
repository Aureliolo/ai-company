---
title: Persistence
description: Repository protocol abstraction, SQLite and Postgres backends, time-series tables, TimescaleDB hypertables, and extension strategy.
---

# Persistence

SynthOrg abstracts durable storage behind a set of repository protocols so the
engine, agent runtime, budget tracker, security auditor, and HR subsystems all
depend on interfaces rather than concrete backends.  Two backends ship in the
reference implementation: SQLite for single-user development and small
self-hosted setups, Postgres for multi-user production deployments with
concurrent writers.  Both implement the same Python protocol surface; switching
backends is a configuration change, not a code change.

## Backend catalog

| Backend  | Primary use case                                    | Concurrency model                    | Migration tool |
|----------|-----------------------------------------------------|--------------------------------------|----------------|
| SQLite   | Single-user dev, small self-hosted, demos           | Single-writer with WAL journaling    | Atlas          |
| Postgres | Multi-user production, high-concurrency write paths | Row-level MVCC, server-side triggers | Atlas          |

Repositories live under `src/synthorg/persistence/sqlite/` and
`src/synthorg/persistence/postgres/`.  Each concrete repository implements the
protocol in `synthorg.persistence.repositories`; application code depends on the
protocol, not the implementation.  This makes switching backends a
configuration change (``PersistenceConfig.backend``) rather than a code change,
and keeps the unit-test suite backend-free so most tests stay fast and local.

Postgres adds server-side integrity beyond what SQLite can express: `CONSTRAINT
TRIGGER`s enforce "exactly one CEO" and "at least one owner" invariants across
concurrent writers, and optional capability protocols surface Postgres-native
features (JSONB analytics, TimescaleDB hypertables) that SQLite callers
simply do not see.

## Schema patterns

The schema (`src/synthorg/persistence/postgres/schema.sql` and its SQLite
sibling) mixes two write patterns:

**Mutable tables** -- canonical state with in-place updates.  Examples:
`users`, `settings`, `agent_states`, `heartbeats`.  Rows are updated on every
state transition; row count stays bounded.  Concurrent updates are serialised
by MVCC + application-level CAS (settings use `updated_at` as an etag; see
`SettingsRepository.set` and `set_many`).

**Append-only time-series tables** -- facts with a timestamp column, never
updated in place.  Examples: `cost_records`, `audit_entries`,
`lifecycle_events`, `messages`, `task_metrics`, `collaboration_metrics`,
`login_attempts`.  These tables grow linearly with system activity and are the
primary candidates for time-based partitioning.  `cost_records` and
`audit_entries` both have the partitioning column (`timestamp`) composed into
the primary key so they can be converted to TimescaleDB hypertables without
touching any application code.

`heartbeats` is deliberately **excluded** from the append-only set.  Despite
having a timestamp, it stores one row per `execution_id` and updates that row
on every pulse -- the write pattern is update-heavy and the row count is
bounded by the number of live executions.  Hypertables optimise for immutable
append-only data, so converting `heartbeats` would be the wrong choice.

## Time-series tables and TimescaleDB hypertables

For append-only tables on Postgres deployments, SynthOrg supports converting
`cost_records` and `audit_entries` into TimescaleDB hypertables.  Hypertables
transparently partition the data into time-bucketed chunks so queries that
filter on `timestamp` scan a bounded subset of chunks rather than the whole
table, and operations like `DROP TABLE` or chunk eviction become O(chunk
count) rather than O(row count).

The feature is **off by default** and gated behind
`PostgresConfig.enable_timescaledb`.  Operators running vanilla Postgres or a
managed service without TimescaleDB leave it off and the tables stay regular
relational tables with a composite primary key.  Note: the composite-primary-key
schema change and its Atlas migration run unconditionally (they are valid on
vanilla Postgres); only the `create_hypertable` step is gated behind the flag.

```python
PostgresConfig(
    ...,
    enable_timescaledb=True,
    cost_records_chunk_interval="1 day",
    audit_entries_chunk_interval="1 day",
)
```

When enabled, the backend's `migrate` method runs two phases: first Atlas
applies the declarative schema migrations, then a dedicated step calls
`create_hypertable` on each target table.  The conversion is idempotent
(`if_not_exists => TRUE`) so reruns and restores are safe.  If the
`timescaledb` extension is not installed on the server, the flag is treated as
a best-effort hint and the backend logs a warning rather than failing the
migration -- this lets operators leave the flag true in shared config and have
it degrade gracefully on clusters that do not support it.

**Scope: Apache-2.0 features only.**  The Postgres backend uses exclusively
TimescaleDB features that ship under Apache-2.0: core hypertables,
`create_hypertable`, chunk management, and `drop_chunks`.  Retention policies,
compression, and continuous aggregates are under the Timescale License and are
**not** used -- they would force every deployment to accept the Timescale
License terms and would not run on the OSS image (`-oss` tag).  Self-hosted
operators who want retention today can call `drop_chunks('cost_records',
older_than => INTERVAL '90 days')` on their own cron schedule until SynthOrg
grows a backend-owned retention policy that stays within Apache-2.0.

| Table           | Included | Rationale                                                         |
|-----------------|----------|-------------------------------------------------------------------|
| `cost_records`  | Yes      | LLM call costs; append-only; highest-volume time-series table.    |
| `audit_entries` | Yes      | Security events; append-only; compliance queries are time-bound.  |
| `heartbeats`    | No       | Update-heavy (per-execution row bump); hypertable semantics wrong. |

### Managed-service compatibility

TimescaleDB is a self-hosted-only feature.  The major managed Postgres offerings
(AWS RDS, Google Cloud SQL) do not allow custom extensions; operators
cannot install `timescaledb` there.  Azure Database for PostgreSQL
Flexible Server is an exception -- it supports TimescaleDB as an extension.  SynthOrg runs
cleanly on all of them -- leave `enable_timescaledb=False` and the schema stays
fully relational.  The composite primary keys on `cost_records` and
`audit_entries` are valid on vanilla Postgres and do not require TimescaleDB to
function; they just preserve the option of turning hypertables on later if the
deployment moves to self-hosted.

| Deployment target            | TimescaleDB support | Recommended setting |
|------------------------------|---------------------|---------------------|
| Self-hosted Postgres 18+     | Operator-installed  | `enable_timescaledb=True` |
| AWS RDS / Aurora Postgres    | Not available       | `enable_timescaledb=False` |
| Google Cloud SQL Postgres    | Not available       | `enable_timescaledb=False` |
| Azure Database for Postgres (Flexible Server) | Supported (extension) | `enable_timescaledb=True` |
| Docker / local dev           | `timescale/timescaledb:latest-pg18-oss` | `enable_timescaledb=True` |

## Extension strategy

Postgres extensions need two things to work through Atlas's declarative
pipeline: the extension DDL has to be acceptable to Atlas's dev database during
`atlas migrate diff`, and any catalog objects the extension creates after
migrations run must not be flagged as drift on subsequent diffs.  SynthOrg
handles this with a two-step pattern:

1. **Declarative schema** (`schema.sql` + Atlas migrations) only contains DDL
   that is valid on vanilla Postgres.  Function-call SQL like
   `SELECT create_hypertable(...)` cannot live here because Atlas's declarative
   diff engine does not parse function calls.
2. **Runtime setup hooks** in the backend's `migrate` method run post-Atlas SQL
   against the real target database.  These hooks detect extension
   availability via `pg_available_extensions` and skip gracefully when the
   extension is not installed, so the same config works on vanilla Postgres
   and on self-hosted TimescaleDB without branching at deployment time.

This pattern scales to other extensions (`pgvector`, `pg_trgm`, `pgcrypto`) if
SynthOrg adopts them later.  The rule is: if the extension adds objects that
Atlas cannot express or recognize, add a runtime setup hook; if the extension
is purely about `CREATE EXTENSION` and then standard DDL, let Atlas own it.

## Migration workflow

Migrations are generated by [Atlas](https://atlasgo.io/) from the single source
of truth in `src/synthorg/persistence/<backend>/schema.sql`:

```bash
atlas migrate diff --env sqlite <name>     # SQLite
atlas migrate diff --env postgres <name>   # Postgres (requires Docker dev DB)
```

Never hand-edit generated migration files, and never run `atlas migrate hash`
post-release (a PreToolUse hook blocks it in the default environment).  If a
migration needs to change before it has landed, delete the file and regenerate
it via `atlas migrate diff`; this preserves `atlas.sum` integrity end-to-end.

Hand-written migrations (procedural SQL that Atlas cannot derive from
`schema.sql`) are NOT added to the `revisions/` directory because they would
invalidate `atlas.sum`.  Instead, procedural setup runs through the backend's
runtime migration hooks (see the TimescaleDB pattern above).

## Migration squashing

As the migration count grows, the revisions directory becomes harder to review
and Atlas's diff engine slows perceptibly.  SynthOrg uses a periodic partial
squash to keep the history manageable while preserving upgrade paths.

### When squashing triggers

The squash script (`scripts/squash_migrations.sh`) checks both SQLite and
Postgres backends.  When a backend exceeds **100 migration files** (configurable
via `SQUASH_THRESHOLD`), the oldest files beyond the **newest 50**
(`SQUASH_KEEP`) are replaced by a single Atlas checkpoint.

### How it works

1. The script copies the oldest files to a temporary directory and runs
   `atlas migrate checkpoint` to produce a DDL-only snapshot of the schema at
   that point.
2. The checkpoint file is timestamped between the last squashed migration and
   the first kept migration so Atlas orders it correctly.
3. The original revisions directory is rebuilt with the checkpoint plus the
   remaining individual files, and `atlas migrate hash` regenerates
   `atlas.sum`.

### Upgrade paths after squash

| Database state | Behavior |
|---|---|
| Fresh install | Applies checkpoint (full schema to squash point) then remaining files |
| At or past squash point | Skips checkpoint, applies only unapplied files |
| Before squash point | **Error** -- the individual files it needs are gone; upgrade through the unsquashed release first |

The "before squash point" case is safe because the threshold (100) and keep
count (50) guarantee that by the time a squash runs, all production databases
have had at least 50 migration versions to catch up past the squash boundary.

### Dual-backend squashing

Both SQLite and Postgres backends are processed independently in a single
invocation.  Each backend may have a different migration count; only backends
that exceed the threshold are squashed.

```bash
bash scripts/squash_migrations.sh
```

### Committing a squash

Squash commits delete old migration files and rewrite `atlas.sum`, which the
pre-commit hook `check_no_modify_migration.sh` would normally block.  Set the
`SYNTHORG_MIGRATION_SQUASH` environment variable to bypass:

```bash
SYNTHORG_MIGRATION_SQUASH=1 git commit -m "chore: squash oldest migrations"
```
