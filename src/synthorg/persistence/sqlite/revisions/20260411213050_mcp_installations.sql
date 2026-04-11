-- Create "mcp_installations" table
CREATE TABLE `mcp_installations` (
  `catalog_entry_id` text NOT NULL,
  `connection_name` text NULL,
  `installed_at` text NOT NULL,
  PRIMARY KEY (`catalog_entry_id`),
  CONSTRAINT `0` FOREIGN KEY (`connection_name`) REFERENCES `connections` (`name`) ON UPDATE NO ACTION ON DELETE SET NULL,
  CHECK (length(catalog_entry_id) > 0)
);
-- Create index "idx_mcp_installations_connection" to table: "mcp_installations"
CREATE INDEX `idx_mcp_installations_connection` ON `mcp_installations` (`connection_name`);
