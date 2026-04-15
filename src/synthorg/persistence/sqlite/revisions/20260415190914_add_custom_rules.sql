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
  PRIMARY KEY (`id`),
  CHECK (length(id) > 0),
  CHECK (length(trim(name)) > 0),
  CHECK (length(trim(description)) > 0),
  CHECK (length(trim(metric_path)) > 0),
  CHECK (length(trim(comparator)) > 0),
  CHECK (length(trim(severity)) > 0),
  CHECK (
        created_at LIKE '%+00:00' OR created_at LIKE '%Z'
    ),
  CHECK (
        updated_at LIKE '%+00:00' OR updated_at LIKE '%Z'
    )
);
-- Create index "custom_rules_name" to table: "custom_rules"
CREATE UNIQUE INDEX `custom_rules_name` ON `custom_rules` (`name`);
