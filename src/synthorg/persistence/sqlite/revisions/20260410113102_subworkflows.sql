-- Disable the enforcement of foreign-keys constraints
PRAGMA foreign_keys = off;
-- Create "new_workflow_definitions" table
CREATE TABLE `new_workflow_definitions` (
  `id` text NOT NULL,
  `name` text NOT NULL,
  `description` text NOT NULL DEFAULT '',
  `workflow_type` text NOT NULL,
  `version` text NOT NULL DEFAULT '1.0.0',
  `inputs` text NOT NULL DEFAULT '[]',
  `outputs` text NOT NULL DEFAULT '[]',
  `is_subworkflow` integer NOT NULL DEFAULT 0,
  `nodes` text NOT NULL,
  `edges` text NOT NULL,
  `created_by` text NOT NULL,
  `created_at` text NOT NULL,
  `updated_at` text NOT NULL,
  `revision` integer NOT NULL DEFAULT 1,
  PRIMARY KEY (`id`),
  CHECK (length(id) > 0),
  CHECK (length(name) > 0),
  CHECK (workflow_type IN (
        'sequential_pipeline', 'parallel_execution', 'kanban', 'agile_kanban'
    )),
  CHECK (length(version) > 0),
  CHECK (is_subworkflow IN (0, 1)),
  CHECK (length(created_by) > 0),
  CHECK (revision >= 1)
);
-- Copy rows from old table "workflow_definitions" to new temporary table "new_workflow_definitions"
INSERT INTO `new_workflow_definitions` (`id`, `name`, `description`, `workflow_type`, `version`, `nodes`, `edges`, `created_by`, `created_at`, `updated_at`, `revision`) SELECT `id`, `name`, `description`, `workflow_type`, '1.0.0', `nodes`, `edges`, `created_by`, `created_at`, `updated_at`, IFNULL(`version`, 1) FROM `workflow_definitions`;
-- Drop "workflow_definitions" table after copying rows
DROP TABLE `workflow_definitions`;
-- Rename temporary table "new_workflow_definitions" to "workflow_definitions"
ALTER TABLE `new_workflow_definitions` RENAME TO `workflow_definitions`;
-- Create index "idx_wd_workflow_type" to table: "workflow_definitions"
CREATE INDEX `idx_wd_workflow_type` ON `workflow_definitions` (`workflow_type`);
-- Create index "idx_wd_updated_at" to table: "workflow_definitions"
CREATE INDEX `idx_wd_updated_at` ON `workflow_definitions` (`updated_at` DESC);
-- Create index "idx_wd_is_subworkflow" to table: "workflow_definitions"
CREATE INDEX `idx_wd_is_subworkflow` ON `workflow_definitions` (`is_subworkflow`);
-- Create "new_workflow_executions" table
CREATE TABLE `new_workflow_executions` (
  `id` text NOT NULL,
  `definition_id` text NOT NULL,
  `definition_revision` integer NOT NULL,
  `status` text NOT NULL,
  `node_executions` text NOT NULL DEFAULT '[]',
  `activated_by` text NOT NULL,
  `project` text NOT NULL,
  `created_at` text NOT NULL,
  `updated_at` text NOT NULL,
  `completed_at` text NULL,
  `error` text NULL,
  `version` integer NOT NULL DEFAULT 1,
  PRIMARY KEY (`id`),
  CONSTRAINT `0` FOREIGN KEY (`definition_id`) REFERENCES `workflow_definitions` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION,
  CHECK (length(id) > 0),
  CHECK (length(definition_id) > 0),
  CHECK (definition_revision >= 1),
  CHECK (status IN (
        'pending', 'running', 'completed', 'failed', 'cancelled'
    )),
  CHECK (length(activated_by) > 0),
  CHECK (length(project) > 0),
  CHECK (version >= 1)
);
-- Copy rows from old table "workflow_executions" to new temporary table "new_workflow_executions"
INSERT INTO `new_workflow_executions` (`id`, `definition_id`, `definition_revision`, `status`, `node_executions`, `activated_by`, `project`, `created_at`, `updated_at`, `completed_at`, `error`, `version`) SELECT `id`, `definition_id`, IFNULL(`definition_version`, 1), `status`, `node_executions`, `activated_by`, `project`, `created_at`, `updated_at`, `completed_at`, `error`, `version` FROM `workflow_executions`;
-- Drop "workflow_executions" table after copying rows
DROP TABLE `workflow_executions`;
-- Rename temporary table "new_workflow_executions" to "workflow_executions"
ALTER TABLE `new_workflow_executions` RENAME TO `workflow_executions`;
-- Create index "idx_wfe_definition_id" to table: "workflow_executions"
CREATE INDEX `idx_wfe_definition_id` ON `workflow_executions` (`definition_id`);
-- Create index "idx_wfe_status" to table: "workflow_executions"
CREATE INDEX `idx_wfe_status` ON `workflow_executions` (`status`);
-- Create index "idx_wfe_updated_at" to table: "workflow_executions"
CREATE INDEX `idx_wfe_updated_at` ON `workflow_executions` (`updated_at` DESC);
-- Create index "idx_wfe_definition_updated" to table: "workflow_executions"
CREATE INDEX `idx_wfe_definition_updated` ON `workflow_executions` (`definition_id`, `updated_at` DESC);
-- Create index "idx_wfe_definition_revision" to table: "workflow_executions"
CREATE INDEX `idx_wfe_definition_revision` ON `workflow_executions` (`definition_id`, `definition_revision`);
-- Create index "idx_wfe_status_updated" to table: "workflow_executions"
CREATE INDEX `idx_wfe_status_updated` ON `workflow_executions` (`status`, `updated_at` DESC);
-- Create index "idx_wfe_project" to table: "workflow_executions"
CREATE INDEX `idx_wfe_project` ON `workflow_executions` (`project`);
-- Create "subworkflows" table
CREATE TABLE `subworkflows` (
  `subworkflow_id` text NOT NULL,
  `semver` text NOT NULL,
  `name` text NOT NULL,
  `description` text NOT NULL DEFAULT '',
  `workflow_type` text NOT NULL,
  `inputs` text NOT NULL DEFAULT '[]',
  `outputs` text NOT NULL DEFAULT '[]',
  `nodes` text NOT NULL,
  `edges` text NOT NULL,
  `created_by` text NOT NULL,
  `created_at` text NOT NULL,
  PRIMARY KEY (`subworkflow_id`, `semver`),
  CHECK (length(subworkflow_id) > 0),
  CHECK (length(semver) > 0),
  CHECK (length(name) > 0),
  CHECK (workflow_type IN (
        'sequential_pipeline', 'parallel_execution', 'kanban', 'agile_kanban'
    )),
  CHECK (length(created_by) > 0)
);
-- Create index "idx_subworkflows_id" to table: "subworkflows"
CREATE INDEX `idx_subworkflows_id` ON `subworkflows` (`subworkflow_id`);
-- Create index "idx_subworkflows_created_at" to table: "subworkflows"
CREATE INDEX `idx_subworkflows_created_at` ON `subworkflows` (`created_at` DESC);
-- Enable back the enforcement of foreign-keys constraints
PRAGMA foreign_keys = on;
