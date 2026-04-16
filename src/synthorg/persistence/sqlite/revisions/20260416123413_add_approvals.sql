-- Create "approvals" table
CREATE TABLE `approvals` (
  `id` text NOT NULL,
  `action_type` text NOT NULL,
  `title` text NOT NULL,
  `description` text NOT NULL,
  `requested_by` text NOT NULL,
  `risk_level` text NOT NULL DEFAULT 'medium',
  `status` text NOT NULL DEFAULT 'pending',
  `created_at` text NOT NULL,
  `expires_at` text NULL,
  `decided_at` text NULL,
  `decided_by` text NULL,
  `decision_reason` text NULL,
  `task_id` text NULL,
  `metadata` text NOT NULL DEFAULT '{}',
  PRIMARY KEY (`id`),
  CONSTRAINT `fk_approvals_task_id` FOREIGN KEY (`task_id`) REFERENCES `tasks` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION,
  CHECK (length(trim(id)) > 0),
  CHECK (length(trim(action_type)) > 0),
  CHECK (length(trim(title)) > 0),
  CHECK (length(trim(requested_by)) > 0),
  CHECK (
        risk_level IN ('low', 'medium', 'high', 'critical')
    ),
  CHECK (
        status IN ('pending', 'approved', 'rejected', 'expired')
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
        (decided_at IS NULL AND decided_by IS NULL)
        OR (decided_at IS NOT NULL AND decided_by IS NOT NULL)
    ),
  CHECK (
        status != 'rejected' OR (decision_reason IS NOT NULL AND length(trim(decision_reason)) > 0)
    )
);
-- Create index "idx_approvals_status" to table: "approvals"
CREATE INDEX `idx_approvals_status` ON `approvals` (`status`);
-- Create index "idx_approvals_action_type" to table: "approvals"
CREATE INDEX `idx_approvals_action_type` ON `approvals` (`action_type`);
-- Create index "idx_approvals_risk_level" to table: "approvals"
CREATE INDEX `idx_approvals_risk_level` ON `approvals` (`risk_level`);
