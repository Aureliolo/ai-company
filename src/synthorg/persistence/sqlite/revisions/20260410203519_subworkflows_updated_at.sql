-- Add column "updated_at" to table: "subworkflows"
ALTER TABLE `subworkflows` ADD COLUMN `updated_at` text NOT NULL;
-- Create index "idx_subworkflows_updated_at" to table: "subworkflows"
CREATE INDEX `idx_subworkflows_updated_at` ON `subworkflows` (`updated_at` DESC);
