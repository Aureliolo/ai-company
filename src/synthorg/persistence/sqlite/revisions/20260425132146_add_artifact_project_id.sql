-- Add column "project_id" to table: "artifacts"
ALTER TABLE `artifacts` ADD COLUMN `project_id` text NULL;
-- Create index "idx_artifacts_project_id" to table: "artifacts"
CREATE INDEX `idx_artifacts_project_id` ON `artifacts` (`project_id`);
