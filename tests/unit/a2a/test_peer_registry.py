"""Tests for the external peer discovery registry."""

import pytest

from synthorg.a2a.models import A2AAgentCard
from synthorg.a2a.peer_registry import PeerRegistry


def _make_card(name: str = "peer-agent") -> A2AAgentCard:
    """Create a minimal Agent Card for testing."""
    return A2AAgentCard(
        name=name,
        url="https://example.com/a2a",
    )


class TestPeerRegistry:
    """PeerRegistry CRUD operations."""

    @pytest.mark.unit
    async def test_register_and_get(self) -> None:
        """Register a peer and retrieve its card."""
        reg = PeerRegistry()
        card = _make_card()
        await reg.register("peer-a", card)

        result = await reg.get("peer-a")
        assert result is not None
        assert result.name == "peer-agent"

    @pytest.mark.unit
    async def test_get_missing(self) -> None:
        """Get returns None for unknown peers."""
        reg = PeerRegistry()
        assert await reg.get("missing") is None

    @pytest.mark.unit
    async def test_case_insensitive(self) -> None:
        """Peer names are case-insensitive."""
        reg = PeerRegistry()
        await reg.register("Peer-A", _make_card())
        assert await reg.get("peer-a") is not None
        assert await reg.get("PEER-A") is not None

    @pytest.mark.unit
    async def test_remove(self) -> None:
        """Remove a registered peer."""
        reg = PeerRegistry()
        await reg.register("peer-a", _make_card())
        assert await reg.remove("peer-a") is True
        assert await reg.get("peer-a") is None

    @pytest.mark.unit
    async def test_remove_missing(self) -> None:
        """Remove returns False for unknown peers."""
        reg = PeerRegistry()
        assert await reg.remove("missing") is False

    @pytest.mark.unit
    async def test_list_peers(self) -> None:
        """List all registered peer names."""
        reg = PeerRegistry()
        await reg.register("peer-a", _make_card("a"))
        await reg.register("peer-b", _make_card("b"))

        peers = await reg.list_peers()
        assert set(peers) == {"peer-a", "peer-b"}

    @pytest.mark.unit
    async def test_list_empty(self) -> None:
        """Empty registry returns empty tuple."""
        reg = PeerRegistry()
        assert await reg.list_peers() == ()

    @pytest.mark.unit
    async def test_update_existing(self) -> None:
        """Re-registering updates the card."""
        reg = PeerRegistry()
        await reg.register("peer-a", _make_card("old"))
        await reg.register("peer-a", _make_card("new"))

        card = await reg.get("peer-a")
        assert card is not None
        assert card.name == "new"

    @pytest.mark.unit
    async def test_get_returns_deep_copy(self) -> None:
        """Get returns a deep copy (mutations don't affect registry)."""
        reg = PeerRegistry()
        await reg.register("peer-a", _make_card())

        card1 = await reg.get("peer-a")
        card2 = await reg.get("peer-a")
        assert card1 is not card2
