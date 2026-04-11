"""Optional JSONB-native query extension for Postgres backends.

Defines the ``JsonbQueryCapability`` runtime-checkable protocol that
Postgres repositories may implement.  SQLite repositories do not
implement this protocol; call sites check with ``isinstance()``
before using JSONB-specific query methods.

All query methods use parameterised SQL internally to prevent
injection.  Path expressions are validated against a strict
allowlist before being used in queries.
"""

import re
from typing import Any, Protocol, runtime_checkable

from synthorg.observability import get_logger

logger = get_logger(__name__)

# Path validation: alphanumeric segments joined by dots, max depth 5.
_PATH_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*){0,4}$")
_MAX_PATH_LENGTH = 128


def validate_jsonb_path(path: str) -> None:
    """Validate a JSONB path expression for safe use in queries.

    Only allows dot-separated alphanumeric/underscore segments
    with a maximum depth of 5 and total length of 128 characters.

    Args:
        path: The path expression to validate.

    Raises:
        ValueError: If the path is invalid or potentially unsafe.
    """
    if not path or len(path) > _MAX_PATH_LENGTH:
        msg = f"JSONB path must be 1-{_MAX_PATH_LENGTH} characters, got {len(path)}"
        raise ValueError(msg)
    if not _PATH_PATTERN.match(path):
        msg = (
            f"Invalid JSONB path {path!r}: must be dot-separated "
            "alphanumeric/underscore segments (max depth 5)"
        )
        raise ValueError(msg)


@runtime_checkable
class JsonbQueryCapability(Protocol):
    """Optional JSONB-native query extension for Postgres backends.

    Repositories implementing this protocol support GIN-indexed
    queries on JSONB columns using Postgres-native operators.

    Call sites should check ``isinstance(repo, JsonbQueryCapability)``
    before invoking these methods.  Non-Postgres backends (SQLite)
    do not implement this protocol.
    """

    async def query_jsonb_contains(  # noqa: PLR0913
        self,
        column: str,
        value: dict[str, Any] | list[Any],
        *,
        since: Any | None = None,
        until: Any | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[tuple[Any, ...], int]:
        """Query rows where a JSONB column contains the given value.

        Uses the Postgres ``@>`` containment operator, which is
        GIN-indexed for efficient lookups.

        Args:
            column: JSONB column name to query.
            value: JSON value that the column must contain.
            since: Only return rows at or after this timestamp.
            until: Only return rows at or before this timestamp.
            limit: Maximum rows to return.
            offset: Number of rows to skip.

        Returns:
            Tuple of (matching rows, total count before pagination).
        """
        ...

    async def query_jsonb_key_exists(  # noqa: PLR0913
        self,
        column: str,
        key: str,
        *,
        since: Any | None = None,
        until: Any | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[tuple[Any, ...], int]:
        """Query rows where a JSONB column has the given top-level key.

        Uses the Postgres ``?`` existence operator, which is
        GIN-indexed for efficient lookups.

        Args:
            column: JSONB column name to query.
            key: Top-level key that must exist in the JSONB value.
            since: Only return rows at or after this timestamp.
            until: Only return rows at or before this timestamp.
            limit: Maximum rows to return.
            offset: Number of rows to skip.

        Returns:
            Tuple of (matching rows, total count before pagination).
        """
        ...

    async def query_jsonb_path_equals(  # noqa: PLR0913
        self,
        column: str,
        path: str,
        value: str,
        *,
        since: Any | None = None,
        until: Any | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[tuple[Any, ...], int]:
        """Query rows where a JSONB path extracts to a specific value.

        Uses the Postgres ``->>`` path extraction operator.  The
        *path* argument is validated against a strict allowlist
        before use.

        Args:
            column: JSONB column name to query.
            path: Dot-separated path within the JSONB value.
            value: Expected string value at the path.
            since: Only return rows at or after this timestamp.
            until: Only return rows at or before this timestamp.
            limit: Maximum rows to return.
            offset: Number of rows to skip.

        Returns:
            Tuple of (matching rows, total count before pagination).
        """
        ...
