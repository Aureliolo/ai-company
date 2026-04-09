-- Create "tasks" table
CREATE TABLE `tasks` (
  `id` text NULL,
  `title` text NOT NULL,
  `description` text NOT NULL,
  `type` text NOT NULL,
  `priority` text NOT NULL DEFAULT 'medium',
  `project` text NOT NULL,
  `created_by` text NOT NULL,
  `assigned_to` text NULL,
  `status` text NOT NULL DEFAULT 'created',
  `estimated_complexity` text NOT NULL DEFAULT 'medium',
  `budget_limit` real NOT NULL DEFAULT 0.0,
  `deadline` text NULL,
  `max_retries` integer NOT NULL DEFAULT 1,
  `parent_task_id` text NULL,
  `task_structure` text NULL,
  `coordination_topology` text NOT NULL DEFAULT 'auto',
  `reviewers` text NOT NULL DEFAULT '[]',
  `dependencies` text NOT NULL DEFAULT '[]',
  `artifacts_expected` text NOT NULL DEFAULT '[]',
  `acceptance_criteria` text NOT NULL DEFAULT '[]',
  `delegation_chain` text NOT NULL DEFAULT '[]',
  PRIMARY KEY (`id`)
);
-- Create index "idx_tasks_status" to table: "tasks"
CREATE INDEX `idx_tasks_status` ON `tasks` (`status`);
-- Create index "idx_tasks_assigned_to" to table: "tasks"
CREATE INDEX `idx_tasks_assigned_to` ON `tasks` (`assigned_to`);
-- Create index "idx_tasks_project" to table: "tasks"
CREATE INDEX `idx_tasks_project` ON `tasks` (`project`);
-- Create "cost_records" table
CREATE TABLE `cost_records` (
  `rowid` integer NULL PRIMARY KEY AUTOINCREMENT,
  `agent_id` text NOT NULL,
  `task_id` text NOT NULL,
  `provider` text NOT NULL,
  `model` text NOT NULL,
  `input_tokens` integer NOT NULL,
  `output_tokens` integer NOT NULL,
  `cost_usd` real NOT NULL,
  `timestamp` text NOT NULL,
  `call_category` text NULL,
  CONSTRAINT `0` FOREIGN KEY (`task_id`) REFERENCES `tasks` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
);
-- Create index "idx_cost_records_agent_id" to table: "cost_records"
CREATE INDEX `idx_cost_records_agent_id` ON `cost_records` (`agent_id`);
-- Create index "idx_cost_records_task_id" to table: "cost_records"
CREATE INDEX `idx_cost_records_task_id` ON `cost_records` (`task_id`);
-- Create "messages" table
CREATE TABLE `messages` (
  `id` text NULL,
  `timestamp` text NOT NULL,
  `sender` text NOT NULL,
  `to` text NOT NULL,
  `type` text NOT NULL,
  `priority` text NOT NULL DEFAULT 'normal',
  `channel` text NOT NULL,
  `content` text NOT NULL,
  `attachments` text NOT NULL DEFAULT '[]',
  `metadata` text NOT NULL DEFAULT '{}',
  PRIMARY KEY (`id`)
);
-- Create index "idx_messages_channel" to table: "messages"
CREATE INDEX `idx_messages_channel` ON `messages` (`channel`);
-- Create index "idx_messages_timestamp" to table: "messages"
CREATE INDEX `idx_messages_timestamp` ON `messages` (`timestamp`);
-- Create "lifecycle_events" table
CREATE TABLE `lifecycle_events` (
  `id` text NULL,
  `agent_id` text NOT NULL,
  `agent_name` text NOT NULL,
  `event_type` text NOT NULL,
  `timestamp` text NOT NULL,
  `initiated_by` text NOT NULL,
  `details` text NOT NULL DEFAULT '',
  `metadata` text NOT NULL DEFAULT '{}',
  PRIMARY KEY (`id`)
);
-- Create index "idx_le_agent_id" to table: "lifecycle_events"
CREATE INDEX `idx_le_agent_id` ON `lifecycle_events` (`agent_id`);
-- Create index "idx_le_event_type" to table: "lifecycle_events"
CREATE INDEX `idx_le_event_type` ON `lifecycle_events` (`event_type`);
-- Create index "idx_le_timestamp" to table: "lifecycle_events"
CREATE INDEX `idx_le_timestamp` ON `lifecycle_events` (`timestamp`);
-- Create "task_metrics" table
CREATE TABLE `task_metrics` (
  `id` text NULL,
  `agent_id` text NOT NULL,
  `task_id` text NOT NULL,
  `task_type` text NOT NULL,
  `completed_at` text NOT NULL,
  `is_success` integer NOT NULL,
  `duration_seconds` real NOT NULL,
  `cost_usd` real NOT NULL,
  `turns_used` integer NOT NULL,
  `tokens_used` integer NOT NULL,
  `quality_score` real NULL,
  `complexity` text NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `0` FOREIGN KEY (`task_id`) REFERENCES `tasks` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
);
-- Create index "idx_tm_agent_id" to table: "task_metrics"
CREATE INDEX `idx_tm_agent_id` ON `task_metrics` (`agent_id`);
-- Create index "idx_tm_completed_at" to table: "task_metrics"
CREATE INDEX `idx_tm_completed_at` ON `task_metrics` (`completed_at`);
-- Create index "idx_tm_agent_completed" to table: "task_metrics"
CREATE INDEX `idx_tm_agent_completed` ON `task_metrics` (`agent_id`, `completed_at`);
-- Create "collaboration_metrics" table
CREATE TABLE `collaboration_metrics` (
  `id` text NULL,
  `agent_id` text NOT NULL,
  `recorded_at` text NOT NULL,
  `delegation_success` integer NULL,
  `delegation_response_seconds` real NULL,
  `conflict_constructiveness` real NULL,
  `meeting_contribution` real NULL,
  `loop_triggered` integer NOT NULL DEFAULT 0,
  `handoff_completeness` real NULL,
  PRIMARY KEY (`id`)
);
-- Create index "idx_cm_agent_id" to table: "collaboration_metrics"
CREATE INDEX `idx_cm_agent_id` ON `collaboration_metrics` (`agent_id`);
-- Create index "idx_cm_recorded_at" to table: "collaboration_metrics"
CREATE INDEX `idx_cm_recorded_at` ON `collaboration_metrics` (`recorded_at`);
-- Create index "idx_cm_agent_recorded" to table: "collaboration_metrics"
CREATE INDEX `idx_cm_agent_recorded` ON `collaboration_metrics` (`agent_id`, `recorded_at`);
-- Create "parked_contexts" table
CREATE TABLE `parked_contexts` (
  `id` text NULL,
  `execution_id` text NOT NULL,
  `agent_id` text NOT NULL,
  `task_id` text NULL,
  `approval_id` text NOT NULL,
  `parked_at` text NOT NULL,
  `context_json` text NOT NULL,
  `metadata` text NOT NULL DEFAULT '{}',
  PRIMARY KEY (`id`)
);
-- Create index "idx_pc_agent_id" to table: "parked_contexts"
CREATE INDEX `idx_pc_agent_id` ON `parked_contexts` (`agent_id`);
-- Create index "idx_pc_approval_id" to table: "parked_contexts"
CREATE INDEX `idx_pc_approval_id` ON `parked_contexts` (`approval_id`);
-- Create "audit_entries" table
CREATE TABLE `audit_entries` (
  `id` text NULL,
  `timestamp` text NOT NULL,
  `agent_id` text NULL,
  `task_id` text NULL,
  `tool_name` text NOT NULL,
  `tool_category` text NOT NULL,
  `action_type` text NOT NULL,
  `arguments_hash` text NOT NULL,
  `verdict` text NOT NULL,
  `risk_level` text NOT NULL,
  `reason` text NOT NULL,
  `matched_rules` text NOT NULL DEFAULT '[]',
  `evaluation_duration_ms` real NOT NULL,
  `approval_id` text NULL,
  PRIMARY KEY (`id`)
);
-- Create index "idx_ae_timestamp" to table: "audit_entries"
CREATE INDEX `idx_ae_timestamp` ON `audit_entries` (`timestamp`);
-- Create index "idx_ae_agent_id" to table: "audit_entries"
CREATE INDEX `idx_ae_agent_id` ON `audit_entries` (`agent_id`);
-- Create index "idx_ae_action_type" to table: "audit_entries"
CREATE INDEX `idx_ae_action_type` ON `audit_entries` (`action_type`);
-- Create index "idx_ae_verdict" to table: "audit_entries"
CREATE INDEX `idx_ae_verdict` ON `audit_entries` (`verdict`);
-- Create index "idx_ae_risk_level" to table: "audit_entries"
CREATE INDEX `idx_ae_risk_level` ON `audit_entries` (`risk_level`);
-- Create "settings" table
CREATE TABLE `settings` (
  `namespace` text NOT NULL,
  `key` text NOT NULL,
  `value` text NOT NULL,
  `updated_at` text NOT NULL,
  PRIMARY KEY (`namespace`, `key`)
);
-- Create "users" table
CREATE TABLE `users` (
  `id` text NULL,
  `username` text NOT NULL,
  `password_hash` text NOT NULL,
  `role` text NOT NULL,
  `must_change_password` integer NOT NULL DEFAULT 1,
  `org_roles` text NOT NULL DEFAULT '[]',
  `scoped_departments` text NOT NULL DEFAULT '[]',
  `created_at` text NOT NULL,
  `updated_at` text NOT NULL,
  PRIMARY KEY (`id`)
);
-- Create index "users_username" to table: "users"
CREATE UNIQUE INDEX `users_username` ON `users` (`username`);
-- Create index "idx_users_role" to table: "users"
CREATE INDEX `idx_users_role` ON `users` (`role`);
-- Create index "idx_single_ceo" to table: "users"
CREATE UNIQUE INDEX `idx_single_ceo` ON `users` (`role`) WHERE role = 'ceo';
-- Create "api_keys" table
CREATE TABLE `api_keys` (
  `id` text NULL,
  `key_hash` text NOT NULL,
  `name` text NOT NULL,
  `role` text NOT NULL,
  `user_id` text NOT NULL,
  `created_at` text NOT NULL,
  `expires_at` text NULL,
  `revoked` integer NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  CONSTRAINT `0` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON UPDATE NO ACTION ON DELETE CASCADE
);
-- Create index "api_keys_key_hash" to table: "api_keys"
CREATE UNIQUE INDEX `api_keys_key_hash` ON `api_keys` (`key_hash`);
-- Create index "idx_api_keys_user_id" to table: "api_keys"
CREATE INDEX `idx_api_keys_user_id` ON `api_keys` (`user_id`);
-- Create "sessions" table
CREATE TABLE `sessions` (
  `session_id` text NULL,
  `user_id` text NOT NULL,
  `username` text NOT NULL,
  `role` text NOT NULL,
  `ip_address` text NOT NULL DEFAULT '',
  `user_agent` text NOT NULL DEFAULT '',
  `created_at` text NOT NULL,
  `last_active_at` text NOT NULL,
  `expires_at` text NOT NULL,
  `revoked` integer NOT NULL DEFAULT 0,
  PRIMARY KEY (`session_id`),
  CONSTRAINT `0` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON UPDATE NO ACTION ON DELETE CASCADE
);
-- Create index "idx_sessions_user_revoked_expires" to table: "sessions"
CREATE INDEX `idx_sessions_user_revoked_expires` ON `sessions` (`user_id`, `revoked`, `expires_at`);
-- Create index "idx_sessions_revoked_expires" to table: "sessions"
CREATE INDEX `idx_sessions_revoked_expires` ON `sessions` (`revoked`, `expires_at`);
-- Create index "idx_sessions_expires_at" to table: "sessions"
CREATE INDEX `idx_sessions_expires_at` ON `sessions` (`expires_at`);
-- Create "checkpoints" table
CREATE TABLE `checkpoints` (
  `id` text NULL,
  `execution_id` text NOT NULL,
  `agent_id` text NOT NULL,
  `task_id` text NOT NULL,
  `turn_number` integer NOT NULL,
  `context_json` text NOT NULL,
  `created_at` text NOT NULL,
  PRIMARY KEY (`id`),
  CHECK (turn_number >= 0)
);
-- Create index "idx_cp_execution_id" to table: "checkpoints"
CREATE INDEX `idx_cp_execution_id` ON `checkpoints` (`execution_id`);
-- Create index "idx_cp_task_id" to table: "checkpoints"
CREATE INDEX `idx_cp_task_id` ON `checkpoints` (`task_id`);
-- Create index "idx_cp_exec_turn" to table: "checkpoints"
CREATE INDEX `idx_cp_exec_turn` ON `checkpoints` (`execution_id`, `turn_number`);
-- Create index "idx_cp_task_turn" to table: "checkpoints"
CREATE INDEX `idx_cp_task_turn` ON `checkpoints` (`task_id`, `turn_number`);
-- Create "heartbeats" table
CREATE TABLE `heartbeats` (
  `execution_id` text NULL,
  `agent_id` text NOT NULL,
  `task_id` text NOT NULL,
  `last_heartbeat_at` text NOT NULL,
  PRIMARY KEY (`execution_id`)
);
-- Create index "idx_hb_last_heartbeat" to table: "heartbeats"
CREATE INDEX `idx_hb_last_heartbeat` ON `heartbeats` (`last_heartbeat_at`);
-- Create "agent_states" table
CREATE TABLE `agent_states` (
  `agent_id` text NULL,
  `execution_id` text NULL,
  `task_id` text NULL,
  `status` text NOT NULL DEFAULT 'idle',
  `turn_count` integer NOT NULL DEFAULT 0,
  `accumulated_cost_usd` real NOT NULL DEFAULT 0.0,
  `last_activity_at` text NOT NULL,
  `started_at` text NULL,
  PRIMARY KEY (`agent_id`),
  CHECK (status IN ('idle', 'executing', 'paused')),
  CHECK (turn_count >= 0),
  CHECK (accumulated_cost_usd >= 0.0),
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
-- Create index "idx_as_status_activity" to table: "agent_states"
CREATE INDEX `idx_as_status_activity` ON `agent_states` (`status`, `last_activity_at` DESC);
-- Create "artifacts" table
CREATE TABLE `artifacts` (
  `id` text NULL,
  `type` text NOT NULL,
  `path` text NOT NULL,
  `task_id` text NOT NULL,
  `created_by` text NOT NULL,
  `description` text NOT NULL DEFAULT '',
  `content_type` text NOT NULL DEFAULT '',
  `size_bytes` integer NOT NULL DEFAULT 0,
  `created_at` text NOT NULL,
  PRIMARY KEY (`id`),
  CHECK (size_bytes >= 0)
);
-- Create index "idx_artifacts_task_id" to table: "artifacts"
CREATE INDEX `idx_artifacts_task_id` ON `artifacts` (`task_id`);
-- Create index "idx_artifacts_created_by" to table: "artifacts"
CREATE INDEX `idx_artifacts_created_by` ON `artifacts` (`created_by`);
-- Create index "idx_artifacts_type" to table: "artifacts"
CREATE INDEX `idx_artifacts_type` ON `artifacts` (`type`);
-- Create "projects" table
CREATE TABLE `projects` (
  `id` text NULL,
  `name` text NOT NULL,
  `description` text NOT NULL DEFAULT '',
  `team` text NOT NULL DEFAULT '[]',
  `lead` text NULL,
  `task_ids` text NOT NULL DEFAULT '[]',
  `deadline` text NULL,
  `budget` real NOT NULL DEFAULT 0.0,
  `status` text NOT NULL DEFAULT 'planning',
  PRIMARY KEY (`id`),
  CHECK (budget >= 0.0)
);
-- Create index "idx_projects_status" to table: "projects"
CREATE INDEX `idx_projects_status` ON `projects` (`status`);
-- Create index "idx_projects_lead" to table: "projects"
CREATE INDEX `idx_projects_lead` ON `projects` (`lead`);
-- Create "project_cost_aggregates" table
CREATE TABLE `project_cost_aggregates` (
  `project_id` text NULL,
  `total_cost` real NOT NULL DEFAULT 0.0,
  `total_input_tokens` integer NOT NULL DEFAULT 0,
  `total_output_tokens` integer NOT NULL DEFAULT 0,
  `record_count` integer NOT NULL DEFAULT 0,
  `last_updated` text NOT NULL,
  PRIMARY KEY (`project_id`),
  CHECK (length(project_id) > 0),
  CHECK (total_cost >= 0.0),
  CHECK (total_input_tokens >= 0),
  CHECK (total_output_tokens >= 0),
  CHECK (record_count >= 0),
  CHECK (
        last_updated LIKE '%+00:00' OR last_updated LIKE '%Z'
    )
);
-- Create "custom_presets" table
CREATE TABLE `custom_presets` (
  `name` text NULL,
  `config_json` text NOT NULL,
  `description` text NOT NULL DEFAULT '',
  `created_at` text NOT NULL,
  `updated_at` text NOT NULL,
  PRIMARY KEY (`name`),
  CHECK (length(name) > 0),
  CHECK (length(config_json) > 0)
);
-- Create "workflow_definitions" table
CREATE TABLE `workflow_definitions` (
  `id` text NOT NULL,
  `name` text NOT NULL,
  `description` text NOT NULL DEFAULT '',
  `workflow_type` text NOT NULL,
  `nodes` text NOT NULL,
  `edges` text NOT NULL,
  `created_by` text NOT NULL,
  `created_at` text NOT NULL,
  `updated_at` text NOT NULL,
  `version` integer NOT NULL DEFAULT 1,
  PRIMARY KEY (`id`),
  CHECK (length(id) > 0),
  CHECK (length(name) > 0),
  CHECK (workflow_type IN (
        'sequential_pipeline', 'parallel_execution', 'kanban', 'agile_kanban'
    )),
  CHECK (length(created_by) > 0),
  CHECK (version >= 1)
);
-- Create index "idx_wd_workflow_type" to table: "workflow_definitions"
CREATE INDEX `idx_wd_workflow_type` ON `workflow_definitions` (`workflow_type`);
-- Create index "idx_wd_updated_at" to table: "workflow_definitions"
CREATE INDEX `idx_wd_updated_at` ON `workflow_definitions` (`updated_at` DESC);
-- Create "workflow_executions" table
CREATE TABLE `workflow_executions` (
  `id` text NOT NULL,
  `definition_id` text NOT NULL,
  `definition_version` integer NOT NULL,
  `status` text NOT NULL,
  `node_executions` text NOT NULL DEFAULT '[]',
  `activated_by` text NOT NULL,
  `project` text NOT NULL,
  `created_at` text NOT NULL,
  `updated_at` text NOT NULL,
  `completed_at` text NULL,
  `error` text NULL,
  `version` integer NOT NULL DEFAULT 1,
  PRIMARY KEY (`id`),
  CONSTRAINT `0` FOREIGN KEY (`definition_id`) REFERENCES `workflow_definitions` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION,
  CHECK (length(id) > 0),
  CHECK (length(definition_id) > 0),
  CHECK (definition_version >= 1),
  CHECK (status IN (
        'pending', 'running', 'completed', 'failed', 'cancelled'
    )),
  CHECK (length(activated_by) > 0),
  CHECK (length(project) > 0),
  CHECK (version >= 1)
);
-- Create index "idx_wfe_definition_id" to table: "workflow_executions"
CREATE INDEX `idx_wfe_definition_id` ON `workflow_executions` (`definition_id`);
-- Create index "idx_wfe_status" to table: "workflow_executions"
CREATE INDEX `idx_wfe_status` ON `workflow_executions` (`status`);
-- Create index "idx_wfe_updated_at" to table: "workflow_executions"
CREATE INDEX `idx_wfe_updated_at` ON `workflow_executions` (`updated_at` DESC);
-- Create index "idx_wfe_definition_updated" to table: "workflow_executions"
CREATE INDEX `idx_wfe_definition_updated` ON `workflow_executions` (`definition_id`, `updated_at` DESC);
-- Create index "idx_wfe_status_updated" to table: "workflow_executions"
CREATE INDEX `idx_wfe_status_updated` ON `workflow_executions` (`status`, `updated_at` DESC);
-- Create index "idx_wfe_project" to table: "workflow_executions"
CREATE INDEX `idx_wfe_project` ON `workflow_executions` (`project`);
-- Create "fine_tune_runs" table
CREATE TABLE `fine_tune_runs` (
  `id` text NOT NULL,
  `stage` text NOT NULL,
  `progress` real NULL,
  `error` text NULL,
  `config_json` text NOT NULL,
  `started_at` text NOT NULL,
  `updated_at` text NOT NULL,
  `completed_at` text NULL,
  `stages_completed` text NOT NULL DEFAULT '[]',
  PRIMARY KEY (`id`),
  CHECK (length(id) > 0),
  CHECK (stage IN ('idle', 'generating_data', 'mining_negatives', 'training', 'evaluating', 'deploying', 'complete', 'failed')),
  CHECK (progress IS NULL OR (progress >= 0.0 AND progress <= 1.0))
);
-- Create index "idx_ftr_stage" to table: "fine_tune_runs"
CREATE INDEX `idx_ftr_stage` ON `fine_tune_runs` (`stage`);
-- Create index "idx_ftr_started_at" to table: "fine_tune_runs"
CREATE INDEX `idx_ftr_started_at` ON `fine_tune_runs` (`started_at` DESC);
-- Create index "idx_ftr_updated_at" to table: "fine_tune_runs"
CREATE INDEX `idx_ftr_updated_at` ON `fine_tune_runs` (`updated_at` DESC);
-- Create "fine_tune_checkpoints" table
CREATE TABLE `fine_tune_checkpoints` (
  `id` text NOT NULL,
  `run_id` text NOT NULL,
  `model_path` text NOT NULL,
  `base_model` text NOT NULL,
  `doc_count` integer NOT NULL,
  `eval_metrics_json` text NULL,
  `size_bytes` integer NOT NULL,
  `created_at` text NOT NULL,
  `is_active` integer NOT NULL DEFAULT 0,
  `backup_config_json` text NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `0` FOREIGN KEY (`run_id`) REFERENCES `fine_tune_runs` (`id`) ON UPDATE NO ACTION ON DELETE CASCADE,
  CHECK (length(id) > 0),
  CHECK (doc_count >= 0),
  CHECK (size_bytes >= 0),
  CHECK (is_active IN (0, 1))
);
-- Create index "idx_ftc_run_id" to table: "fine_tune_checkpoints"
CREATE INDEX `idx_ftc_run_id` ON `fine_tune_checkpoints` (`run_id`);
-- Create index "idx_ftc_active" to table: "fine_tune_checkpoints"
CREATE INDEX `idx_ftc_active` ON `fine_tune_checkpoints` (`is_active`);
-- Create index "idx_ftc_single_active" to table: "fine_tune_checkpoints"
CREATE UNIQUE INDEX `idx_ftc_single_active` ON `fine_tune_checkpoints` (`is_active`) WHERE is_active = 1;
-- Create index "idx_ftc_created_at" to table: "fine_tune_checkpoints"
CREATE INDEX `idx_ftc_created_at` ON `fine_tune_checkpoints` (`created_at` DESC);
-- Create "workflow_definition_versions" table
CREATE TABLE `workflow_definition_versions` (
  `entity_id` text NOT NULL,
  `version` integer NOT NULL,
  `content_hash` text NOT NULL,
  `snapshot` text NOT NULL,
  `saved_by` text NOT NULL,
  `saved_at` text NOT NULL,
  PRIMARY KEY (`entity_id`, `version`),
  CHECK (length(entity_id) > 0),
  CHECK (version >= 1),
  CHECK (length(content_hash) > 0),
  CHECK (length(snapshot) > 0),
  CHECK (length(saved_by) > 0),
  CHECK (
        saved_at LIKE '%+00:00' OR saved_at LIKE '%Z'
    )
);
-- Create index "idx_wdv_entity_saved" to table: "workflow_definition_versions"
CREATE INDEX `idx_wdv_entity_saved` ON `workflow_definition_versions` (`entity_id`, `saved_at` DESC);
-- Create index "idx_wdv_content_hash" to table: "workflow_definition_versions"
CREATE INDEX `idx_wdv_content_hash` ON `workflow_definition_versions` (`entity_id`, `content_hash`);
-- Create "decision_records" table
CREATE TABLE `decision_records` (
  `id` text NULL,
  `task_id` text NOT NULL,
  `approval_id` text NULL,
  `executing_agent_id` text NOT NULL,
  `reviewer_agent_id` text NOT NULL,
  `decision` text NOT NULL,
  `reason` text NULL,
  `criteria_snapshot` text NOT NULL DEFAULT '[]',
  `recorded_at` text NOT NULL,
  `version` integer NOT NULL,
  `metadata` text NOT NULL DEFAULT '{}',
  PRIMARY KEY (`id`),
  CONSTRAINT `0` FOREIGN KEY (`task_id`) REFERENCES `tasks` (`id`) ON UPDATE NO ACTION ON DELETE RESTRICT,
  CHECK (reviewer_agent_id != executing_agent_id),
  CHECK (decision IN (
        'approved', 'rejected', 'auto_approved', 'auto_rejected', 'escalated'
    )),
  CHECK (
        recorded_at LIKE '%+00:00' OR recorded_at LIKE '%Z'
    ),
  CHECK (version >= 1)
);
-- Create index "decision_records_task_id_version" to table: "decision_records"
CREATE UNIQUE INDEX `decision_records_task_id_version` ON `decision_records` (`task_id`, `version`);
-- Create index "idx_dr_executing_agent_recorded" to table: "decision_records"
CREATE INDEX `idx_dr_executing_agent_recorded` ON `decision_records` (`executing_agent_id`, `recorded_at` DESC);
-- Create index "idx_dr_reviewer_agent_recorded" to table: "decision_records"
CREATE INDEX `idx_dr_reviewer_agent_recorded` ON `decision_records` (`reviewer_agent_id`, `recorded_at` DESC);
-- Create "login_attempts" table
CREATE TABLE `login_attempts` (
  `id` integer NULL PRIMARY KEY AUTOINCREMENT,
  `username` text NOT NULL,
  `attempted_at` text NOT NULL,
  `ip_address` text NOT NULL DEFAULT ''
);
-- Create index "idx_la_username_attempted" to table: "login_attempts"
CREATE INDEX `idx_la_username_attempted` ON `login_attempts` (`username`, `attempted_at`);
-- Create index "idx_la_attempted_at" to table: "login_attempts"
CREATE INDEX `idx_la_attempted_at` ON `login_attempts` (`attempted_at`);
-- Create "refresh_tokens" table
CREATE TABLE `refresh_tokens` (
  `token_hash` text NULL,
  `session_id` text NOT NULL,
  `user_id` text NOT NULL,
  `expires_at` text NOT NULL,
  `used` integer NOT NULL DEFAULT 0,
  `created_at` text NOT NULL,
  PRIMARY KEY (`token_hash`),
  CONSTRAINT `0` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON UPDATE NO ACTION ON DELETE CASCADE,
  CONSTRAINT `1` FOREIGN KEY (`session_id`) REFERENCES `sessions` (`session_id`) ON UPDATE NO ACTION ON DELETE CASCADE,
  CHECK (used IN (0, 1))
);
-- Create index "idx_rt_user_id" to table: "refresh_tokens"
CREATE INDEX `idx_rt_user_id` ON `refresh_tokens` (`user_id`);
-- Create index "idx_rt_session_id" to table: "refresh_tokens"
CREATE INDEX `idx_rt_session_id` ON `refresh_tokens` (`session_id`);
-- Create index "idx_rt_expires_at" to table: "refresh_tokens"
CREATE INDEX `idx_rt_expires_at` ON `refresh_tokens` (`expires_at`);
-- Create "risk_overrides" table
CREATE TABLE `risk_overrides` (
  `id` text NULL,
  `action_type` text NOT NULL,
  `original_tier` text NOT NULL,
  `override_tier` text NOT NULL,
  `reason` text NOT NULL,
  `created_by` text NOT NULL,
  `created_at` text NOT NULL,
  `expires_at` text NOT NULL,
  `revoked_at` text NULL,
  `revoked_by` text NULL,
  PRIMARY KEY (`id`),
  CHECK (
        (revoked_at IS NULL AND revoked_by IS NULL)
        OR
        (revoked_at IS NOT NULL AND revoked_by IS NOT NULL)
    )
);
-- Create index "idx_ro_action_type" to table: "risk_overrides"
CREATE INDEX `idx_ro_action_type` ON `risk_overrides` (`action_type`);
-- Create index "idx_ro_active" to table: "risk_overrides"
CREATE INDEX `idx_ro_active` ON `risk_overrides` (`created_at` DESC, `expires_at`) WHERE revoked_at IS NULL;
-- Create "ssrf_violations" table
CREATE TABLE `ssrf_violations` (
  `id` text NULL,
  `timestamp` text NOT NULL,
  `url` text NOT NULL,
  `hostname` text NOT NULL,
  `port` integer NOT NULL,
  `resolved_ip` text NULL,
  `blocked_range` text NULL,
  `provider_name` text NULL,
  `status` text NOT NULL DEFAULT 'pending',
  `resolved_by` text NULL,
  `resolved_at` text NULL,
  PRIMARY KEY (`id`),
  CHECK (port BETWEEN 1 AND 65535),
  CHECK (status IN ('pending', 'allowed', 'denied')),
  CHECK (
        (status = 'pending' AND resolved_by IS NULL AND resolved_at IS NULL)
        OR
        (status IN ('allowed', 'denied')
         AND resolved_by IS NOT NULL
         AND resolved_at IS NOT NULL)
    )
);
-- Create index "idx_sv_status_timestamp" to table: "ssrf_violations"
CREATE INDEX `idx_sv_status_timestamp` ON `ssrf_violations` (`status`, `timestamp` DESC);
-- Create index "idx_sv_timestamp" to table: "ssrf_violations"
CREATE INDEX `idx_sv_timestamp` ON `ssrf_violations` (`timestamp`);
-- Create index "idx_sv_hostname" to table: "ssrf_violations"
CREATE INDEX `idx_sv_hostname` ON `ssrf_violations` (`hostname`, `port`);
-- Create "agent_identity_versions" table
CREATE TABLE `agent_identity_versions` (
  `entity_id` text NOT NULL,
  `version` integer NOT NULL,
  `content_hash` text NOT NULL,
  `snapshot` text NOT NULL,
  `saved_by` text NOT NULL,
  `saved_at` text NOT NULL,
  PRIMARY KEY (`entity_id`, `version`),
  CHECK (length(entity_id) > 0),
  CHECK (version >= 1),
  CHECK (length(content_hash) > 0),
  CHECK (length(snapshot) > 0),
  CHECK (length(saved_by) > 0),
  CHECK (
        saved_at LIKE '%+00:00' OR saved_at LIKE '%Z'
    )
);
-- Create index "idx_aiv_entity_saved" to table: "agent_identity_versions"
CREATE INDEX `idx_aiv_entity_saved` ON `agent_identity_versions` (`entity_id`, `saved_at` DESC);
-- Create index "idx_aiv_content_hash" to table: "agent_identity_versions"
CREATE INDEX `idx_aiv_content_hash` ON `agent_identity_versions` (`entity_id`, `content_hash`);
-- Create "evaluation_config_versions" table
CREATE TABLE `evaluation_config_versions` (
  `entity_id` text NOT NULL,
  `version` integer NOT NULL,
  `content_hash` text NOT NULL,
  `snapshot` text NOT NULL,
  `saved_by` text NOT NULL,
  `saved_at` text NOT NULL,
  PRIMARY KEY (`entity_id`, `version`),
  CHECK (length(entity_id) > 0),
  CHECK (version >= 1),
  CHECK (length(content_hash) > 0),
  CHECK (length(snapshot) > 0),
  CHECK (length(saved_by) > 0),
  CHECK (
        saved_at LIKE '%+00:00' OR saved_at LIKE '%Z'
    )
);
-- Create index "idx_ecv_entity_saved" to table: "evaluation_config_versions"
CREATE INDEX `idx_ecv_entity_saved` ON `evaluation_config_versions` (`entity_id`, `saved_at` DESC);
-- Create index "idx_ecv_content_hash" to table: "evaluation_config_versions"
CREATE INDEX `idx_ecv_content_hash` ON `evaluation_config_versions` (`entity_id`, `content_hash`);
-- Create "budget_config_versions" table
CREATE TABLE `budget_config_versions` (
  `entity_id` text NOT NULL,
  `version` integer NOT NULL,
  `content_hash` text NOT NULL,
  `snapshot` text NOT NULL,
  `saved_by` text NOT NULL,
  `saved_at` text NOT NULL,
  PRIMARY KEY (`entity_id`, `version`),
  CHECK (length(entity_id) > 0),
  CHECK (version >= 1),
  CHECK (length(content_hash) > 0),
  CHECK (length(snapshot) > 0),
  CHECK (length(saved_by) > 0),
  CHECK (
        saved_at LIKE '%+00:00' OR saved_at LIKE '%Z'
    )
);
-- Create index "idx_bcv_entity_saved" to table: "budget_config_versions"
CREATE INDEX `idx_bcv_entity_saved` ON `budget_config_versions` (`entity_id`, `saved_at` DESC);
-- Create index "idx_bcv_content_hash" to table: "budget_config_versions"
CREATE INDEX `idx_bcv_content_hash` ON `budget_config_versions` (`entity_id`, `content_hash`);
-- Create "company_versions" table
CREATE TABLE `company_versions` (
  `entity_id` text NOT NULL,
  `version` integer NOT NULL,
  `content_hash` text NOT NULL,
  `snapshot` text NOT NULL,
  `saved_by` text NOT NULL,
  `saved_at` text NOT NULL,
  PRIMARY KEY (`entity_id`, `version`),
  CHECK (length(entity_id) > 0),
  CHECK (version >= 1),
  CHECK (length(content_hash) > 0),
  CHECK (length(snapshot) > 0),
  CHECK (length(saved_by) > 0),
  CHECK (
        saved_at LIKE '%+00:00' OR saved_at LIKE '%Z'
    )
);
-- Create index "idx_cv_entity_saved" to table: "company_versions"
CREATE INDEX `idx_cv_entity_saved` ON `company_versions` (`entity_id`, `saved_at` DESC);
-- Create index "idx_cv_content_hash" to table: "company_versions"
CREATE INDEX `idx_cv_content_hash` ON `company_versions` (`entity_id`, `content_hash`);
-- Create "role_versions" table
CREATE TABLE `role_versions` (
  `entity_id` text NOT NULL,
  `version` integer NOT NULL,
  `content_hash` text NOT NULL,
  `snapshot` text NOT NULL,
  `saved_by` text NOT NULL,
  `saved_at` text NOT NULL,
  PRIMARY KEY (`entity_id`, `version`),
  CHECK (length(entity_id) > 0),
  CHECK (version >= 1),
  CHECK (length(content_hash) > 0),
  CHECK (length(snapshot) > 0),
  CHECK (length(saved_by) > 0),
  CHECK (
        saved_at LIKE '%+00:00' OR saved_at LIKE '%Z'
    )
);
-- Create index "idx_rv_entity_saved" to table: "role_versions"
CREATE INDEX `idx_rv_entity_saved` ON `role_versions` (`entity_id`, `saved_at` DESC);
-- Create index "idx_rv_content_hash" to table: "role_versions"
CREATE INDEX `idx_rv_content_hash` ON `role_versions` (`entity_id`, `content_hash`);
-- Create "circuit_breaker_state" table
CREATE TABLE `circuit_breaker_state` (
  `pair_key_a` text NOT NULL,
  `pair_key_b` text NOT NULL,
  `bounce_count` integer NOT NULL DEFAULT 0,
  `trip_count` integer NOT NULL DEFAULT 0,
  `opened_at` real NULL,
  PRIMARY KEY (`pair_key_a`, `pair_key_b`),
  CHECK (length(pair_key_a) > 0),
  CHECK (length(pair_key_b) > 0),
  CHECK (bounce_count >= 0),
  CHECK (trip_count >= 0)
);
-- Create "entity_definitions" table
CREATE TABLE `entity_definitions` (
  `name` text NULL,
  `tier` text NOT NULL,
  `source` text NOT NULL,
  `definition` text NOT NULL DEFAULT '',
  `fields` text NOT NULL DEFAULT '[]',
  `constraints` text NOT NULL DEFAULT '[]',
  `disambiguation` text NOT NULL DEFAULT '',
  `relationships` text NOT NULL DEFAULT '[]',
  `created_by` text NOT NULL,
  `created_at` text NOT NULL,
  `updated_at` text NOT NULL,
  PRIMARY KEY (`name`),
  CHECK (length(name) > 0),
  CHECK (tier IN ('core', 'user')),
  CHECK (source IN ('auto', 'config', 'api')),
  CHECK (length(created_by) > 0)
);
-- Create index "idx_ed_tier" to table: "entity_definitions"
CREATE INDEX `idx_ed_tier` ON `entity_definitions` (`tier`);
-- Create "entity_definition_versions" table
CREATE TABLE `entity_definition_versions` (
  `entity_id` text NOT NULL,
  `version` integer NOT NULL,
  `content_hash` text NOT NULL,
  `snapshot` text NOT NULL,
  `saved_by` text NOT NULL,
  `saved_at` text NOT NULL,
  PRIMARY KEY (`entity_id`, `version`),
  CHECK (length(entity_id) > 0),
  CHECK (version >= 1),
  CHECK (length(content_hash) > 0),
  CHECK (length(snapshot) > 0),
  CHECK (length(saved_by) > 0),
  CHECK (
        saved_at LIKE '%+00:00' OR saved_at LIKE '%Z'
    )
);
-- Create index "idx_edv_entity_saved" to table: "entity_definition_versions"
CREATE INDEX `idx_edv_entity_saved` ON `entity_definition_versions` (`entity_id`, `saved_at` DESC);
-- Create index "idx_edv_content_hash" to table: "entity_definition_versions"
CREATE INDEX `idx_edv_content_hash` ON `entity_definition_versions` (`entity_id`, `content_hash`);
