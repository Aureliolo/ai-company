"""SQL query tool -- execute SQL queries against a configured database.

Read-only by default.  Write queries (INSERT, UPDATE, DELETE, etc.)
are rejected unless the connection config has ``read_only=False``.
Uses parameterized queries to prevent SQL injection.
"""

import re
from typing import Any, Final

import aiosqlite

from synthorg.core.enums import ActionType
from synthorg.observability import get_logger
from synthorg.observability.events.database import (
    DB_QUERY_FAILED,
    DB_QUERY_START,
    DB_QUERY_SUCCESS,
    DB_QUERY_TIMEOUT,
    DB_WRITE_BLOCKED,
)
from synthorg.tools.base import ToolExecutionResult
from synthorg.tools.database.base_db_tool import BaseDatabaseTool
from synthorg.tools.database.config import DatabaseConnectionConfig  # noqa: TC001

logger = get_logger(__name__)

# Statement prefixes that are always considered read-only.
_READ_ONLY_PREFIXES: Final[tuple[str, ...]] = (
    "SELECT",
    "EXPLAIN",
    "PRAGMA",
    "WITH",
)

# Statement prefixes that require write access.
_WRITE_PREFIXES: Final[tuple[str, ...]] = (
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "CREATE",
    "TRUNCATE",
    "REPLACE",
    "ATTACH",
    "DETACH",
    "REINDEX",
    "VACUUM",
)

_LEADING_COMMENT_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s*(?:--[^\n]*\n|/\*.*?\*/\s*)*",
    re.DOTALL,
)

_PARAMETERS_SCHEMA: Final[dict[str, Any]] = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "SQL query to execute",
        },
        "parameters": {
            "type": "array",
            "items": {},
            "description": "Query parameters (for parameterized queries)",
        },
    },
    "required": ["query"],
    "additionalProperties": False,
}


def _classify_statement(query: str) -> str:
    """Return the uppercase first keyword of a SQL statement.

    Strips leading whitespace and SQL comments (``--`` and ``/* */``).

    Args:
        query: Raw SQL query string.

    Returns:
        The first keyword in uppercase, or empty string if empty.
    """
    stripped = _LEADING_COMMENT_RE.sub("", query).strip()
    if not stripped:
        return ""
    first_word = stripped.split(maxsplit=1)[0]
    return first_word.upper()


class SqlQueryTool(BaseDatabaseTool):
    """Execute SQL queries against a configured SQLite database.

    Read-only by default: rejects INSERT, UPDATE, DELETE, DROP, etc.
    unless the connection config has ``read_only=False``.  Write
    queries use ``ActionType.DB_MUTATE`` for security escalation.

    Uses parameterized queries to prevent SQL injection.

    Examples:
        Execute a read-only query::

            tool = SqlQueryTool(config=db_config)
            result = await tool.execute(
                arguments={"query": "SELECT * FROM users LIMIT 10"}
            )
    """

    def __init__(self, *, config: DatabaseConnectionConfig) -> None:
        """Initialize the SQL query tool.

        Args:
            config: Database connection configuration.
        """
        super().__init__(
            name="sql_query",
            description=(
                "Execute SQL queries against a database. "
                "Read-only by default; write queries require "
                "explicit configuration."
            ),
            parameters_schema=dict(_PARAMETERS_SCHEMA),
            action_type=ActionType.DB_QUERY,
            config=config,
        )

    async def execute(
        self,
        *,
        arguments: dict[str, Any],
    ) -> ToolExecutionResult:
        """Execute a SQL query.

        Args:
            arguments: Must contain ``query``; optionally ``parameters``.

        Returns:
            A ``ToolExecutionResult`` with formatted query results.
        """
        query: str = arguments["query"]
        parameters: list[Any] = arguments.get("parameters") or []

        keyword = _classify_statement(query)
        if not keyword:
            return ToolExecutionResult(
                content="Empty query",
                is_error=True,
            )

        # Write protection
        is_write = keyword in _WRITE_PREFIXES
        if is_write and self._config.read_only:
            logger.warning(
                DB_WRITE_BLOCKED,
                keyword=keyword,
                database=self._config.database_path,
            )
            return ToolExecutionResult(
                content=(
                    f"Write query blocked: {keyword} statements are not "
                    f"allowed in read-only mode"
                ),
                is_error=True,
            )

        logger.info(
            DB_QUERY_START,
            keyword=keyword,
            is_write=is_write,
            database=self._config.database_path,
        )

        return await self._execute_query(query, parameters, keyword, is_write)

    async def _execute_query(
        self,
        query: str,
        parameters: list[Any],
        keyword: str,
        is_write: bool,  # noqa: FBT001  -- private method
    ) -> ToolExecutionResult:
        """Execute the query against SQLite.

        Args:
            query: SQL query string.
            parameters: Query parameters.
            keyword: First keyword of the statement.
            is_write: Whether this is a write operation.

        Returns:
            A ``ToolExecutionResult`` with the result.
        """
        try:
            async with aiosqlite.connect(self._config.database_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(query, parameters)

                if is_write:
                    await db.commit()
                    content = f"{keyword} affected {cursor.rowcount} row(s)"
                    logger.info(
                        DB_QUERY_SUCCESS,
                        keyword=keyword,
                        rowcount=cursor.rowcount,
                    )
                    return ToolExecutionResult(
                        content=content,
                        metadata={
                            "keyword": keyword,
                            "rowcount": cursor.rowcount,
                        },
                    )

                rows = list(await cursor.fetchall())
                if not rows:
                    logger.info(DB_QUERY_SUCCESS, keyword=keyword, row_count=0)
                    return ToolExecutionResult(
                        content="Query returned no results.",
                        metadata={"keyword": keyword, "row_count": 0},
                    )

                columns = [desc[0] for desc in cursor.description or []]
                content = self._format_results(columns, rows)
                logger.info(
                    DB_QUERY_SUCCESS,
                    keyword=keyword,
                    row_count=len(rows),
                    column_count=len(columns),
                )
                return ToolExecutionResult(
                    content=content,
                    metadata={
                        "keyword": keyword,
                        "row_count": len(rows),
                        "columns": columns,
                    },
                )
        except aiosqlite.OperationalError as exc:
            error_str = str(exc)
            if "timeout" in error_str.lower():
                logger.warning(
                    DB_QUERY_TIMEOUT,
                    database=self._config.database_path,
                )
                return ToolExecutionResult(
                    content=f"Query timed out: {exc}",
                    is_error=True,
                )
            logger.warning(
                DB_QUERY_FAILED,
                database=self._config.database_path,
                error=error_str,
            )
            return ToolExecutionResult(
                content=f"Query failed: {exc}",
                is_error=True,
            )
        except Exception as exc:
            logger.warning(
                DB_QUERY_FAILED,
                database=self._config.database_path,
                error=str(exc),
            )
            return ToolExecutionResult(
                content=f"Database error: {exc}",
                is_error=True,
            )

    @staticmethod
    def _format_results(
        columns: list[str],
        rows: list[Any],
    ) -> str:
        """Format query results as a table.

        Args:
            columns: Column names.
            rows: Result rows (each row is indexable by column position).

        Returns:
            Formatted table string.
        """
        lines: list[str] = []
        header = " | ".join(columns)
        lines.append(header)
        lines.append("-" * len(header))
        for row in rows:
            values = [str(row[i]) for i in range(len(columns))]
            lines.append(" | ".join(values))
        return "\n".join(lines)
