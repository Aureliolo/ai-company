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
