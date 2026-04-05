-- SynthOrg SQLite schema -- single source of truth.
--
-- Fresh installs apply this file directly via apply_schema().
-- When data stability is declared, adopt Atlas for declarative
-- migrations (diff schema.sql against the current DB).

-- ── Tasks ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    type TEXT NOT NULL,
    priority TEXT NOT NULL DEFAULT 'medium',
    project TEXT NOT NULL,
    created_by TEXT NOT NULL,
    assigned_to TEXT,
    status TEXT NOT NULL DEFAULT 'created',
    estimated_complexity TEXT NOT NULL DEFAULT 'medium',
    budget_limit REAL NOT NULL DEFAULT 0.0,
    deadline TEXT,
    max_retries INTEGER NOT NULL DEFAULT 1,
    parent_task_id TEXT,
    task_structure TEXT,
    coordination_topology TEXT NOT NULL DEFAULT 'auto',
    reviewers TEXT NOT NULL DEFAULT '[]',
    dependencies TEXT NOT NULL DEFAULT '[]',
    artifacts_expected TEXT NOT NULL DEFAULT '[]',
    acceptance_criteria TEXT NOT NULL DEFAULT '[]',
    delegation_chain TEXT NOT NULL DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_assigned_to ON tasks(assigned_to);
CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project);

-- ── Cost records ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cost_records (
    rowid INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    task_id TEXT NOT NULL REFERENCES tasks(id),
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cost_usd REAL NOT NULL,
    timestamp TEXT NOT NULL,
    call_category TEXT
);

CREATE INDEX IF NOT EXISTS idx_cost_records_agent_id ON cost_records(agent_id);
CREATE INDEX IF NOT EXISTS idx_cost_records_task_id ON cost_records(task_id);

-- ── Messages ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    sender TEXT NOT NULL,
    "to" TEXT NOT NULL,
    type TEXT NOT NULL,
    priority TEXT NOT NULL DEFAULT 'normal',
    channel TEXT NOT NULL,
    content TEXT NOT NULL,
    attachments TEXT NOT NULL DEFAULT '[]',
    metadata TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_messages_channel ON messages(channel);
CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);

-- ── Lifecycle events ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS lifecycle_events (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    agent_name TEXT NOT NULL,
    event_type TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    initiated_by TEXT NOT NULL,
    details TEXT NOT NULL DEFAULT '',
    metadata TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_le_agent_id ON lifecycle_events(agent_id);
CREATE INDEX IF NOT EXISTS idx_le_event_type ON lifecycle_events(event_type);
CREATE INDEX IF NOT EXISTS idx_le_timestamp ON lifecycle_events(timestamp);

-- ── Task metrics ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS task_metrics (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    task_id TEXT NOT NULL REFERENCES tasks(id),
    task_type TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    is_success INTEGER NOT NULL,
    duration_seconds REAL NOT NULL,
    cost_usd REAL NOT NULL,
    turns_used INTEGER NOT NULL,
    tokens_used INTEGER NOT NULL,
    quality_score REAL,
    complexity TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tm_agent_id ON task_metrics(agent_id);
CREATE INDEX IF NOT EXISTS idx_tm_completed_at ON task_metrics(completed_at);
CREATE INDEX IF NOT EXISTS idx_tm_agent_completed
    ON task_metrics(agent_id, completed_at);

-- ── Collaboration metrics ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS collaboration_metrics (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    delegation_success INTEGER,
    delegation_response_seconds REAL,
    conflict_constructiveness REAL,
    meeting_contribution REAL,
    loop_triggered INTEGER NOT NULL DEFAULT 0,
    handoff_completeness REAL
);

CREATE INDEX IF NOT EXISTS idx_cm_agent_id ON collaboration_metrics(agent_id);
CREATE INDEX IF NOT EXISTS idx_cm_recorded_at
    ON collaboration_metrics(recorded_at);
CREATE INDEX IF NOT EXISTS idx_cm_agent_recorded
    ON collaboration_metrics(agent_id, recorded_at);

-- ── Parked contexts ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS parked_contexts (
    id TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    task_id TEXT,
    approval_id TEXT NOT NULL,
    parked_at TEXT NOT NULL,
    context_json TEXT NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_pc_agent_id ON parked_contexts(agent_id);
CREATE INDEX IF NOT EXISTS idx_pc_approval_id ON parked_contexts(approval_id);

-- ── Audit entries ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_entries (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    agent_id TEXT,
    task_id TEXT,
    tool_name TEXT NOT NULL,
    tool_category TEXT NOT NULL,
    action_type TEXT NOT NULL,
    arguments_hash TEXT NOT NULL,
    verdict TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    reason TEXT NOT NULL,
    matched_rules TEXT NOT NULL DEFAULT '[]',
    evaluation_duration_ms REAL NOT NULL,
    approval_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_ae_timestamp ON audit_entries(timestamp);
CREATE INDEX IF NOT EXISTS idx_ae_agent_id ON audit_entries(agent_id);
CREATE INDEX IF NOT EXISTS idx_ae_action_type ON audit_entries(action_type);
CREATE INDEX IF NOT EXISTS idx_ae_verdict ON audit_entries(verdict);
CREATE INDEX IF NOT EXISTS idx_ae_risk_level ON audit_entries(risk_level);

-- ── Settings (namespaced key-value) ───────────────────────────
CREATE TABLE IF NOT EXISTS settings (
    namespace TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (namespace, key)
);

-- ── Users ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    must_change_password INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE UNIQUE INDEX IF NOT EXISTS idx_single_ceo ON users(role) WHERE role = 'ceo';

-- ── API keys ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS api_keys (
    id TEXT PRIMARY KEY,
    key_hash TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    expires_at TEXT,
    revoked INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON api_keys(user_id);

-- ── Sessions ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    username TEXT NOT NULL,
    role TEXT NOT NULL,
    ip_address TEXT NOT NULL DEFAULT '',
    user_agent TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    last_active_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revoked INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_revoked_expires
    ON sessions(user_id, revoked, expires_at);
CREATE INDEX IF NOT EXISTS idx_sessions_revoked_expires
    ON sessions(revoked, expires_at);
CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at);

-- ── Checkpoints ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS checkpoints (
    id TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    turn_number INTEGER NOT NULL CHECK (turn_number >= 0),
    context_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cp_execution_id ON checkpoints(execution_id);
CREATE INDEX IF NOT EXISTS idx_cp_task_id ON checkpoints(task_id);
CREATE INDEX IF NOT EXISTS idx_cp_exec_turn
    ON checkpoints(execution_id, turn_number);
CREATE INDEX IF NOT EXISTS idx_cp_task_turn
    ON checkpoints(task_id, turn_number);

-- ── Heartbeats ────────────────────────────────────────────────
-- No FK to tasks -- checkpoints/heartbeats are ephemeral recovery
-- data that may outlive their tasks.  Cleanup is the engine's
-- responsibility (delete_by_execution after completion).
CREATE TABLE IF NOT EXISTS heartbeats (
    execution_id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    last_heartbeat_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_hb_last_heartbeat
    ON heartbeats(last_heartbeat_at);

-- ── Agent states ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agent_states (
    agent_id TEXT PRIMARY KEY,
    execution_id TEXT,
    task_id TEXT,
    status TEXT NOT NULL DEFAULT 'idle'
        CHECK (status IN ('idle', 'executing', 'paused')),
    turn_count INTEGER NOT NULL DEFAULT 0 CHECK (turn_count >= 0),
    accumulated_cost_usd REAL NOT NULL DEFAULT 0.0
        CHECK (accumulated_cost_usd >= 0.0),
    last_activity_at TEXT NOT NULL,
    started_at TEXT,
    CHECK (
        (status = 'idle'
         AND execution_id IS NULL
         AND task_id IS NULL
         AND started_at IS NULL
         AND turn_count = 0
         AND accumulated_cost_usd = 0.0)
        OR
        (status IN ('executing', 'paused')
         AND execution_id IS NOT NULL
         AND started_at IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_as_status_activity
    ON agent_states(status, last_activity_at DESC);

-- ── Artifacts ────────────────────────────────────────────────
-- No FK to tasks -- artifacts may outlive tasks (same rationale
-- as heartbeats/checkpoints).
CREATE TABLE IF NOT EXISTS artifacts (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    path TEXT NOT NULL,
    task_id TEXT NOT NULL,
    created_by TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    content_type TEXT NOT NULL DEFAULT '',
    size_bytes INTEGER NOT NULL DEFAULT 0 CHECK (size_bytes >= 0),
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_artifacts_task_id ON artifacts(task_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_created_by ON artifacts(created_by);
CREATE INDEX IF NOT EXISTS idx_artifacts_type ON artifacts(type);

-- ── Projects ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    team TEXT NOT NULL DEFAULT '[]',
    lead TEXT,
    task_ids TEXT NOT NULL DEFAULT '[]',
    deadline TEXT,
    budget REAL NOT NULL DEFAULT 0.0 CHECK (budget >= 0.0),
    status TEXT NOT NULL DEFAULT 'planning'
);

CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
CREATE INDEX IF NOT EXISTS idx_projects_lead ON projects(lead);

-- ── Custom personality presets (user-defined) ────────────────
CREATE TABLE IF NOT EXISTS custom_presets (
    name TEXT PRIMARY KEY CHECK(length(name) > 0),
    config_json TEXT NOT NULL CHECK(length(config_json) > 0),
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS workflow_definitions (
    id TEXT PRIMARY KEY NOT NULL CHECK(length(id) > 0),
    name TEXT NOT NULL CHECK(length(name) > 0),
    description TEXT NOT NULL DEFAULT '',
    workflow_type TEXT NOT NULL CHECK(workflow_type IN (
        'sequential_pipeline', 'parallel_execution', 'kanban', 'agile_kanban'
    )),
    nodes TEXT NOT NULL,
    edges TEXT NOT NULL,
    created_by TEXT NOT NULL CHECK(length(created_by) > 0),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1 CHECK(version >= 1)
);

CREATE INDEX IF NOT EXISTS idx_wd_workflow_type
    ON workflow_definitions(workflow_type);

CREATE INDEX IF NOT EXISTS idx_wd_updated_at
    ON workflow_definitions(updated_at DESC);

-- Workflow execution instances ------------------------------------------------

CREATE TABLE IF NOT EXISTS workflow_executions (
    id TEXT PRIMARY KEY NOT NULL CHECK(length(id) > 0),
    definition_id TEXT NOT NULL CHECK(length(definition_id) > 0),
    definition_version INTEGER NOT NULL CHECK(definition_version >= 1),
    status TEXT NOT NULL CHECK(status IN (
        'pending', 'running', 'completed', 'failed', 'cancelled'
    )),
    node_executions TEXT NOT NULL DEFAULT '[]',
    activated_by TEXT NOT NULL CHECK(length(activated_by) > 0),
    project TEXT NOT NULL CHECK(length(project) > 0),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT,
    error TEXT,
    version INTEGER NOT NULL DEFAULT 1 CHECK(version >= 1),
    FOREIGN KEY (definition_id) REFERENCES workflow_definitions(id)
);

CREATE INDEX IF NOT EXISTS idx_wfe_definition_id
    ON workflow_executions(definition_id);

CREATE INDEX IF NOT EXISTS idx_wfe_status
    ON workflow_executions(status);

CREATE INDEX IF NOT EXISTS idx_wfe_updated_at
    ON workflow_executions(updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_wfe_definition_updated
    ON workflow_executions(definition_id, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_wfe_status_updated
    ON workflow_executions(status, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_wfe_project
    ON workflow_executions(project);

-- ── Fine-tuning pipeline runs ───────────────────────────────────
CREATE TABLE IF NOT EXISTS fine_tune_runs (
    id TEXT PRIMARY KEY NOT NULL CHECK(length(id) > 0),
    stage TEXT NOT NULL CHECK(stage IN ('idle', 'generating_data', 'mining_negatives', 'training', 'evaluating', 'deploying', 'complete', 'failed')),
    progress REAL CHECK(progress IS NULL OR (progress >= 0.0 AND progress <= 1.0)),
    error TEXT,
    config_json TEXT NOT NULL,
    started_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT,
    stages_completed TEXT NOT NULL DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_ftr_stage
    ON fine_tune_runs(stage);

CREATE INDEX IF NOT EXISTS idx_ftr_started_at
    ON fine_tune_runs(started_at DESC);

CREATE INDEX IF NOT EXISTS idx_ftr_updated_at
    ON fine_tune_runs(updated_at DESC);

-- ── Fine-tuning checkpoints ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS fine_tune_checkpoints (
    id TEXT PRIMARY KEY NOT NULL CHECK(length(id) > 0),
    run_id TEXT NOT NULL REFERENCES fine_tune_runs(id) ON DELETE CASCADE,
    model_path TEXT NOT NULL,
    base_model TEXT NOT NULL,
    doc_count INTEGER NOT NULL CHECK(doc_count >= 0),
    eval_metrics_json TEXT,
    size_bytes INTEGER NOT NULL CHECK(size_bytes >= 0),
    created_at TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 0 CHECK(is_active IN (0, 1)),
    backup_config_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_ftc_run_id
    ON fine_tune_checkpoints(run_id);

CREATE INDEX IF NOT EXISTS idx_ftc_active
    ON fine_tune_checkpoints(is_active);

CREATE UNIQUE INDEX IF NOT EXISTS idx_ftc_single_active
    ON fine_tune_checkpoints(is_active)
    WHERE is_active = 1;

CREATE INDEX IF NOT EXISTS idx_ftc_created_at
    ON fine_tune_checkpoints(created_at DESC);

-- ── Workflow Definition Versions ─────────────────────────────

CREATE TABLE IF NOT EXISTS workflow_definition_versions (
    definition_id TEXT NOT NULL CHECK(length(definition_id) > 0),
    version INTEGER NOT NULL CHECK(version >= 1),
    name TEXT NOT NULL CHECK(length(name) > 0),
    description TEXT NOT NULL DEFAULT '',
    workflow_type TEXT NOT NULL CHECK(workflow_type IN (
        'sequential_pipeline', 'parallel_execution', 'kanban', 'agile_kanban'
    )),
    nodes TEXT NOT NULL,
    edges TEXT NOT NULL,
    created_by TEXT NOT NULL CHECK(length(created_by) > 0),
    saved_by TEXT NOT NULL CHECK(length(saved_by) > 0),
    saved_at TEXT NOT NULL,
    PRIMARY KEY (definition_id, version),
    FOREIGN KEY (definition_id)
        REFERENCES workflow_definitions(id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_wdv_definition_saved
    ON workflow_definition_versions(definition_id, saved_at DESC);

-- ── Decision records (auditable decisions drop-box) ─────────────
-- Append-only audit trail.  ON DELETE RESTRICT on the tasks FK is
-- deliberate: preserving the audit trail takes priority over task
-- cleanup, so tasks with decision records cannot be deleted until
-- their audit entries are explicitly archived or purged.  Dropping
-- this RESTRICT would silently cascade-delete audit data and violate
-- issue #700's append-only guarantee.
CREATE TABLE IF NOT EXISTS decision_records (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE RESTRICT,
    approval_id TEXT,
    executing_agent_id TEXT NOT NULL,
    reviewer_agent_id TEXT NOT NULL CHECK(reviewer_agent_id != executing_agent_id),
    decision TEXT NOT NULL CHECK(decision IN (
        'approved', 'rejected', 'auto_approved', 'auto_rejected', 'escalated'
    )),
    reason TEXT,
    criteria_snapshot TEXT NOT NULL DEFAULT '[]',
    -- recorded_at must be ISO 8601 with a UTC offset ('+00:00' or 'Z')
    -- so lexicographic ordering equals chronological ordering.  The
    -- repository normalizes to UTC via .astimezone(UTC).isoformat()
    -- before inserting; the CHECK here enforces the invariant against
    -- raw SQL callers and migrations.
    recorded_at TEXT NOT NULL CHECK(
        recorded_at LIKE '%+00:00' OR recorded_at LIKE '%Z'
    ),
    version INTEGER NOT NULL CHECK(version >= 1),
    metadata TEXT NOT NULL DEFAULT '{}',
    UNIQUE(task_id, version)
);

-- idx_dr_task_id is intentionally omitted -- the UNIQUE(task_id, version)
-- constraint already creates a covering index on task_id as the leading
-- key.  Adding a separate idx on task_id alone would be redundant write
-- overhead with no planner benefit.
CREATE INDEX IF NOT EXISTS idx_dr_executing_agent_recorded
    ON decision_records(executing_agent_id, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_dr_reviewer_agent_recorded
    ON decision_records(reviewer_agent_id, recorded_at DESC);
