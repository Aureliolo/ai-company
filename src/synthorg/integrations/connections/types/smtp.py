"""SMTP connection type."""

from synthorg.integrations.connections.models import ConnectionType
from synthorg.integrations.errors import InvalidConnectionAuthError


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
        if "host" not in credentials or not credentials["host"].strip():
            msg = "SMTP connection requires a 'host' field"
            raise InvalidConnectionAuthError(msg)
        username = credentials.get("username", "")
        password = credentials.get("password", "")
        if bool(username) != bool(password):
            msg = "SMTP connection requires both 'username' and 'password', or neither"
            raise InvalidConnectionAuthError(msg)

    def required_fields(self) -> tuple[str, ...]:
        """Return required credential field names."""
        return ("host",)
