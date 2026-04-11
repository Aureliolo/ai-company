"""OAuth app connection type."""

from urllib.parse import urlparse

from synthorg.integrations.connections.models import ConnectionType
from synthorg.integrations.errors import InvalidConnectionAuthError
from synthorg.observability import get_logger
from synthorg.observability.events.integrations import (
    CONNECTION_VALIDATION_FAILED,
)

logger = get_logger(__name__)

_URL_FIELDS = ("auth_url", "token_url")
_ALLOWED_SCHEMES = ("http", "https")


class OAuthAppAuthenticator:
    """Validates OAuth app registration credentials.

    Required fields: ``client_id``, ``client_secret``,
    ``auth_url``, ``token_url``. Optional fields: ``scopes``.
    URL fields must have an http/https scheme and a non-empty
    hostname.
    """

    @property
    def connection_type(self) -> ConnectionType:
        """The connection type this authenticator handles."""
        return ConnectionType.OAUTH_APP

    def validate_credentials(
        self,
        credentials: dict[str, str],
    ) -> None:
        """Validate credential fields (presence + URL format)."""
        for field in ("client_id", "client_secret", "auth_url", "token_url"):
            value = credentials.get(field)
            if not isinstance(value, str) or not value.strip():
                logger.warning(
                    CONNECTION_VALIDATION_FAILED,
                    connection_type=str(ConnectionType.OAUTH_APP),
                    field=field,
                    error="missing or blank",
                )
                msg = f"OAuth app connection requires a '{field}' field"
                raise InvalidConnectionAuthError(msg)

        for url_field in _URL_FIELDS:
            parsed = urlparse(credentials[url_field].strip())
            if parsed.scheme not in _ALLOWED_SCHEMES or not parsed.netloc:
                logger.warning(
                    CONNECTION_VALIDATION_FAILED,
                    connection_type=str(ConnectionType.OAUTH_APP),
                    field=url_field,
                    error=f"invalid URL scheme/host: {parsed.scheme}",
                )
                msg = (
                    f"OAuth app '{url_field}' must be an http or https URL "
                    "with a valid hostname"
                )
                raise InvalidConnectionAuthError(msg)

    def required_fields(self) -> tuple[str, ...]:
        """Return required credential field names."""
        return ("client_id", "client_secret", "auth_url", "token_url")
