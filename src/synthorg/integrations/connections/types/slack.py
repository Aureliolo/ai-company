"""Slack connection type."""

from synthorg.integrations.connections.models import ConnectionType
from synthorg.integrations.errors import InvalidConnectionAuthError


class SlackAuthenticator:
    """Validates Slack connection credentials.

    Required fields: ``token``.
    Optional fields: ``signing_secret`` (for webhook verification),
    ``team_id``.
    """

    @property
    def connection_type(self) -> ConnectionType:
        """The connection type this authenticator handles."""
        return ConnectionType.SLACK

    def validate_credentials(
        self,
        credentials: dict[str, str],
    ) -> None:
        """Validate credential fields."""
        if "token" not in credentials or not credentials["token"].strip():
            msg = "Slack connection requires a 'token' field"
            raise InvalidConnectionAuthError(msg)

    def required_fields(self) -> tuple[str, ...]:
        """Return required credential field names."""
        return ("token",)
