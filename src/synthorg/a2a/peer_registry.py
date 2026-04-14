"""External A2A peer discovery cache.

Stores discovered external A2A peers and their Agent Cards.
Separate from the internal ``AgentRegistryService`` -- this
registry only tracks *external* peers discovered via A2A
federation.
"""

import asyncio
import copy

from synthorg.a2a.models import (
    A2AAgentCard,  # noqa: TC001 -- runtime for type annotation
)
from synthorg.observability import get_logger
from synthorg.observability.events.a2a import (
    A2A_PEER_REGISTERED,
    A2A_PEER_REMOVED,
)

logger = get_logger(__name__)


class PeerRegistry:
    """In-memory cache of discovered external A2A peers.

    Thread-safe via asyncio.Lock.  Peer names are normalized
    to lowercase for case-insensitive lookup.
    """

    __slots__ = ("_lock", "_peers")

    def __init__(self) -> None:
        self._peers: dict[str, A2AAgentCard] = {}
        self._lock = asyncio.Lock()

    async def register(
        self,
        peer_name: str,
        card: A2AAgentCard,
    ) -> None:
        """Register or update an external peer.

        Args:
            peer_name: Peer identifier (case-insensitive).
            card: The peer's Agent Card.
        """
        key = peer_name.lower()
        async with self._lock:
            self._peers[key] = card
        logger.info(
            A2A_PEER_REGISTERED,
            peer_name=peer_name,
            skill_count=len(card.skills),
        )

    async def get(self, peer_name: str) -> A2AAgentCard | None:
        """Look up a peer's Agent Card.

        Args:
            peer_name: Peer identifier (case-insensitive).

        Returns:
            The peer's Agent Card, or ``None`` if not found.
        """
        key = peer_name.lower()
        async with self._lock:
            card = self._peers.get(key)
        return copy.deepcopy(card) if card is not None else None

    async def remove(self, peer_name: str) -> bool:
        """Remove a peer from the registry.

        Args:
            peer_name: Peer identifier (case-insensitive).

        Returns:
            ``True`` if the peer was removed, ``False`` if not found.
        """
        key = peer_name.lower()
        async with self._lock:
            removed = self._peers.pop(key, None)
        if removed is not None:
            logger.info(A2A_PEER_REMOVED, peer_name=peer_name)
            return True
        return False

    async def list_peers(self) -> tuple[str, ...]:
        """Return all registered peer names.

        Returns:
            Tuple of peer names (lowercase).
        """
        async with self._lock:
            return tuple(self._peers.keys())
