-- Create "heartbeats" table
CREATE TABLE "heartbeats" (
  "execution_id" text NOT NULL,
  "agent_id" text NOT NULL,
  "task_id" text NOT NULL,
  "last_heartbeat_at" timestamptz NOT NULL,
  PRIMARY KEY ("execution_id")
);
-- Create index "idx_hb_last_heartbeat" to table: "heartbeats"
CREATE INDEX "idx_hb_last_heartbeat" ON "heartbeats" ("last_heartbeat_at");
-- Create "entity_definition_versions" table
CREATE TABLE "entity_definition_versions" (
  "entity_id" text NOT NULL,
  "version" bigint NOT NULL,
  "content_hash" text NOT NULL,
  "snapshot" jsonb NOT NULL,
  "saved_by" text NOT NULL,
  "saved_at" timestamptz NOT NULL,
  PRIMARY KEY ("entity_id", "version"),
  CONSTRAINT "entity_definition_versions_content_hash_check" CHECK (length(content_hash) > 0),
  CONSTRAINT "entity_definition_versions_entity_id_check" CHECK (length(entity_id) > 0),
  CONSTRAINT "entity_definition_versions_saved_by_check" CHECK (length(saved_by) > 0),
  CONSTRAINT "entity_definition_versions_version_check" CHECK (version >= 1)
);
-- Create index "idx_edv_content_hash" to table: "entity_definition_versions"
CREATE INDEX "idx_edv_content_hash" ON "entity_definition_versions" ("entity_id", "content_hash");
-- Create index "idx_edv_entity_saved" to table: "entity_definition_versions"
CREATE INDEX "idx_edv_entity_saved" ON "entity_definition_versions" ("entity_id", "saved_at" DESC);
-- Create "role_versions" table
CREATE TABLE "role_versions" (
  "entity_id" text NOT NULL,
  "version" bigint NOT NULL,
  "content_hash" text NOT NULL,
  "snapshot" jsonb NOT NULL,
  "saved_by" text NOT NULL,
  "saved_at" timestamptz NOT NULL,
  PRIMARY KEY ("entity_id", "version"),
  CONSTRAINT "role_versions_content_hash_check" CHECK (length(content_hash) > 0),
  CONSTRAINT "role_versions_entity_id_check" CHECK (length(entity_id) > 0),
  CONSTRAINT "role_versions_saved_by_check" CHECK (length(saved_by) > 0),
  CONSTRAINT "role_versions_version_check" CHECK (version >= 1)
);
-- Create index "idx_rv_content_hash" to table: "role_versions"
CREATE INDEX "idx_rv_content_hash" ON "role_versions" ("entity_id", "content_hash");
-- Create index "idx_rv_entity_saved" to table: "role_versions"
CREATE INDEX "idx_rv_entity_saved" ON "role_versions" ("entity_id", "saved_at" DESC);
-- Create "artifacts" table
CREATE TABLE "artifacts" (
  "id" text NOT NULL,
  "type" text NOT NULL,
  "path" text NOT NULL,
  "task_id" text NOT NULL,
  "created_by" text NOT NULL,
  "description" text NOT NULL DEFAULT '',
  "content_type" text NOT NULL DEFAULT '',
  "size_bytes" bigint NOT NULL DEFAULT 0,
  "created_at" timestamptz NOT NULL,
  PRIMARY KEY ("id"),
  CONSTRAINT "artifacts_size_bytes_check" CHECK (size_bytes >= 0)
);
-- Create index "idx_artifacts_created_by" to table: "artifacts"
CREATE INDEX "idx_artifacts_created_by" ON "artifacts" ("created_by");
-- Create index "idx_artifacts_task_id" to table: "artifacts"
CREATE INDEX "idx_artifacts_task_id" ON "artifacts" ("task_id");
-- Create index "idx_artifacts_type" to table: "artifacts"
CREATE INDEX "idx_artifacts_type" ON "artifacts" ("type");
-- Create "audit_entries" table
CREATE TABLE "audit_entries" (
  "id" text NOT NULL,
  "timestamp" timestamptz NOT NULL,
  "agent_id" text NULL,
  "task_id" text NULL,
  "tool_name" text NOT NULL,
  "tool_category" text NOT NULL,
  "action_type" text NOT NULL,
  "arguments_hash" text NOT NULL,
  "verdict" text NOT NULL,
  "risk_level" text NOT NULL,
  "reason" text NOT NULL,
  "matched_rules" jsonb NOT NULL DEFAULT '[]',
  "evaluation_duration_ms" double precision NOT NULL,
  "approval_id" text NULL,
  PRIMARY KEY ("id")
);
-- Create index "idx_ae_action_type" to table: "audit_entries"
CREATE INDEX "idx_ae_action_type" ON "audit_entries" ("action_type");
-- Create index "idx_ae_agent_id" to table: "audit_entries"
CREATE INDEX "idx_ae_agent_id" ON "audit_entries" ("agent_id");
-- Create index "idx_ae_matched_rules_gin" to table: "audit_entries"
CREATE INDEX "idx_ae_matched_rules_gin" ON "audit_entries" USING GIN ("matched_rules");
-- Create index "idx_ae_risk_level" to table: "audit_entries"
CREATE INDEX "idx_ae_risk_level" ON "audit_entries" ("risk_level");
-- Create index "idx_ae_timestamp" to table: "audit_entries"
CREATE INDEX "idx_ae_timestamp" ON "audit_entries" ("timestamp");
-- Create index "idx_ae_verdict" to table: "audit_entries"
CREATE INDEX "idx_ae_verdict" ON "audit_entries" ("verdict");
-- Create "login_attempts" table
CREATE TABLE "login_attempts" (
  "id" bigint NOT NULL GENERATED ALWAYS AS IDENTITY,
  "username" text NOT NULL,
  "attempted_at" timestamptz NOT NULL,
  "ip_address" text NOT NULL DEFAULT '',
  PRIMARY KEY ("id")
);
-- Create index "idx_la_attempted_at" to table: "login_attempts"
CREATE INDEX "idx_la_attempted_at" ON "login_attempts" ("attempted_at");
-- Create index "idx_la_username_attempted" to table: "login_attempts"
CREATE INDEX "idx_la_username_attempted" ON "login_attempts" ("username", "attempted_at");
-- Create "checkpoints" table
CREATE TABLE "checkpoints" (
  "id" text NOT NULL,
  "execution_id" text NOT NULL,
  "agent_id" text NOT NULL,
  "task_id" text NOT NULL,
  "turn_number" bigint NOT NULL,
  "context_json" jsonb NOT NULL,
  "created_at" timestamptz NOT NULL,
  PRIMARY KEY ("id"),
  CONSTRAINT "checkpoints_turn_number_check" CHECK (turn_number >= 0)
);
-- Create index "idx_cp_exec_turn" to table: "checkpoints"
CREATE INDEX "idx_cp_exec_turn" ON "checkpoints" ("execution_id", "turn_number");
-- Create index "idx_cp_execution_id" to table: "checkpoints"
CREATE INDEX "idx_cp_execution_id" ON "checkpoints" ("execution_id");
-- Create index "idx_cp_task_id" to table: "checkpoints"
CREATE INDEX "idx_cp_task_id" ON "checkpoints" ("task_id");
-- Create index "idx_cp_task_turn" to table: "checkpoints"
CREATE INDEX "idx_cp_task_turn" ON "checkpoints" ("task_id", "turn_number");
-- Create "circuit_breaker_state" table
CREATE TABLE "circuit_breaker_state" (
  "pair_key_a" text NOT NULL,
  "pair_key_b" text NOT NULL,
  "bounce_count" bigint NOT NULL DEFAULT 0,
  "trip_count" bigint NOT NULL DEFAULT 0,
  "opened_at" double precision NULL,
  PRIMARY KEY ("pair_key_a", "pair_key_b"),
  CONSTRAINT "circuit_breaker_state_bounce_count_check" CHECK (bounce_count >= 0),
  CONSTRAINT "circuit_breaker_state_pair_key_a_check" CHECK (length(pair_key_a) > 0),
  CONSTRAINT "circuit_breaker_state_pair_key_b_check" CHECK (length(pair_key_b) > 0),
  CONSTRAINT "circuit_breaker_state_trip_count_check" CHECK (trip_count >= 0)
);
-- Create "collaboration_metrics" table
CREATE TABLE "collaboration_metrics" (
  "id" text NOT NULL,
  "agent_id" text NOT NULL,
  "recorded_at" timestamptz NOT NULL,
  "delegation_success" boolean NULL,
  "delegation_response_seconds" double precision NULL,
  "conflict_constructiveness" double precision NULL,
  "meeting_contribution" double precision NULL,
  "loop_triggered" boolean NOT NULL DEFAULT false,
  "handoff_completeness" double precision NULL,
  PRIMARY KEY ("id")
);
-- Create index "idx_cm_agent_id" to table: "collaboration_metrics"
CREATE INDEX "idx_cm_agent_id" ON "collaboration_metrics" ("agent_id");
-- Create index "idx_cm_agent_recorded" to table: "collaboration_metrics"
CREATE INDEX "idx_cm_agent_recorded" ON "collaboration_metrics" ("agent_id", "recorded_at");
-- Create index "idx_cm_recorded_at" to table: "collaboration_metrics"
CREATE INDEX "idx_cm_recorded_at" ON "collaboration_metrics" ("recorded_at");
-- Create "company_versions" table
CREATE TABLE "company_versions" (
  "entity_id" text NOT NULL,
  "version" bigint NOT NULL,
  "content_hash" text NOT NULL,
  "snapshot" jsonb NOT NULL,
  "saved_by" text NOT NULL,
  "saved_at" timestamptz NOT NULL,
  PRIMARY KEY ("entity_id", "version"),
  CONSTRAINT "company_versions_content_hash_check" CHECK (length(content_hash) > 0),
  CONSTRAINT "company_versions_entity_id_check" CHECK (length(entity_id) > 0),
  CONSTRAINT "company_versions_saved_by_check" CHECK (length(saved_by) > 0),
  CONSTRAINT "company_versions_version_check" CHECK (version >= 1)
);
-- Create index "idx_cv_content_hash" to table: "company_versions"
CREATE INDEX "idx_cv_content_hash" ON "company_versions" ("entity_id", "content_hash");
-- Create index "idx_cv_entity_saved" to table: "company_versions"
CREATE INDEX "idx_cv_entity_saved" ON "company_versions" ("entity_id", "saved_at" DESC);
-- Create "agent_identity_versions" table
CREATE TABLE "agent_identity_versions" (
  "entity_id" text NOT NULL,
  "version" bigint NOT NULL,
  "content_hash" text NOT NULL,
  "snapshot" jsonb NOT NULL,
  "saved_by" text NOT NULL,
  "saved_at" timestamptz NOT NULL,
  PRIMARY KEY ("entity_id", "version"),
  CONSTRAINT "agent_identity_versions_content_hash_check" CHECK (length(content_hash) > 0),
  CONSTRAINT "agent_identity_versions_entity_id_check" CHECK (length(entity_id) > 0),
  CONSTRAINT "agent_identity_versions_saved_by_check" CHECK (length(saved_by) > 0),
  CONSTRAINT "agent_identity_versions_version_check" CHECK (version >= 1)
);
-- Create index "idx_aiv_content_hash" to table: "agent_identity_versions"
CREATE INDEX "idx_aiv_content_hash" ON "agent_identity_versions" ("entity_id", "content_hash");
-- Create index "idx_aiv_entity_saved" to table: "agent_identity_versions"
CREATE INDEX "idx_aiv_entity_saved" ON "agent_identity_versions" ("entity_id", "saved_at" DESC);
-- Create "custom_presets" table
CREATE TABLE "custom_presets" (
  "name" text NOT NULL,
  "config_json" jsonb NOT NULL,
  "description" text NOT NULL DEFAULT '',
  "created_at" timestamptz NOT NULL,
  "updated_at" timestamptz NOT NULL,
  PRIMARY KEY ("name"),
  CONSTRAINT "custom_presets_name_check" CHECK (length(name) > 0)
);
-- Create "workflow_definition_versions" table
CREATE TABLE "workflow_definition_versions" (
  "entity_id" text NOT NULL,
  "version" bigint NOT NULL,
  "content_hash" text NOT NULL,
  "snapshot" jsonb NOT NULL,
  "saved_by" text NOT NULL,
  "saved_at" timestamptz NOT NULL,
  PRIMARY KEY ("entity_id", "version"),
  CONSTRAINT "workflow_definition_versions_content_hash_check" CHECK (length(content_hash) > 0),
  CONSTRAINT "workflow_definition_versions_entity_id_check" CHECK (length(entity_id) > 0),
  CONSTRAINT "workflow_definition_versions_saved_by_check" CHECK (length(saved_by) > 0),
  CONSTRAINT "workflow_definition_versions_version_check" CHECK (version >= 1)
);
-- Create index "idx_wdv_content_hash" to table: "workflow_definition_versions"
CREATE INDEX "idx_wdv_content_hash" ON "workflow_definition_versions" ("entity_id", "content_hash");
-- Create index "idx_wdv_entity_saved" to table: "workflow_definition_versions"
CREATE INDEX "idx_wdv_entity_saved" ON "workflow_definition_versions" ("entity_id", "saved_at" DESC);
-- Create "settings" table
CREATE TABLE "settings" (
  "namespace" text NOT NULL,
  "key" text NOT NULL,
  "value" text NOT NULL,
  "updated_at" timestamptz NOT NULL,
  PRIMARY KEY ("namespace", "key")
);
-- Create "entity_definitions" table
CREATE TABLE "entity_definitions" (
  "name" text NOT NULL,
  "tier" text NOT NULL,
  "source" text NOT NULL,
  "definition" text NOT NULL DEFAULT '',
  "fields" jsonb NOT NULL DEFAULT '[]',
  "constraints" jsonb NOT NULL DEFAULT '[]',
  "disambiguation" text NOT NULL DEFAULT '',
  "relationships" jsonb NOT NULL DEFAULT '[]',
  "created_by" text NOT NULL,
  "created_at" timestamptz NOT NULL,
  "updated_at" timestamptz NOT NULL,
  PRIMARY KEY ("name"),
  CONSTRAINT "entity_definitions_created_by_check" CHECK (length(created_by) > 0),
  CONSTRAINT "entity_definitions_name_check" CHECK (length(name) > 0),
  CONSTRAINT "entity_definitions_source_check" CHECK (source = ANY (ARRAY['auto'::text, 'config'::text, 'api'::text])),
  CONSTRAINT "entity_definitions_tier_check" CHECK (tier = ANY (ARRAY['core'::text, 'user'::text]))
);
-- Create index "idx_ed_tier" to table: "entity_definitions"
CREATE INDEX "idx_ed_tier" ON "entity_definitions" ("tier");
-- Create "evaluation_config_versions" table
CREATE TABLE "evaluation_config_versions" (
  "entity_id" text NOT NULL,
  "version" bigint NOT NULL,
  "content_hash" text NOT NULL,
  "snapshot" jsonb NOT NULL,
  "saved_by" text NOT NULL,
  "saved_at" timestamptz NOT NULL,
  PRIMARY KEY ("entity_id", "version"),
  CONSTRAINT "evaluation_config_versions_content_hash_check" CHECK (length(content_hash) > 0),
  CONSTRAINT "evaluation_config_versions_entity_id_check" CHECK (length(entity_id) > 0),
  CONSTRAINT "evaluation_config_versions_saved_by_check" CHECK (length(saved_by) > 0),
  CONSTRAINT "evaluation_config_versions_version_check" CHECK (version >= 1)
);
-- Create index "idx_ecv_content_hash" to table: "evaluation_config_versions"
CREATE INDEX "idx_ecv_content_hash" ON "evaluation_config_versions" ("entity_id", "content_hash");
-- Create index "idx_ecv_entity_saved" to table: "evaluation_config_versions"
CREATE INDEX "idx_ecv_entity_saved" ON "evaluation_config_versions" ("entity_id", "saved_at" DESC);
-- Create "users" table
CREATE TABLE "users" (
  "id" text NOT NULL,
  "username" text NOT NULL,
  "password_hash" text NOT NULL,
  "role" text NOT NULL,
  "must_change_password" boolean NOT NULL DEFAULT true,
  "org_roles" jsonb NOT NULL DEFAULT '[]',
  "scoped_departments" jsonb NOT NULL DEFAULT '[]',
  "created_at" timestamptz NOT NULL,
  "updated_at" timestamptz NOT NULL,
  PRIMARY KEY ("id"),
  CONSTRAINT "users_username_key" UNIQUE ("username")
);
-- Create index "idx_single_ceo" to table: "users"
CREATE UNIQUE INDEX "idx_single_ceo" ON "users" ("role") WHERE (role = 'ceo'::text);
-- Create index "idx_users_role" to table: "users"
CREATE INDEX "idx_users_role" ON "users" ("role");
-- Create "risk_overrides" table
CREATE TABLE "risk_overrides" (
  "id" text NOT NULL,
  "action_type" text NOT NULL,
  "original_tier" text NOT NULL,
  "override_tier" text NOT NULL,
  "reason" text NOT NULL,
  "created_by" text NOT NULL,
  "created_at" timestamptz NOT NULL,
  "expires_at" timestamptz NOT NULL,
  "revoked_at" timestamptz NULL,
  "revoked_by" text NULL,
  PRIMARY KEY ("id"),
  CONSTRAINT "risk_overrides_check" CHECK (((revoked_at IS NULL) AND (revoked_by IS NULL)) OR ((revoked_at IS NOT NULL) AND (revoked_by IS NOT NULL)))
);
-- Create index "idx_ro_action_type" to table: "risk_overrides"
CREATE INDEX "idx_ro_action_type" ON "risk_overrides" ("action_type");
-- Create index "idx_ro_active" to table: "risk_overrides"
CREATE INDEX "idx_ro_active" ON "risk_overrides" ("created_at" DESC, "expires_at") WHERE (revoked_at IS NULL);
-- Create "agent_states" table
CREATE TABLE "agent_states" (
  "agent_id" text NOT NULL,
  "execution_id" text NULL,
  "task_id" text NULL,
  "status" text NOT NULL DEFAULT 'idle',
  "turn_count" bigint NOT NULL DEFAULT 0,
  "accumulated_cost_usd" double precision NOT NULL DEFAULT 0.0,
  "last_activity_at" timestamptz NOT NULL,
  "started_at" timestamptz NULL,
  PRIMARY KEY ("agent_id"),
  CONSTRAINT "agent_states_accumulated_cost_usd_check" CHECK (accumulated_cost_usd >= (0.0)::double precision),
  CONSTRAINT "agent_states_check" CHECK (((status = 'idle'::text) AND (execution_id IS NULL) AND (task_id IS NULL) AND (started_at IS NULL) AND (turn_count = 0) AND (accumulated_cost_usd = (0.0)::double precision)) OR ((status = ANY (ARRAY['executing'::text, 'paused'::text])) AND (execution_id IS NOT NULL) AND (started_at IS NOT NULL))),
  CONSTRAINT "agent_states_status_check" CHECK (status = ANY (ARRAY['idle'::text, 'executing'::text, 'paused'::text])),
  CONSTRAINT "agent_states_turn_count_check" CHECK (turn_count >= 0)
);
-- Create index "idx_as_status_activity" to table: "agent_states"
CREATE INDEX "idx_as_status_activity" ON "agent_states" ("status", "last_activity_at" DESC);
-- Create "lifecycle_events" table
CREATE TABLE "lifecycle_events" (
  "id" text NOT NULL,
  "agent_id" text NOT NULL,
  "agent_name" text NOT NULL,
  "event_type" text NOT NULL,
  "timestamp" timestamptz NOT NULL,
  "initiated_by" text NOT NULL,
  "details" text NOT NULL DEFAULT '',
  "metadata" jsonb NOT NULL DEFAULT '{}',
  PRIMARY KEY ("id")
);
-- Create index "idx_le_agent_id" to table: "lifecycle_events"
CREATE INDEX "idx_le_agent_id" ON "lifecycle_events" ("agent_id");
-- Create index "idx_le_event_type" to table: "lifecycle_events"
CREATE INDEX "idx_le_event_type" ON "lifecycle_events" ("event_type");
-- Create index "idx_le_metadata_gin" to table: "lifecycle_events"
CREATE INDEX "idx_le_metadata_gin" ON "lifecycle_events" USING GIN ("metadata");
-- Create index "idx_le_timestamp" to table: "lifecycle_events"
CREATE INDEX "idx_le_timestamp" ON "lifecycle_events" ("timestamp");
-- Create "budget_config_versions" table
CREATE TABLE "budget_config_versions" (
  "entity_id" text NOT NULL,
  "version" bigint NOT NULL,
  "content_hash" text NOT NULL,
  "snapshot" jsonb NOT NULL,
  "saved_by" text NOT NULL,
  "saved_at" timestamptz NOT NULL,
  PRIMARY KEY ("entity_id", "version"),
  CONSTRAINT "budget_config_versions_content_hash_check" CHECK (length(content_hash) > 0),
  CONSTRAINT "budget_config_versions_entity_id_check" CHECK (length(entity_id) > 0),
  CONSTRAINT "budget_config_versions_saved_by_check" CHECK (length(saved_by) > 0),
  CONSTRAINT "budget_config_versions_version_check" CHECK (version >= 1)
);
-- Create index "idx_bcv_content_hash" to table: "budget_config_versions"
CREATE INDEX "idx_bcv_content_hash" ON "budget_config_versions" ("entity_id", "content_hash");
-- Create index "idx_bcv_entity_saved" to table: "budget_config_versions"
CREATE INDEX "idx_bcv_entity_saved" ON "budget_config_versions" ("entity_id", "saved_at" DESC);
-- Create "messages" table
CREATE TABLE "messages" (
  "id" text NOT NULL,
  "timestamp" timestamptz NOT NULL,
  "sender" text NOT NULL,
  "to" text NOT NULL,
  "type" text NOT NULL,
  "priority" text NOT NULL DEFAULT 'normal',
  "channel" text NOT NULL,
  "content" text NOT NULL,
  "attachments" jsonb NOT NULL DEFAULT '[]',
  "metadata" jsonb NOT NULL DEFAULT '{}',
  PRIMARY KEY ("id")
);
-- Create index "idx_messages_channel" to table: "messages"
CREATE INDEX "idx_messages_channel" ON "messages" ("channel");
-- Create index "idx_messages_metadata_gin" to table: "messages"
CREATE INDEX "idx_messages_metadata_gin" ON "messages" USING GIN ("metadata");
-- Create index "idx_messages_timestamp" to table: "messages"
CREATE INDEX "idx_messages_timestamp" ON "messages" ("timestamp");
-- Create "parked_contexts" table
CREATE TABLE "parked_contexts" (
  "id" text NOT NULL,
  "execution_id" text NOT NULL,
  "agent_id" text NOT NULL,
  "task_id" text NULL,
  "approval_id" text NOT NULL,
  "parked_at" timestamptz NOT NULL,
  "context_json" jsonb NOT NULL,
  "metadata" jsonb NOT NULL DEFAULT '{}',
  PRIMARY KEY ("id")
);
-- Create index "idx_pc_agent_id" to table: "parked_contexts"
CREATE INDEX "idx_pc_agent_id" ON "parked_contexts" ("agent_id");
-- Create index "idx_pc_approval_id" to table: "parked_contexts"
CREATE INDEX "idx_pc_approval_id" ON "parked_contexts" ("approval_id");
-- Create "project_cost_aggregates" table
CREATE TABLE "project_cost_aggregates" (
  "project_id" text NOT NULL,
  "total_cost" double precision NOT NULL DEFAULT 0.0,
  "total_input_tokens" bigint NOT NULL DEFAULT 0,
  "total_output_tokens" bigint NOT NULL DEFAULT 0,
  "record_count" bigint NOT NULL DEFAULT 0,
  "last_updated" timestamptz NOT NULL,
  PRIMARY KEY ("project_id"),
  CONSTRAINT "project_cost_aggregates_project_id_check" CHECK (length(project_id) > 0),
  CONSTRAINT "project_cost_aggregates_record_count_check" CHECK (record_count >= 0),
  CONSTRAINT "project_cost_aggregates_total_cost_check" CHECK (total_cost >= (0.0)::double precision),
  CONSTRAINT "project_cost_aggregates_total_input_tokens_check" CHECK (total_input_tokens >= 0),
  CONSTRAINT "project_cost_aggregates_total_output_tokens_check" CHECK (total_output_tokens >= 0)
);
-- Create "projects" table
CREATE TABLE "projects" (
  "id" text NOT NULL,
  "name" text NOT NULL,
  "description" text NOT NULL DEFAULT '',
  "team" jsonb NOT NULL DEFAULT '[]',
  "lead" text NULL,
  "task_ids" jsonb NOT NULL DEFAULT '[]',
  "deadline" timestamptz NULL,
  "budget" double precision NOT NULL DEFAULT 0.0,
  "status" text NOT NULL DEFAULT 'planning',
  PRIMARY KEY ("id"),
  CONSTRAINT "projects_budget_check" CHECK (budget >= (0.0)::double precision)
);
-- Create index "idx_projects_lead" to table: "projects"
CREATE INDEX "idx_projects_lead" ON "projects" ("lead");
-- Create index "idx_projects_status" to table: "projects"
CREATE INDEX "idx_projects_status" ON "projects" ("status");
-- Create "ssrf_violations" table
CREATE TABLE "ssrf_violations" (
  "id" text NOT NULL,
  "timestamp" timestamptz NOT NULL,
  "url" text NOT NULL,
  "hostname" text NOT NULL,
  "port" bigint NOT NULL,
  "resolved_ip" text NULL,
  "blocked_range" text NULL,
  "provider_name" text NULL,
  "status" text NOT NULL DEFAULT 'pending',
  "resolved_by" text NULL,
  "resolved_at" timestamptz NULL,
  PRIMARY KEY ("id"),
  CONSTRAINT "ssrf_violations_check" CHECK (((status = 'pending'::text) AND (resolved_by IS NULL) AND (resolved_at IS NULL)) OR ((status = ANY (ARRAY['allowed'::text, 'denied'::text])) AND (resolved_by IS NOT NULL) AND (resolved_at IS NOT NULL))),
  CONSTRAINT "ssrf_violations_port_check" CHECK ((port >= 1) AND (port <= 65535)),
  CONSTRAINT "ssrf_violations_status_check" CHECK (status = ANY (ARRAY['pending'::text, 'allowed'::text, 'denied'::text]))
);
-- Create index "idx_sv_hostname" to table: "ssrf_violations"
CREATE INDEX "idx_sv_hostname" ON "ssrf_violations" ("hostname", "port");
-- Create index "idx_sv_status_timestamp" to table: "ssrf_violations"
CREATE INDEX "idx_sv_status_timestamp" ON "ssrf_violations" ("status", "timestamp" DESC);
-- Create index "idx_sv_timestamp" to table: "ssrf_violations"
CREATE INDEX "idx_sv_timestamp" ON "ssrf_violations" ("timestamp");
-- Create "api_keys" table
CREATE TABLE "api_keys" (
  "id" text NOT NULL,
  "key_hash" text NOT NULL,
  "name" text NOT NULL,
  "role" text NOT NULL,
  "user_id" text NOT NULL,
  "created_at" timestamptz NOT NULL,
  "expires_at" timestamptz NULL,
  "revoked" boolean NOT NULL DEFAULT false,
  PRIMARY KEY ("id"),
  CONSTRAINT "api_keys_key_hash_key" UNIQUE ("key_hash"),
  CONSTRAINT "api_keys_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users" ("id") ON UPDATE NO ACTION ON DELETE CASCADE
);
-- Create index "idx_api_keys_user_id" to table: "api_keys"
CREATE INDEX "idx_api_keys_user_id" ON "api_keys" ("user_id");
-- Create "tasks" table
CREATE TABLE "tasks" (
  "id" text NOT NULL,
  "title" text NOT NULL,
  "description" text NOT NULL,
  "type" text NOT NULL,
  "priority" text NOT NULL DEFAULT 'medium',
  "project" text NOT NULL,
  "created_by" text NOT NULL,
  "assigned_to" text NULL,
  "status" text NOT NULL DEFAULT 'created',
  "estimated_complexity" text NOT NULL DEFAULT 'medium',
  "budget_limit" double precision NOT NULL DEFAULT 0.0,
  "deadline" timestamptz NULL,
  "max_retries" bigint NOT NULL DEFAULT 1,
  "parent_task_id" text NULL,
  "task_structure" jsonb NULL,
  "coordination_topology" text NOT NULL DEFAULT 'auto',
  "reviewers" jsonb NOT NULL DEFAULT '[]',
  "dependencies" jsonb NOT NULL DEFAULT '[]',
  "artifacts_expected" jsonb NOT NULL DEFAULT '[]',
  "acceptance_criteria" jsonb NOT NULL DEFAULT '[]',
  "delegation_chain" jsonb NOT NULL DEFAULT '[]',
  PRIMARY KEY ("id")
);
-- Create index "idx_tasks_assigned_to" to table: "tasks"
CREATE INDEX "idx_tasks_assigned_to" ON "tasks" ("assigned_to");
-- Create index "idx_tasks_project" to table: "tasks"
CREATE INDEX "idx_tasks_project" ON "tasks" ("project");
-- Create index "idx_tasks_status" to table: "tasks"
CREATE INDEX "idx_tasks_status" ON "tasks" ("status");
-- Create "cost_records" table
CREATE TABLE "cost_records" (
  "rowid" bigint NOT NULL GENERATED ALWAYS AS IDENTITY,
  "agent_id" text NOT NULL,
  "task_id" text NOT NULL,
  "provider" text NOT NULL,
  "model" text NOT NULL,
  "input_tokens" bigint NOT NULL,
  "output_tokens" bigint NOT NULL,
  "cost_usd" double precision NOT NULL,
  "timestamp" timestamptz NOT NULL,
  "call_category" text NULL,
  PRIMARY KEY ("rowid"),
  CONSTRAINT "cost_records_task_id_fkey" FOREIGN KEY ("task_id") REFERENCES "tasks" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION
);
-- Create index "idx_cost_records_agent_id" to table: "cost_records"
CREATE INDEX "idx_cost_records_agent_id" ON "cost_records" ("agent_id");
-- Create index "idx_cost_records_task_id" to table: "cost_records"
CREATE INDEX "idx_cost_records_task_id" ON "cost_records" ("task_id");
-- Create index "idx_cost_records_timestamp" to table: "cost_records"
CREATE INDEX "idx_cost_records_timestamp" ON "cost_records" ("timestamp" DESC);
-- Create "decision_records" table
CREATE TABLE "decision_records" (
  "id" text NOT NULL,
  "task_id" text NOT NULL,
  "approval_id" text NULL,
  "executing_agent_id" text NOT NULL,
  "reviewer_agent_id" text NOT NULL,
  "decision" text NOT NULL,
  "reason" text NULL,
  "criteria_snapshot" jsonb NOT NULL DEFAULT '[]',
  "recorded_at" timestamptz NOT NULL,
  "version" bigint NOT NULL,
  "metadata" jsonb NOT NULL DEFAULT '{}',
  PRIMARY KEY ("id"),
  CONSTRAINT "decision_records_task_id_version_key" UNIQUE ("task_id", "version"),
  CONSTRAINT "decision_records_task_id_fkey" FOREIGN KEY ("task_id") REFERENCES "tasks" ("id") ON UPDATE NO ACTION ON DELETE RESTRICT,
  CONSTRAINT "decision_records_check" CHECK (reviewer_agent_id <> executing_agent_id),
  CONSTRAINT "decision_records_decision_check" CHECK (decision = ANY (ARRAY['approved'::text, 'rejected'::text, 'auto_approved'::text, 'auto_rejected'::text, 'escalated'::text])),
  CONSTRAINT "decision_records_version_check" CHECK (version >= 1)
);
-- Create index "idx_dr_executing_agent_recorded" to table: "decision_records"
CREATE INDEX "idx_dr_executing_agent_recorded" ON "decision_records" ("executing_agent_id", "recorded_at" DESC);
-- Create index "idx_dr_metadata_gin" to table: "decision_records"
CREATE INDEX "idx_dr_metadata_gin" ON "decision_records" USING GIN ("metadata");
-- Create index "idx_dr_reviewer_agent_recorded" to table: "decision_records"
CREATE INDEX "idx_dr_reviewer_agent_recorded" ON "decision_records" ("reviewer_agent_id", "recorded_at" DESC);
-- Create "fine_tune_runs" table
CREATE TABLE "fine_tune_runs" (
  "id" text NOT NULL,
  "stage" text NOT NULL,
  "progress" double precision NULL,
  "error" text NULL,
  "config_json" jsonb NOT NULL,
  "started_at" timestamptz NOT NULL,
  "updated_at" timestamptz NOT NULL,
  "completed_at" timestamptz NULL,
  "stages_completed" jsonb NOT NULL DEFAULT '[]',
  PRIMARY KEY ("id"),
  CONSTRAINT "fine_tune_runs_id_check" CHECK (length(id) > 0),
  CONSTRAINT "fine_tune_runs_progress_check" CHECK ((progress IS NULL) OR ((progress >= (0.0)::double precision) AND (progress <= (1.0)::double precision))),
  CONSTRAINT "fine_tune_runs_stage_check" CHECK (stage = ANY (ARRAY['idle'::text, 'generating_data'::text, 'mining_negatives'::text, 'training'::text, 'evaluating'::text, 'deploying'::text, 'complete'::text, 'failed'::text]))
);
-- Create index "idx_ftr_stage" to table: "fine_tune_runs"
CREATE INDEX "idx_ftr_stage" ON "fine_tune_runs" ("stage");
-- Create index "idx_ftr_started_at" to table: "fine_tune_runs"
CREATE INDEX "idx_ftr_started_at" ON "fine_tune_runs" ("started_at" DESC);
-- Create index "idx_ftr_updated_at" to table: "fine_tune_runs"
CREATE INDEX "idx_ftr_updated_at" ON "fine_tune_runs" ("updated_at" DESC);
-- Create "fine_tune_checkpoints" table
CREATE TABLE "fine_tune_checkpoints" (
  "id" text NOT NULL,
  "run_id" text NOT NULL,
  "model_path" text NOT NULL,
  "base_model" text NOT NULL,
  "doc_count" bigint NOT NULL,
  "eval_metrics_json" jsonb NULL,
  "size_bytes" bigint NOT NULL,
  "created_at" timestamptz NOT NULL,
  "is_active" boolean NOT NULL DEFAULT false,
  "backup_config_json" jsonb NULL,
  PRIMARY KEY ("id"),
  CONSTRAINT "fine_tune_checkpoints_run_id_fkey" FOREIGN KEY ("run_id") REFERENCES "fine_tune_runs" ("id") ON UPDATE NO ACTION ON DELETE CASCADE,
  CONSTRAINT "fine_tune_checkpoints_doc_count_check" CHECK (doc_count >= 0),
  CONSTRAINT "fine_tune_checkpoints_id_check" CHECK (length(id) > 0),
  CONSTRAINT "fine_tune_checkpoints_size_bytes_check" CHECK (size_bytes >= 0)
);
-- Create index "idx_ftc_active" to table: "fine_tune_checkpoints"
CREATE INDEX "idx_ftc_active" ON "fine_tune_checkpoints" ("is_active");
-- Create index "idx_ftc_created_at" to table: "fine_tune_checkpoints"
CREATE INDEX "idx_ftc_created_at" ON "fine_tune_checkpoints" ("created_at" DESC);
-- Create index "idx_ftc_run_id" to table: "fine_tune_checkpoints"
CREATE INDEX "idx_ftc_run_id" ON "fine_tune_checkpoints" ("run_id");
-- Create index "idx_ftc_single_active" to table: "fine_tune_checkpoints"
CREATE UNIQUE INDEX "idx_ftc_single_active" ON "fine_tune_checkpoints" ("is_active") WHERE (is_active = true);
-- Create "sessions" table
CREATE TABLE "sessions" (
  "session_id" text NOT NULL,
  "user_id" text NOT NULL,
  "username" text NOT NULL,
  "role" text NOT NULL,
  "ip_address" text NOT NULL DEFAULT '',
  "user_agent" text NOT NULL DEFAULT '',
  "created_at" timestamptz NOT NULL,
  "last_active_at" timestamptz NOT NULL,
  "expires_at" timestamptz NOT NULL,
  "revoked" boolean NOT NULL DEFAULT false,
  PRIMARY KEY ("session_id"),
  CONSTRAINT "sessions_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users" ("id") ON UPDATE NO ACTION ON DELETE CASCADE
);
-- Create index "idx_sessions_expires_at" to table: "sessions"
CREATE INDEX "idx_sessions_expires_at" ON "sessions" ("expires_at");
-- Create index "idx_sessions_revoked_expires" to table: "sessions"
CREATE INDEX "idx_sessions_revoked_expires" ON "sessions" ("revoked", "expires_at");
-- Create index "idx_sessions_user_revoked_expires" to table: "sessions"
CREATE INDEX "idx_sessions_user_revoked_expires" ON "sessions" ("user_id", "revoked", "expires_at");
-- Create "refresh_tokens" table
CREATE TABLE "refresh_tokens" (
  "token_hash" text NOT NULL,
  "session_id" text NOT NULL,
  "user_id" text NOT NULL,
  "expires_at" timestamptz NOT NULL,
  "used" boolean NOT NULL DEFAULT false,
  "created_at" timestamptz NOT NULL,
  PRIMARY KEY ("token_hash"),
  CONSTRAINT "refresh_tokens_session_id_fkey" FOREIGN KEY ("session_id") REFERENCES "sessions" ("session_id") ON UPDATE NO ACTION ON DELETE CASCADE,
  CONSTRAINT "refresh_tokens_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users" ("id") ON UPDATE NO ACTION ON DELETE CASCADE
);
-- Create index "idx_rt_expires_at" to table: "refresh_tokens"
CREATE INDEX "idx_rt_expires_at" ON "refresh_tokens" ("expires_at");
-- Create index "idx_rt_session_id" to table: "refresh_tokens"
CREATE INDEX "idx_rt_session_id" ON "refresh_tokens" ("session_id");
-- Create index "idx_rt_user_id" to table: "refresh_tokens"
CREATE INDEX "idx_rt_user_id" ON "refresh_tokens" ("user_id");
-- Create "task_metrics" table
CREATE TABLE "task_metrics" (
  "id" text NOT NULL,
  "agent_id" text NOT NULL,
  "task_id" text NOT NULL,
  "task_type" text NOT NULL,
  "completed_at" timestamptz NOT NULL,
  "is_success" boolean NOT NULL,
  "duration_seconds" double precision NOT NULL,
  "cost_usd" double precision NOT NULL,
  "turns_used" bigint NOT NULL,
  "tokens_used" bigint NOT NULL,
  "quality_score" double precision NULL,
  "complexity" text NOT NULL,
  PRIMARY KEY ("id"),
  CONSTRAINT "task_metrics_task_id_fkey" FOREIGN KEY ("task_id") REFERENCES "tasks" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION
);
-- Create index "idx_tm_agent_completed" to table: "task_metrics"
CREATE INDEX "idx_tm_agent_completed" ON "task_metrics" ("agent_id", "completed_at");
-- Create index "idx_tm_agent_id" to table: "task_metrics"
CREATE INDEX "idx_tm_agent_id" ON "task_metrics" ("agent_id");
-- Create index "idx_tm_completed_at" to table: "task_metrics"
CREATE INDEX "idx_tm_completed_at" ON "task_metrics" ("completed_at");
-- Create "workflow_definitions" table
CREATE TABLE "workflow_definitions" (
  "id" text NOT NULL,
  "name" text NOT NULL,
  "description" text NOT NULL DEFAULT '',
  "workflow_type" text NOT NULL,
  "nodes" jsonb NOT NULL,
  "edges" jsonb NOT NULL,
  "created_by" text NOT NULL,
  "created_at" timestamptz NOT NULL,
  "updated_at" timestamptz NOT NULL,
  "version" bigint NOT NULL DEFAULT 1,
  PRIMARY KEY ("id"),
  CONSTRAINT "workflow_definitions_created_by_check" CHECK (length(created_by) > 0),
  CONSTRAINT "workflow_definitions_id_check" CHECK (length(id) > 0),
  CONSTRAINT "workflow_definitions_name_check" CHECK (length(name) > 0),
  CONSTRAINT "workflow_definitions_version_check" CHECK (version >= 1),
  CONSTRAINT "workflow_definitions_workflow_type_check" CHECK (workflow_type = ANY (ARRAY['sequential_pipeline'::text, 'parallel_execution'::text, 'kanban'::text, 'agile_kanban'::text]))
);
-- Create index "idx_wd_updated_at" to table: "workflow_definitions"
CREATE INDEX "idx_wd_updated_at" ON "workflow_definitions" ("updated_at" DESC);
-- Create index "idx_wd_workflow_type" to table: "workflow_definitions"
CREATE INDEX "idx_wd_workflow_type" ON "workflow_definitions" ("workflow_type");
-- Create "workflow_executions" table
CREATE TABLE "workflow_executions" (
  "id" text NOT NULL,
  "definition_id" text NOT NULL,
  "definition_version" bigint NOT NULL,
  "status" text NOT NULL,
  "node_executions" jsonb NOT NULL DEFAULT '[]',
  "activated_by" text NOT NULL,
  "project" text NOT NULL,
  "created_at" timestamptz NOT NULL,
  "updated_at" timestamptz NOT NULL,
  "completed_at" timestamptz NULL,
  "error" text NULL,
  "version" bigint NOT NULL DEFAULT 1,
  PRIMARY KEY ("id"),
  CONSTRAINT "workflow_executions_definition_id_fkey" FOREIGN KEY ("definition_id") REFERENCES "workflow_definitions" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION,
  CONSTRAINT "workflow_executions_activated_by_check" CHECK (length(activated_by) > 0),
  CONSTRAINT "workflow_executions_definition_id_check" CHECK (length(definition_id) > 0),
  CONSTRAINT "workflow_executions_definition_version_check" CHECK (definition_version >= 1),
  CONSTRAINT "workflow_executions_id_check" CHECK (length(id) > 0),
  CONSTRAINT "workflow_executions_project_check" CHECK (length(project) > 0),
  CONSTRAINT "workflow_executions_status_check" CHECK (status = ANY (ARRAY['pending'::text, 'running'::text, 'completed'::text, 'failed'::text, 'cancelled'::text])),
  CONSTRAINT "workflow_executions_version_check" CHECK (version >= 1)
);
-- Create index "idx_wfe_definition_id" to table: "workflow_executions"
CREATE INDEX "idx_wfe_definition_id" ON "workflow_executions" ("definition_id");
-- Create index "idx_wfe_definition_updated" to table: "workflow_executions"
CREATE INDEX "idx_wfe_definition_updated" ON "workflow_executions" ("definition_id", "updated_at" DESC);
-- Create index "idx_wfe_project" to table: "workflow_executions"
CREATE INDEX "idx_wfe_project" ON "workflow_executions" ("project");
-- Create index "idx_wfe_status" to table: "workflow_executions"
CREATE INDEX "idx_wfe_status" ON "workflow_executions" ("status");
-- Create index "idx_wfe_status_updated" to table: "workflow_executions"
CREATE INDEX "idx_wfe_status_updated" ON "workflow_executions" ("status", "updated_at" DESC);
-- Create index "idx_wfe_updated_at" to table: "workflow_executions"
CREATE INDEX "idx_wfe_updated_at" ON "workflow_executions" ("updated_at" DESC);
