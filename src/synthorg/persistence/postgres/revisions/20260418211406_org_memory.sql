-- Create "org_facts_operation_log" table
CREATE TABLE "org_facts_operation_log" (
  "operation_id" text NOT NULL,
  "fact_id" text NOT NULL,
  "operation_type" text NOT NULL,
  "content" text NULL,
  "tags" text NOT NULL DEFAULT '[]',
  "author_agent_id" text NULL,
  "author_seniority" text NULL,
  "author_is_human" boolean NOT NULL DEFAULT false,
  "author_autonomy_level" text NULL,
  "category" text NULL,
  "timestamp" timestamptz NOT NULL,
  "version" integer NOT NULL,
  PRIMARY KEY ("operation_id"),
  CONSTRAINT "org_facts_operation_log_fact_id_version_key" UNIQUE ("fact_id", "version"),
  CONSTRAINT "org_facts_operation_log_operation_type_check" CHECK (operation_type = ANY (ARRAY['PUBLISH'::text, 'RETRACT'::text]))
);
-- Create index "idx_oplog_fact_id" to table: "org_facts_operation_log"
CREATE INDEX "idx_oplog_fact_id" ON "org_facts_operation_log" ("fact_id");
-- Create index "idx_oplog_timestamp" to table: "org_facts_operation_log"
CREATE INDEX "idx_oplog_timestamp" ON "org_facts_operation_log" ("timestamp");
-- Create index "idx_oplog_ts_fact" to table: "org_facts_operation_log"
CREATE INDEX "idx_oplog_ts_fact" ON "org_facts_operation_log" ("timestamp", "fact_id");
-- Create "org_facts_snapshot" table
CREATE TABLE "org_facts_snapshot" (
  "fact_id" text NOT NULL,
  "content" text NOT NULL,
  "category" text NOT NULL,
  "tags" text NOT NULL DEFAULT '[]',
  "author_agent_id" text NULL,
  "author_seniority" text NULL,
  "author_is_human" boolean NOT NULL DEFAULT false,
  "author_autonomy_level" text NULL,
  "created_at" timestamptz NOT NULL,
  "retracted_at" timestamptz NULL,
  "version" integer NOT NULL,
  PRIMARY KEY ("fact_id")
);
-- Create index "idx_snapshot_active" to table: "org_facts_snapshot"
CREATE INDEX "idx_snapshot_active" ON "org_facts_snapshot" ("retracted_at") WHERE (retracted_at IS NULL);
-- Create index "idx_snapshot_category" to table: "org_facts_snapshot"
CREATE INDEX "idx_snapshot_category" ON "org_facts_snapshot" ("category");
