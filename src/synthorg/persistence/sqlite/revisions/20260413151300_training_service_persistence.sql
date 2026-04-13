-- Create "training_plans" table
CREATE TABLE `training_plans` (
  `id` text NOT NULL,
  `new_agent_id` text NOT NULL,
  `new_agent_role` text NOT NULL,
  `new_agent_level` text NOT NULL,
  `new_agent_department` text NULL,
  `source_selector_type` text NOT NULL DEFAULT 'role_top_performers',
  `enabled_content_types` text NOT NULL DEFAULT '[]',
  `curation_strategy_type` text NOT NULL DEFAULT 'relevance',
  `volume_caps` text NOT NULL DEFAULT '[]',
  `override_sources` text NOT NULL DEFAULT '[]',
  `skip_training` integer NOT NULL DEFAULT 0,
  `require_review` integer NOT NULL DEFAULT 1,
  `status` text NOT NULL DEFAULT 'pending',
  `created_at` text NOT NULL,
  `executed_at` text NULL,
  PRIMARY KEY (`id`),
  CHECK (status IN ('pending', 'executed', 'failed')),
  CHECK (
        (status = 'pending' AND executed_at IS NULL)
        OR (status <> 'pending' AND executed_at IS NOT NULL)
    )
);
-- Create index "idx_training_plans_agent_status" to table: "training_plans"
CREATE INDEX `idx_training_plans_agent_status` ON `training_plans` (`new_agent_id`, `status`);
-- Create index "idx_training_plans_created" to table: "training_plans"
CREATE INDEX `idx_training_plans_created` ON `training_plans` (`created_at`);
-- Create "training_results" table
CREATE TABLE `training_results` (
  `id` text NOT NULL,
  `plan_id` text NOT NULL,
  `new_agent_id` text NOT NULL,
  `source_agents_used` text NOT NULL DEFAULT '[]',
  `items_extracted` text NOT NULL DEFAULT '[]',
  `items_after_curation` text NOT NULL DEFAULT '[]',
  `items_after_guards` text NOT NULL DEFAULT '[]',
  `items_stored` text NOT NULL DEFAULT '[]',
  `approval_item_id` text NULL,
  `pending_approvals` text NOT NULL DEFAULT '[]',
  `review_pending` integer NOT NULL DEFAULT 0,
  `errors` text NOT NULL DEFAULT '[]',
  `started_at` text NOT NULL,
  `completed_at` text NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `0` FOREIGN KEY (`plan_id`) REFERENCES `training_plans` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
);
-- Create index "idx_training_results_plan" to table: "training_results"
CREATE UNIQUE INDEX `idx_training_results_plan` ON `training_results` (`plan_id`);
-- Create index "idx_training_results_agent" to table: "training_results"
CREATE INDEX `idx_training_results_agent` ON `training_results` (`new_agent_id`, `completed_at` DESC);
