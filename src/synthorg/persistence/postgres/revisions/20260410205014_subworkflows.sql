-- Create "subworkflows" table
CREATE TABLE "subworkflows" (
  "subworkflow_id" text NOT NULL,
  "semver" text NOT NULL,
  "name" text NOT NULL,
  "description" text NOT NULL DEFAULT '',
  "workflow_type" text NOT NULL,
  "inputs" jsonb NOT NULL DEFAULT '[]',
  "outputs" jsonb NOT NULL DEFAULT '[]',
  "nodes" jsonb NOT NULL,
  "edges" jsonb NOT NULL,
  "created_by" text NOT NULL,
  "created_at" timestamptz NOT NULL,
  "updated_at" timestamptz NOT NULL,
  PRIMARY KEY ("subworkflow_id", "semver"),
  CONSTRAINT "subworkflows_created_by_check" CHECK (length(created_by) > 0),
  CONSTRAINT "subworkflows_name_check" CHECK (length(name) > 0),
  CONSTRAINT "subworkflows_semver_check" CHECK (length(semver) > 0),
  CONSTRAINT "subworkflows_subworkflow_id_check" CHECK (length(subworkflow_id) > 0),
  CONSTRAINT "subworkflows_workflow_type_check" CHECK (workflow_type = ANY (ARRAY['sequential_pipeline'::text, 'parallel_execution'::text, 'kanban'::text, 'agile_kanban'::text]))
);
-- Create index "idx_subworkflows_created_at" to table: "subworkflows"
CREATE INDEX "idx_subworkflows_created_at" ON "subworkflows" ("created_at" DESC);
-- Create index "idx_subworkflows_id" to table: "subworkflows"
CREATE INDEX "idx_subworkflows_id" ON "subworkflows" ("subworkflow_id");
-- Create index "idx_subworkflows_updated_at" to table: "subworkflows"
CREATE INDEX "idx_subworkflows_updated_at" ON "subworkflows" ("updated_at" DESC);
