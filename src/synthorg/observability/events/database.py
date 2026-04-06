"""Event constants for database tool operations."""

from typing import Final

DB_QUERY_START: Final[str] = "db.query.start"
DB_QUERY_SUCCESS: Final[str] = "db.query.success"
DB_QUERY_FAILED: Final[str] = "db.query.failed"
DB_QUERY_TIMEOUT: Final[str] = "db.query.timeout"
DB_SCHEMA_INSPECT_START: Final[str] = "db.schema.inspect.start"
DB_SCHEMA_INSPECT_SUCCESS: Final[str] = "db.schema.inspect.success"
DB_SCHEMA_INSPECT_FAILED: Final[str] = "db.schema.inspect.failed"
DB_WRITE_BLOCKED: Final[str] = "db.write.blocked"
DB_CONNECTION_OPENED: Final[str] = "db.connection.opened"
DB_CONNECTION_FAILED: Final[str] = "db.connection.failed"
DB_CONNECTION_CLOSED: Final[str] = "db.connection.closed"
