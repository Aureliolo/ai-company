-- Disable the enforcement of foreign-keys constraints
PRAGMA foreign_keys = off;
-- Create "new_cost_records" table
CREATE TABLE `new_cost_records` (
  `rowid` integer NULL PRIMARY KEY AUTOINCREMENT,
  `agent_id` text NOT NULL,
  `task_id` text NOT NULL,
  `provider` text NOT NULL,
  `model` text NOT NULL,
  `input_tokens` integer NOT NULL,
  `output_tokens` integer NOT NULL,
  `cost` real NOT NULL,
  `currency` text NOT NULL DEFAULT 'USD',
  `timestamp` text NOT NULL,
  `call_category` text NULL,
  CONSTRAINT `0` FOREIGN KEY (`task_id`) REFERENCES `tasks` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION,
  CHECK (currency GLOB '[A-Z][A-Z][A-Z]')
);
-- Copy rows from old table "cost_records" to new temporary table "new_cost_records"
INSERT INTO `new_cost_records` (`rowid`, `agent_id`, `task_id`, `provider`, `model`, `input_tokens`, `output_tokens`, `cost`, `timestamp`, `call_category`) SELECT `rowid`, `agent_id`, `task_id`, `provider`, `model`, `input_tokens`, `output_tokens`, `cost`, `timestamp`, `call_category` FROM `cost_records`;
-- Drop "cost_records" table after copying rows
DROP TABLE `cost_records`;
-- Rename temporary table "new_cost_records" to "cost_records"
ALTER TABLE `new_cost_records` RENAME TO `cost_records`;
-- Create index "idx_cost_records_agent_id" to table: "cost_records"
CREATE INDEX `idx_cost_records_agent_id` ON `cost_records` (`agent_id`);
-- Create index "idx_cost_records_task_id" to table: "cost_records"
CREATE INDEX `idx_cost_records_task_id` ON `cost_records` (`task_id`);
-- Create "new_task_metrics" table
CREATE TABLE `new_task_metrics` (
  `id` text NOT NULL,
  `agent_id` text NOT NULL,
  `task_id` text NOT NULL,
  `task_type` text NOT NULL,
  `completed_at` text NOT NULL,
  `is_success` integer NOT NULL,
  `duration_seconds` real NOT NULL,
  `cost` real NOT NULL,
  `currency` text NOT NULL DEFAULT 'USD',
  `turns_used` integer NOT NULL,
  `tokens_used` integer NOT NULL,
  `quality_score` real NULL,
  `complexity` text NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `0` FOREIGN KEY (`task_id`) REFERENCES `tasks` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION,
  CHECK (currency GLOB '[A-Z][A-Z][A-Z]')
);
-- Copy rows from old table "task_metrics" to new temporary table "new_task_metrics"
INSERT INTO `new_task_metrics` (`id`, `agent_id`, `task_id`, `task_type`, `completed_at`, `is_success`, `duration_seconds`, `cost`, `turns_used`, `tokens_used`, `quality_score`, `complexity`) SELECT `id`, `agent_id`, `task_id`, `task_type`, `completed_at`, `is_success`, `duration_seconds`, `cost`, `turns_used`, `tokens_used`, `quality_score`, `complexity` FROM `task_metrics`;
-- Drop "task_metrics" table after copying rows
DROP TABLE `task_metrics`;
-- Rename temporary table "new_task_metrics" to "task_metrics"
ALTER TABLE `new_task_metrics` RENAME TO `task_metrics`;
-- Create index "idx_tm_agent_id" to table: "task_metrics"
CREATE INDEX `idx_tm_agent_id` ON `task_metrics` (`agent_id`);
-- Create index "idx_tm_completed_at" to table: "task_metrics"
CREATE INDEX `idx_tm_completed_at` ON `task_metrics` (`completed_at`);
-- Create index "idx_tm_agent_completed" to table: "task_metrics"
CREATE INDEX `idx_tm_agent_completed` ON `task_metrics` (`agent_id`, `completed_at`);
-- Create "new_agent_states" table
CREATE TABLE `new_agent_states` (
  `agent_id` text NOT NULL,
  `execution_id` text NULL,
  `task_id` text NULL,
  `status` text NOT NULL DEFAULT 'idle',
  `turn_count` integer NOT NULL DEFAULT 0,
  `accumulated_cost` real NOT NULL DEFAULT 0.0,
  `currency` text NOT NULL DEFAULT 'USD',
  `last_activity_at` text NOT NULL,
  `started_at` text NULL,
  PRIMARY KEY (`agent_id`),
  CHECK (status IN ('idle', 'executing', 'paused')),
  CHECK (turn_count >= 0),
  CHECK (accumulated_cost >= 0.0),
  CHECK (currency GLOB '[A-Z][A-Z][A-Z]'),
  CHECK (
        (status = 'idle'
         AND execution_id IS NULL
         AND task_id IS NULL
         AND started_at IS NULL
         AND turn_count = 0
         AND accumulated_cost = 0.0)
        OR
        (status IN ('executing', 'paused')
         AND execution_id IS NOT NULL
         AND started_at IS NOT NULL)
    )
);
-- Copy rows from old table "agent_states" to new temporary table "new_agent_states"
INSERT INTO `new_agent_states` (`agent_id`, `execution_id`, `task_id`, `status`, `turn_count`, `accumulated_cost`, `last_activity_at`, `started_at`) SELECT `agent_id`, `execution_id`, `task_id`, `status`, `turn_count`, `accumulated_cost`, `last_activity_at`, `started_at` FROM `agent_states`;
-- Drop "agent_states" table after copying rows
DROP TABLE `agent_states`;
-- Rename temporary table "new_agent_states" to "agent_states"
ALTER TABLE `new_agent_states` RENAME TO `agent_states`;
-- Create index "idx_as_status_activity" to table: "agent_states"
CREATE INDEX `idx_as_status_activity` ON `agent_states` (`status`, `last_activity_at` DESC);
-- Enable back the enforcement of foreign-keys constraints
PRAGMA foreign_keys = on;
