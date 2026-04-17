-- Create "conflict_escalations" table
CREATE TABLE `conflict_escalations` (
  `id` text NOT NULL,
  `conflict_id` text NOT NULL,
  `conflict_json` text NOT NULL,
  `status` text NOT NULL DEFAULT 'pending',
  `created_at` text NOT NULL,
  `expires_at` text NULL,
  `decided_at` text NULL,
  `decided_by` text NULL,
  `decision_json` text NULL,
  PRIMARY KEY (`id`),
  CHECK (length(trim(id)) > 0),
  CHECK (length(trim(conflict_id)) > 0),
  CHECK (
        status IN ('pending', 'decided', 'expired', 'cancelled')
    ),
  CHECK (
        created_at LIKE '%+00:00' OR created_at LIKE '%Z'
    ),
  CHECK (
        expires_at IS NULL OR expires_at LIKE '%+00:00' OR expires_at LIKE '%Z'
    ),
  CHECK (
        decided_at IS NULL OR decided_at LIKE '%+00:00' OR decided_at LIKE '%Z'
    ),
  CHECK (
        (status != 'decided')
        OR (decision_json IS NOT NULL AND decided_at IS NOT NULL AND decided_by IS NOT NULL)
    ),
  CHECK (
        (status != 'pending')
        OR (decision_json IS NULL AND decided_at IS NULL)
    )
);
-- Create index "idx_conflict_escalations_status_created" to table: "conflict_escalations"
CREATE INDEX `idx_conflict_escalations_status_created` ON `conflict_escalations` (`status`, `created_at`);
-- Create index "idx_conflict_escalations_conflict_id" to table: "conflict_escalations"
CREATE INDEX `idx_conflict_escalations_conflict_id` ON `conflict_escalations` (`conflict_id`);
