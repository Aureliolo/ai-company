"""Signature verifier factory."""

from synthorg.integrations.connections.models import ConnectionType
from synthorg.integrations.webhooks.verifiers.generic_hmac import (
    GenericHmacVerifier,
)
from synthorg.integrations.webhooks.verifiers.github_hmac import (
    GitHubHmacVerifier,
)
from synthorg.integrations.webhooks.verifiers.protocol import (
    SignatureVerifier,  # noqa: TC001
)
from synthorg.integrations.webhooks.verifiers.slack_signing import (
    SlackSigningVerifier,
)


def get_verifier(connection_type: ConnectionType) -> SignatureVerifier:
    """Return the appropriate verifier for a connection type.

    Args:
        connection_type: The connection type.

    Returns:
        A ``SignatureVerifier`` instance.
    """
    if connection_type == ConnectionType.GITHUB:
        return GitHubHmacVerifier()
    if connection_type == ConnectionType.SLACK:
        return SlackSigningVerifier()
    return GenericHmacVerifier()
