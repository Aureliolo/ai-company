-- Create index "idx_cost_records_timestamp" to table: "cost_records"
CREATE INDEX `idx_cost_records_timestamp` ON `cost_records` (`timestamp` DESC);
-- Create index "idx_messages_sender" to table: "messages"
CREATE INDEX `idx_messages_sender` ON `messages` (`sender`);
-- Create index "idx_messages_to" to table: "messages"
CREATE INDEX `idx_messages_to` ON `messages` (`to`);
-- Create index "idx_custom_rules_enabled" to table: "custom_rules"
CREATE INDEX `idx_custom_rules_enabled` ON `custom_rules` (`enabled`);
-- Create index "idx_approvals_requested_by_status" to table: "approvals"
CREATE INDEX `idx_approvals_requested_by_status` ON `approvals` (`requested_by`, `status`);
-- Create index "idx_approvals_status_expires_at" to table: "approvals"
CREATE INDEX `idx_approvals_status_expires_at` ON `approvals` (`status`, `expires_at`);
