-- Create "custom_rules" table
CREATE TABLE `custom_rules` (
  `id` text NOT NULL,
  `name` text NOT NULL,
  `description` text NOT NULL,
  `metric_path` text NOT NULL,
  `comparator` text NOT NULL,
  `threshold` real NOT NULL,
  `severity` text NOT NULL,
  `target_altitudes` text NOT NULL,
  `enabled` integer NOT NULL DEFAULT 1,
  `created_at` text NOT NULL,
  `updated_at` text NOT NULL,
  PRIMARY KEY (`id`)
);
-- Create index "custom_rules_name" to table: "custom_rules"
CREATE UNIQUE INDEX `custom_rules_name` ON `custom_rules` (`name`);
