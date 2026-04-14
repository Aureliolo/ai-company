"""A2A peer connection type authenticator."""

from synthorg.integrations.connections.models import ConnectionType
from synthorg.integrations.errors import InvalidConnectionAuthError
from synthorg.observability import get_logger
from synthorg.observability.events.integrations import (
    CONNECTION_VALIDATION_FAILED,
)

logger = get_logger(__name__)


class A2APeerAuthenticator:
    """Validates A2A peer connection credentials.

    Required fields: ``api_key``.
    Optional fields: ``signing_secret`` (for push notification
    verification).
    """

    @property
    def connection_type(self) -> ConnectionType:
        """The connection type this authenticator handles."""
        return ConnectionType.A2A_PEER

    def validate_credentials(
        self,
        credentials: dict[str, str],
    ) -> None:
        """Validate that the API key is present."""
        api_key = credentials.get("api_key")
        if not isinstance(api_key, str) or not api_key.strip():
            logger.warning(
                CONNECTION_VALIDATION_FAILED,
                connection_type=ConnectionType.A2A_PEER.value,
                field="api_key",
                error="missing, non-string, or blank",
            )
            msg = "A2A peer connection requires an 'api_key' field"
            raise InvalidConnectionAuthError(msg)

    def required_fields(self) -> tuple[str, ...]:
        """Return required credential field names."""
        return ("api_key",)
