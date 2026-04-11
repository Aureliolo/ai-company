-- Create "mcp_installations" table
CREATE TABLE "mcp_installations" (
  "catalog_entry_id" text NOT NULL,
  "connection_name" text NULL,
  "installed_at" timestamptz NOT NULL,
  PRIMARY KEY ("catalog_entry_id"),
  CONSTRAINT "mcp_installations_connection_name_fkey" FOREIGN KEY ("connection_name") REFERENCES "connections" ("name") ON UPDATE NO ACTION ON DELETE SET NULL,
  CONSTRAINT "mcp_installations_catalog_entry_id_check" CHECK (length(catalog_entry_id) > 0)
);
-- Create index "idx_mcp_installations_connection" to table: "mcp_installations"
CREATE INDEX "idx_mcp_installations_connection" ON "mcp_installations" ("connection_name");
