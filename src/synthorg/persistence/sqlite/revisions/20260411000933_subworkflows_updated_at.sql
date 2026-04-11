-- Add column "updated_at" to table: "subworkflows"
ALTER TABLE `subworkflows` ADD COLUMN `updated_at` text NOT NULL DEFAULT '1970-01-01T00:00:00+00:00';
-- Create index "idx_subworkflows_updated_at" to table: "subworkflows"
CREATE INDEX `idx_subworkflows_updated_at` ON `subworkflows` (`updated_at` DESC);
