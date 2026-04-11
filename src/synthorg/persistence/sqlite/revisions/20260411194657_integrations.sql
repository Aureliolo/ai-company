-- Create "connection_secrets" table
CREATE TABLE `connection_secrets` (
  `secret_id` text NOT NULL,
  `encrypted_value` blob NOT NULL,
  `key_version` integer NOT NULL DEFAULT 1,
  `created_at` text NOT NULL,
  `rotated_at` text NULL,
  PRIMARY KEY (`secret_id`),
  CHECK (length(secret_id) > 0),
  CHECK (key_version >= 1)
);
-- Create "connections" table
CREATE TABLE `connections` (
  `name` text NOT NULL,
  `connection_type` text NOT NULL,
  `auth_method` text NOT NULL,
  `base_url` text NULL,
  `secret_refs_json` text NOT NULL DEFAULT '[]',
  `rate_limit_rpm` integer NOT NULL DEFAULT 0,
  `rate_limit_concurrent` integer NOT NULL DEFAULT 0,
  `health_check_enabled` integer NOT NULL DEFAULT 1,
  `health_status` text NOT NULL DEFAULT 'unknown',
  `last_health_check_at` text NULL,
  `metadata_json` text NOT NULL DEFAULT '{}',
  `created_at` text NOT NULL,
  `updated_at` text NOT NULL,
  PRIMARY KEY (`name`),
  CHECK (length(name) > 0),
  CHECK (
        connection_type IN (
            'github', 'slack', 'smtp', 'database',
            'generic_http', 'oauth_app'
        )
    ),
  CHECK (
        auth_method IN (
            'api_key', 'oauth2', 'basic_auth',
            'bearer_token', 'custom'
        )
    ),
  CHECK (rate_limit_rpm >= 0),
  CHECK (rate_limit_concurrent >= 0),
  CHECK (health_check_enabled IN (0, 1)),
  CHECK (
            health_status IN ('healthy', 'degraded', 'unhealthy', 'unknown')
        )
);
-- Create index "idx_connections_type" to table: "connections"
CREATE INDEX `idx_connections_type` ON `connections` (`connection_type`);
-- Create "oauth_states" table
CREATE TABLE `oauth_states` (
  `state_token` text NOT NULL,
  `connection_name` text NOT NULL,
  `pkce_verifier` text NULL,
  `scopes_requested` text NOT NULL DEFAULT '',
  `redirect_uri` text NOT NULL DEFAULT '',
  `created_at` text NOT NULL,
  `expires_at` text NOT NULL,
  PRIMARY KEY (`state_token`),
  CONSTRAINT `0` FOREIGN KEY (`connection_name`) REFERENCES `connections` (`name`) ON UPDATE NO ACTION ON DELETE CASCADE
);
-- Create index "idx_oauth_states_expires" to table: "oauth_states"
CREATE INDEX `idx_oauth_states_expires` ON `oauth_states` (`expires_at`);
-- Create index "idx_oauth_states_connection" to table: "oauth_states"
CREATE INDEX `idx_oauth_states_connection` ON `oauth_states` (`connection_name`);
-- Create "webhook_receipts" table
CREATE TABLE `webhook_receipts` (
  `id` text NOT NULL,
  `connection_name` text NOT NULL,
  `event_type` text NOT NULL DEFAULT '',
  `status` text NOT NULL DEFAULT 'received',
  `received_at` text NOT NULL,
  `processed_at` text NULL,
  `payload_json` text NOT NULL DEFAULT '{}',
  `error` text NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `0` FOREIGN KEY (`connection_name`) REFERENCES `connections` (`name`) ON UPDATE NO ACTION ON DELETE CASCADE
);
-- Create index "idx_webhook_receipts_conn_received" to table: "webhook_receipts"
CREATE INDEX `idx_webhook_receipts_conn_received` ON `webhook_receipts` (`connection_name`, `received_at` DESC);
