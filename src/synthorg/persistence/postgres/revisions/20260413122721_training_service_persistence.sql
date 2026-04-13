-- Create "training_plans" table
CREATE TABLE "training_plans" (
  "id" text NOT NULL,
  "new_agent_id" text NOT NULL,
  "new_agent_role" text NOT NULL,
  "new_agent_level" text NOT NULL,
  "new_agent_department" text NULL,
  "source_selector_type" text NOT NULL DEFAULT 'role_top_performers',
  "enabled_content_types" jsonb NOT NULL DEFAULT '[]',
  "curation_strategy_type" text NOT NULL DEFAULT 'relevance',
  "volume_caps" jsonb NOT NULL DEFAULT '[]',
  "override_sources" jsonb NOT NULL DEFAULT '[]',
  "skip_training" boolean NOT NULL DEFAULT false,
  "require_review" boolean NOT NULL DEFAULT true,
  "status" text NOT NULL DEFAULT 'pending',
  "created_at" timestamptz NOT NULL,
  "executed_at" timestamptz NULL,
  PRIMARY KEY ("id"),
  CONSTRAINT "training_plans_status_check" CHECK (status = ANY (ARRAY['pending'::text, 'executed'::text, 'failed'::text]))
);
-- Create index "idx_training_plans_agent_status" to table: "training_plans"
CREATE INDEX "idx_training_plans_agent_status" ON "training_plans" ("new_agent_id", "status");
-- Create index "idx_training_plans_created" to table: "training_plans"
CREATE INDEX "idx_training_plans_created" ON "training_plans" ("created_at");
-- Create "training_results" table
CREATE TABLE "training_results" (
  "id" text NOT NULL,
  "plan_id" text NOT NULL,
  "new_agent_id" text NOT NULL,
  "source_agents_used" jsonb NOT NULL DEFAULT '[]',
  "items_extracted" jsonb NOT NULL DEFAULT '[]',
  "items_after_curation" jsonb NOT NULL DEFAULT '[]',
  "items_after_guards" jsonb NOT NULL DEFAULT '[]',
  "items_stored" jsonb NOT NULL DEFAULT '[]',
  "approval_item_id" text NULL,
  "pending_approvals" jsonb NOT NULL DEFAULT '[]',
  "review_pending" boolean NOT NULL DEFAULT false,
  "errors" jsonb NOT NULL DEFAULT '[]',
  "started_at" timestamptz NOT NULL,
  "completed_at" timestamptz NOT NULL,
  PRIMARY KEY ("id"),
  CONSTRAINT "training_results_plan_id_fkey" FOREIGN KEY ("plan_id") REFERENCES "training_plans" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION
);
-- Create index "idx_training_results_agent" to table: "training_results"
CREATE INDEX "idx_training_results_agent" ON "training_results" ("new_agent_id", "completed_at" DESC);
-- Create index "idx_training_results_plan" to table: "training_results"
CREATE INDEX "idx_training_results_plan" ON "training_results" ("plan_id");
