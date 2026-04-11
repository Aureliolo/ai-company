"""SMTP connection type."""

from synthorg.integrations.connections.models import ConnectionType
from synthorg.integrations.errors import InvalidConnectionAuthError
from synthorg.observability import get_logger
from synthorg.observability.events.integrations import (
    CONNECTION_VALIDATION_FAILED,
)

logger = get_logger(__name__)


class SmtpAuthenticator:
    """Validates SMTP connection credentials.

    Required fields: ``host``.
    Optional fields: ``port``, ``username``, ``password``,
    ``use_tls``, ``from_addr``.
    """

    @property
    def connection_type(self) -> ConnectionType:
        """The connection type this authenticator handles."""
        return ConnectionType.SMTP

    def validate_credentials(
        self,
        credentials: dict[str, str],
    ) -> None:
        """Validate credential fields."""
        host = credentials.get("host")
        if not isinstance(host, str) or not host.strip():
            logger.warning(
                CONNECTION_VALIDATION_FAILED,
                connection_type=ConnectionType.SMTP.value,
                field="host",
                error="missing, non-string, or blank",
            )
            msg = "SMTP connection requires a 'host' field"
            raise InvalidConnectionAuthError(msg)
        username = credentials.get("username", "")
        password = credentials.get("password", "")
        # Normalize whitespace so pure-whitespace values do not look
        # valid to ``bool()``.
        username_s = username.strip() if isinstance(username, str) else ""
        password_s = password.strip() if isinstance(password, str) else ""
        if bool(username_s) != bool(password_s):
            logger.warning(
                CONNECTION_VALIDATION_FAILED,
                connection_type=ConnectionType.SMTP.value,
                field="username/password",
                error="must provide both or neither",
            )
            msg = "SMTP connection requires both 'username' and 'password', or neither"
            raise InvalidConnectionAuthError(msg)

    def required_fields(self) -> tuple[str, ...]:
        """Return required credential field names."""
        return ("host",)
