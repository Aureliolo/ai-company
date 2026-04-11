"""Database connection type."""

from synthorg.integrations.connections.models import ConnectionType
from synthorg.integrations.errors import InvalidConnectionAuthError
from synthorg.observability import get_logger
from synthorg.observability.events.integrations import (
    CONNECTION_VALIDATION_FAILED,
)

logger = get_logger(__name__)

_VALID_DIALECTS = frozenset({"postgres", "mysql", "sqlite", "mariadb"})


class DatabaseAuthenticator:
    """Validates database connection credentials.

    Required fields: ``dialect``, ``host`` (except sqlite),
    ``database``.
    Optional fields: ``port``, ``username``, ``password``.
    """

    @property
    def connection_type(self) -> ConnectionType:
        """The connection type this authenticator handles."""
        return ConnectionType.DATABASE

    def validate_credentials(
        self,
        credentials: dict[str, str],
    ) -> None:
        """Validate credential fields."""
        dialect = credentials.get("dialect", "").strip()
        if not dialect:
            logger.warning(
                CONNECTION_VALIDATION_FAILED,
                connection_type=ConnectionType.DATABASE.value,
                field="dialect",
                error="missing or blank",
            )
            msg = "Database connection requires a 'dialect' field"
            raise InvalidConnectionAuthError(msg)
        if dialect not in _VALID_DIALECTS:
            logger.warning(
                CONNECTION_VALIDATION_FAILED,
                connection_type=ConnectionType.DATABASE.value,
                field="dialect",
                error="unsupported dialect",
                dialect=dialect,
                valid=sorted(_VALID_DIALECTS),
            )
            msg = f"Unknown dialect '{dialect}'; supported: {sorted(_VALID_DIALECTS)}"
            raise InvalidConnectionAuthError(msg)
        if dialect != "sqlite" and (
            "host" not in credentials or not credentials["host"].strip()
        ):
            logger.warning(
                CONNECTION_VALIDATION_FAILED,
                connection_type=ConnectionType.DATABASE.value,
                field="host",
                error="missing or blank",
                dialect=dialect,
            )
            msg = f"Database dialect '{dialect}' requires a 'host' field"
            raise InvalidConnectionAuthError(msg)
        if "database" not in credentials or not credentials["database"].strip():
            logger.warning(
                CONNECTION_VALIDATION_FAILED,
                connection_type=ConnectionType.DATABASE.value,
                field="database",
                error="missing or blank",
            )
            msg = "Database connection requires a 'database' field"
            raise InvalidConnectionAuthError(msg)

    def required_fields(self) -> tuple[str, ...]:
        """Return required credential field names."""
        return ("dialect", "database")
