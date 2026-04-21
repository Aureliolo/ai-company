-- Create index "idx_approvals_requested_by_status" to table: "approvals"
CREATE INDEX "idx_approvals_requested_by_status" ON "approvals" ("requested_by", "status");
-- Create index "idx_approvals_status_expires_at" to table: "approvals"
CREATE INDEX "idx_approvals_status_expires_at" ON "approvals" ("status", "expires_at");
-- Create index "idx_custom_rules_enabled" to table: "custom_rules"
CREATE INDEX "idx_custom_rules_enabled" ON "custom_rules" ("enabled");
-- Create index "idx_messages_sender" to table: "messages"
CREATE INDEX "idx_messages_sender" ON "messages" ("sender");
-- Create index "idx_messages_to" to table: "messages"
CREATE INDEX "idx_messages_to" ON "messages" ("to");
-- Modify "workflow_definitions" table
ALTER TABLE "workflow_definitions" DROP CONSTRAINT "workflow_definitions_version_check", ADD CONSTRAINT "workflow_definitions_version_check" CHECK (length(version) > 0), ADD CONSTRAINT "workflow_definitions_revision_check" CHECK (revision >= 1), ALTER COLUMN "version" TYPE text, ALTER COLUMN "version" SET DEFAULT '1.0.0', ADD COLUMN "inputs" jsonb NOT NULL DEFAULT '[]', ADD COLUMN "outputs" jsonb NOT NULL DEFAULT '[]', ADD COLUMN "is_subworkflow" boolean NOT NULL DEFAULT false, ADD COLUMN "revision" bigint NOT NULL DEFAULT 1;
-- Create index "idx_wd_is_subworkflow" to table: "workflow_definitions"
CREATE INDEX "idx_wd_is_subworkflow" ON "workflow_definitions" ("is_subworkflow");
-- Modify "workflow_executions" table
ALTER TABLE "workflow_executions" DROP CONSTRAINT "workflow_executions_definition_version_check", ADD CONSTRAINT "workflow_executions_definition_revision_check" CHECK (definition_revision >= 1), DROP COLUMN "definition_version", ADD COLUMN "definition_revision" bigint NOT NULL;
