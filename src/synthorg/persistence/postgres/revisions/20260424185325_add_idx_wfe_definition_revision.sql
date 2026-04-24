-- Create index "idx_wfe_definition_revision" to table: "workflow_executions"
CREATE INDEX "idx_wfe_definition_revision" ON "workflow_executions" ("definition_id", "definition_revision");
