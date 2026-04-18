-- Modify "agent_states" table
ALTER TABLE "agent_states" ADD CONSTRAINT "agent_states_currency_check" CHECK (currency ~ '^[A-Z]{3}$'::text), ADD COLUMN "currency" text NOT NULL DEFAULT 'USD';
-- Modify "cost_records" table
ALTER TABLE "cost_records" ADD CONSTRAINT "cost_records_currency_check" CHECK (currency ~ '^[A-Z]{3}$'::text), ADD COLUMN "currency" text NOT NULL DEFAULT 'USD';
-- Modify "task_metrics" table
ALTER TABLE "task_metrics" ADD CONSTRAINT "task_metrics_currency_check" CHECK (currency ~ '^[A-Z]{3}$'::text), ADD COLUMN "currency" text NOT NULL DEFAULT 'USD';
-- Create "custom_rules" table
CREATE TABLE "custom_rules" (
  "id" text NOT NULL,
  "name" text NOT NULL,
  "description" text NOT NULL,
  "metric_path" text NOT NULL,
  "comparator" text NOT NULL,
  "threshold" double precision NOT NULL,
  "severity" text NOT NULL,
  "target_altitudes" jsonb NOT NULL,
  "enabled" boolean NOT NULL DEFAULT true,
  "created_at" timestamptz NOT NULL,
  "updated_at" timestamptz NOT NULL,
  PRIMARY KEY ("id"),
  CONSTRAINT "custom_rules_comparator_check" CHECK (length(TRIM(BOTH FROM comparator)) > 0),
  CONSTRAINT "custom_rules_description_check" CHECK (length(TRIM(BOTH FROM description)) > 0),
  CONSTRAINT "custom_rules_id_check" CHECK (length(id) > 0),
  CONSTRAINT "custom_rules_metric_path_check" CHECK (length(TRIM(BOTH FROM metric_path)) > 0),
  CONSTRAINT "custom_rules_name_check" CHECK (length(TRIM(BOTH FROM name)) > 0),
  CONSTRAINT "custom_rules_severity_check" CHECK (length(TRIM(BOTH FROM severity)) > 0)
);
-- Create index "custom_rules_name" to table: "custom_rules"
CREATE UNIQUE INDEX "custom_rules_name" ON "custom_rules" ("name");
-- Create "approvals" table
CREATE TABLE "approvals" (
  "id" text NOT NULL,
  "action_type" text NOT NULL,
  "title" text NOT NULL,
  "description" text NOT NULL,
  "requested_by" text NOT NULL,
  "risk_level" text NOT NULL DEFAULT 'medium',
  "status" text NOT NULL DEFAULT 'pending',
  "created_at" timestamptz NOT NULL,
  "expires_at" timestamptz NULL,
  "decided_at" timestamptz NULL,
  "decided_by" text NULL,
  "decision_reason" text NULL,
  "task_id" text NULL,
  "evidence_package" jsonb NULL,
  "metadata" jsonb NOT NULL DEFAULT '{}',
  PRIMARY KEY ("id"),
  CONSTRAINT "approvals_task_id_fkey" FOREIGN KEY ("task_id") REFERENCES "tasks" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION,
  CONSTRAINT "approvals_action_type_check" CHECK (length(TRIM(BOTH FROM action_type)) > 0),
  CONSTRAINT "approvals_check" CHECK (((decided_at IS NULL) AND (decided_by IS NULL)) OR ((decided_at IS NOT NULL) AND (decided_by IS NOT NULL))),
  CONSTRAINT "approvals_check1" CHECK ((status <> 'rejected'::text) OR ((decision_reason IS NOT NULL) AND (length(TRIM(BOTH FROM decision_reason)) > 0))),
  CONSTRAINT "approvals_id_check" CHECK (length(TRIM(BOTH FROM id)) > 0),
  CONSTRAINT "approvals_requested_by_check" CHECK (length(TRIM(BOTH FROM requested_by)) > 0),
  CONSTRAINT "approvals_risk_level_check" CHECK (risk_level = ANY (ARRAY['low'::text, 'medium'::text, 'high'::text, 'critical'::text])),
  CONSTRAINT "approvals_status_check" CHECK (status = ANY (ARRAY['pending'::text, 'approved'::text, 'rejected'::text, 'expired'::text])),
  CONSTRAINT "approvals_title_check" CHECK (length(TRIM(BOTH FROM title)) > 0)
);
-- Create index "idx_approvals_action_type" to table: "approvals"
CREATE INDEX "idx_approvals_action_type" ON "approvals" ("action_type");
-- Create index "idx_approvals_risk_level" to table: "approvals"
CREATE INDEX "idx_approvals_risk_level" ON "approvals" ("risk_level");
-- Create index "idx_approvals_status" to table: "approvals"
CREATE INDEX "idx_approvals_status" ON "approvals" ("status");
