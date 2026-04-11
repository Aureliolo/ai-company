"""Generic HTTP connection type."""

from synthorg.integrations.connections.models import ConnectionType
from synthorg.integrations.errors import InvalidConnectionAuthError


class GenericHttpAuthenticator:
    """Validates generic HTTP connection credentials.

    Required fields: ``base_url``.
    Optional fields: ``token``, ``api_key``, ``username``,
    ``password``, ``header_name``, ``header_value``.
    """

    @property
    def connection_type(self) -> ConnectionType:
        """The connection type this authenticator handles."""
        return ConnectionType.GENERIC_HTTP

    def validate_credentials(
        self,
        credentials: dict[str, str],
    ) -> None:
        """Validate credential fields."""
        if "base_url" not in credentials or not credentials["base_url"].strip():
            msg = "Generic HTTP connection requires a 'base_url' field"
            raise InvalidConnectionAuthError(msg)

    def required_fields(self) -> tuple[str, ...]:
        """Return required credential field names."""
        return ("base_url",)
