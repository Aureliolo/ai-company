"""OAuth app connection type."""

from synthorg.integrations.connections.models import ConnectionType
from synthorg.integrations.errors import InvalidConnectionAuthError


class OAuthAppAuthenticator:
    """Validates OAuth app registration credentials.

    Required fields: ``client_id``, ``client_secret``,
    ``auth_url``, ``token_url``.
    Optional fields: ``scopes``.
    """

    @property
    def connection_type(self) -> ConnectionType:
        """The connection type this authenticator handles."""
        return ConnectionType.OAUTH_APP

    def validate_credentials(
        self,
        credentials: dict[str, str],
    ) -> None:
        """Validate credential fields."""
        for field in ("client_id", "client_secret", "auth_url", "token_url"):
            if field not in credentials or not credentials[field].strip():
                msg = f"OAuth app connection requires a '{field}' field"
                raise InvalidConnectionAuthError(msg)

    def required_fields(self) -> tuple[str, ...]:
        """Return required credential field names."""
        return ("client_id", "client_secret", "auth_url", "token_url")
