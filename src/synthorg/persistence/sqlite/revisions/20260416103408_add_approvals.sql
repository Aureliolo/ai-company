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
  CHECK (length(id) > 0),
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
    )
);
-- Create index "idx_approvals_status" to table: "approvals"
CREATE INDEX `idx_approvals_status` ON `approvals` (`status`);
-- Create index "idx_approvals_action_type" to table: "approvals"
CREATE INDEX `idx_approvals_action_type` ON `approvals` (`action_type`);
