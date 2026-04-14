"""A2A inbound request security validation.

Validates peer allowlist membership, payload size limits, and
delegates auth to the connection catalog.  SSRF validation for
outbound calls is handled by the existing
``synthorg.tools.network_validator`` module.
"""

from synthorg.observability import get_logger
from synthorg.observability.events.a2a import (
    A2A_INBOUND_PAYLOAD_TOO_LARGE,
    A2A_INBOUND_PEER_NOT_ALLOWED,
)

logger = get_logger(__name__)


def validate_peer(
    peer_name: str,
    allowed_peers: tuple[str, ...],
) -> bool:
    """Check whether a peer is on the allowlist.

    Args:
        peer_name: Name of the requesting peer.
        allowed_peers: Tuple of allowed peer names.

    Returns:
        ``True`` if the peer is allowed.
    """
    if peer_name not in allowed_peers:
        logger.warning(
            A2A_INBOUND_PEER_NOT_ALLOWED,
            peer_name=peer_name,
        )
        return False
    return True


def validate_payload_size(
    body: bytes,
    max_bytes: int,
) -> bool:
    """Check whether the request body exceeds the size limit.

    Args:
        body: Raw request body.
        max_bytes: Maximum allowed size in bytes.

    Returns:
        ``True`` if the payload is within limits.
    """
    if len(body) > max_bytes:
        logger.warning(
            A2A_INBOUND_PAYLOAD_TOO_LARGE,
            body_size=len(body),
            max_bytes=max_bytes,
        )
        return False
    return True
