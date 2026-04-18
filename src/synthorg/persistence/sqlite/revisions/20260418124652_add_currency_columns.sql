-- Add column "currency" to table: "cost_records"
ALTER TABLE `cost_records` ADD COLUMN `currency` text NOT NULL DEFAULT 'EUR';
-- Add column "currency" to table: "task_metrics"
ALTER TABLE `task_metrics` ADD COLUMN `currency` text NOT NULL DEFAULT 'EUR';
-- Add column "currency" to table: "agent_states"
ALTER TABLE `agent_states` ADD COLUMN `currency` text NOT NULL DEFAULT 'EUR';
