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
  CHECK (json_valid(conflict_json) AND json_type(conflict_json) = 'object'),
  CHECK (
        decision_json IS NULL
        OR (json_valid(decision_json) AND json_type(decision_json) = 'object')
    ),
  CHECK (
        (status != 'decided')
        OR (
            decision_json IS NOT NULL
            AND decided_at IS NOT NULL
            AND decided_by IS NOT NULL
            AND length(trim(decided_by)) > 0
        )
    ),
  CHECK (
        (status != 'pending')
        OR (decision_json IS NULL AND decided_at IS NULL AND decided_by IS NULL)
    ),
  CHECK (
        (status NOT IN ('expired', 'cancelled'))
        OR (
            decision_json IS NULL
            AND decided_at IS NOT NULL
            AND decided_by IS NOT NULL
            AND length(trim(decided_by)) > 0
        )
    )
);
-- Create index "idx_conflict_escalations_status_created" to table: "conflict_escalations"
CREATE INDEX `idx_conflict_escalations_status_created` ON `conflict_escalations` (`status`, `created_at`);
-- Create index "idx_conflict_escalations_conflict_id" to table: "conflict_escalations"
CREATE INDEX `idx_conflict_escalations_conflict_id` ON `conflict_escalations` (`conflict_id`);
-- Create index "idx_conflict_escalations_status_expires_at" to table: "conflict_escalations"
CREATE INDEX `idx_conflict_escalations_status_expires_at` ON `conflict_escalations` (`status`, `expires_at`);
-- Create index "idx_conflict_escalations_unique_pending_conflict" to table: "conflict_escalations"
CREATE UNIQUE INDEX `idx_conflict_escalations_unique_pending_conflict` ON `conflict_escalations` (`conflict_id`) WHERE status = 'pending';
