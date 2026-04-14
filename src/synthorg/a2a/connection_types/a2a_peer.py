"""A2A peer connection type registration.

Provides the ``A2A_PEER`` connection type's webhook signature
verifier registration for the unified webhook receiver.
"""

from synthorg.a2a.push_verifier import A2APushVerifier
from synthorg.integrations.connections.models import ConnectionType
from synthorg.integrations.webhooks.verifiers.protocol import (
    SignatureVerifier,  # noqa: TC001
)


def get_a2a_push_verifier(
    clock_skew_seconds: int = 300,
) -> SignatureVerifier:
    """Create an A2A push notification verifier.

    Args:
        clock_skew_seconds: Clock skew tolerance.

    Returns:
        A ``SignatureVerifier`` instance for A2A push events.
    """
    return A2APushVerifier(clock_skew_seconds=clock_skew_seconds)


# Connection type constant for external reference
A2A_PEER_TYPE = ConnectionType.A2A_PEER
