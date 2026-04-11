-- Create "connection_secrets" table
CREATE TABLE "connection_secrets" (
  "secret_id" text NOT NULL,
  "encrypted_value" bytea NOT NULL,
  "key_version" integer NOT NULL DEFAULT 1,
  "created_at" timestamptz NOT NULL,
  "rotated_at" timestamptz NULL,
  PRIMARY KEY ("secret_id"),
  CONSTRAINT "connection_secrets_key_version_check" CHECK (key_version >= 1),
  CONSTRAINT "connection_secrets_secret_id_check" CHECK (length(secret_id) > 0)
);
-- Create "connections" table
CREATE TABLE "connections" (
  "name" text NOT NULL,
  "connection_type" text NOT NULL,
  "auth_method" text NOT NULL,
  "base_url" text NULL,
  "secret_refs_json" jsonb NOT NULL DEFAULT '[]',
  "rate_limit_rpm" integer NOT NULL DEFAULT 0,
  "rate_limit_concurrent" integer NOT NULL DEFAULT 0,
  "health_check_enabled" boolean NOT NULL DEFAULT true,
  "health_status" text NOT NULL DEFAULT 'unknown',
  "last_health_check_at" timestamptz NULL,
  "metadata_json" jsonb NOT NULL DEFAULT '{}',
  "created_at" timestamptz NOT NULL,
  "updated_at" timestamptz NOT NULL,
  PRIMARY KEY ("name"),
  CONSTRAINT "connections_auth_method_check" CHECK (auth_method = ANY (ARRAY['api_key'::text, 'oauth2'::text, 'basic_auth'::text, 'bearer_token'::text, 'custom'::text])),
  CONSTRAINT "connections_connection_type_check" CHECK (connection_type = ANY (ARRAY['github'::text, 'slack'::text, 'smtp'::text, 'database'::text, 'generic_http'::text, 'oauth_app'::text])),
  CONSTRAINT "connections_health_status_check" CHECK (health_status = ANY (ARRAY['healthy'::text, 'degraded'::text, 'unhealthy'::text, 'unknown'::text])),
  CONSTRAINT "connections_name_check" CHECK (length(name) > 0),
  CONSTRAINT "connections_rate_limit_concurrent_check" CHECK (rate_limit_concurrent >= 0),
  CONSTRAINT "connections_rate_limit_rpm_check" CHECK (rate_limit_rpm >= 0)
);
-- Create index "idx_connections_type" to table: "connections"
CREATE INDEX "idx_connections_type" ON "connections" ("connection_type");
-- Create "oauth_states" table
CREATE TABLE "oauth_states" (
  "state_token" text NOT NULL,
  "connection_name" text NOT NULL,
  "pkce_verifier" text NULL,
  "scopes_requested" text NOT NULL DEFAULT '',
  "redirect_uri" text NOT NULL DEFAULT '',
  "created_at" timestamptz NOT NULL,
  "expires_at" timestamptz NOT NULL,
  PRIMARY KEY ("state_token"),
  CONSTRAINT "oauth_states_connection_name_fkey" FOREIGN KEY ("connection_name") REFERENCES "connections" ("name") ON UPDATE NO ACTION ON DELETE CASCADE
);
-- Create index "idx_oauth_states_connection" to table: "oauth_states"
CREATE INDEX "idx_oauth_states_connection" ON "oauth_states" ("connection_name");
-- Create index "idx_oauth_states_expires" to table: "oauth_states"
CREATE INDEX "idx_oauth_states_expires" ON "oauth_states" ("expires_at");
-- Create "webhook_receipts" table
CREATE TABLE "webhook_receipts" (
  "id" text NOT NULL,
  "connection_name" text NOT NULL,
  "event_type" text NOT NULL DEFAULT '',
  "status" text NOT NULL DEFAULT 'received',
  "received_at" timestamptz NOT NULL,
  "processed_at" timestamptz NULL,
  "payload_json" jsonb NOT NULL DEFAULT '{}',
  "error" text NULL,
  PRIMARY KEY ("id"),
  CONSTRAINT "webhook_receipts_connection_name_fkey" FOREIGN KEY ("connection_name") REFERENCES "connections" ("name") ON UPDATE NO ACTION ON DELETE CASCADE
);
-- Create index "idx_webhook_receipts_conn_received" to table: "webhook_receipts"
CREATE INDEX "idx_webhook_receipts_conn_received" ON "webhook_receipts" ("connection_name", "received_at" DESC);
