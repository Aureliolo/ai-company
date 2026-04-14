"""Tests for the outbound A2A client."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from synthorg.a2a.client import A2AClient, A2AClientError


def _mock_catalog(
    *,
    base_url: str = "https://peer.example.com",
    credentials: dict[str, str] | None = None,
    conn_exists: bool = True,
) -> AsyncMock:
    """Create a mock connection catalog."""
    catalog = AsyncMock()
    if conn_exists:
        conn = MagicMock()
        conn.base_url = base_url
        catalog.get = AsyncMock(return_value=conn)
    else:
        catalog.get = AsyncMock(return_value=None)
    catalog.get_credentials = AsyncMock(
        return_value=credentials or {"api_key": "test-key"},
    )
    return catalog


class TestA2AClient:
    """Outbound A2A client tests."""

    @pytest.mark.unit
    async def test_connection_not_found(self) -> None:
        """Raises when peer connection doesn't exist."""
        catalog = _mock_catalog(conn_exists=False)
        client = A2AClient(catalog)
        with pytest.raises(
            A2AClientError,
            match="not found",
        ):
            await client.get_task("missing-peer", "task-1")

    @pytest.mark.unit
    async def test_no_base_url(self) -> None:
        """Raises when peer has no base_url."""
        catalog = _mock_catalog(base_url="")
        client = A2AClient(catalog)
        with pytest.raises(
            A2AClientError,
            match="no base_url",
        ):
            await client.send_message("peer-a", {"test": True})

    @pytest.mark.unit
    async def test_send_message_calls_catalog(self) -> None:
        """send_message looks up the connection."""
        catalog = _mock_catalog()
        client = A2AClient(catalog)
        # Will fail at HTTP level, but we verify catalog lookup
        with pytest.raises(A2AClientError):
            await client.send_message(
                "peer-a",
                {"message": {"parts": []}},
            )
        catalog.get.assert_called_once_with("peer-a")

    @pytest.mark.unit
    async def test_get_task_calls_catalog(self) -> None:
        """get_task looks up the connection."""
        catalog = _mock_catalog()
        client = A2AClient(catalog)
        with pytest.raises(A2AClientError):
            await client.get_task("peer-a", "task-1")
        catalog.get.assert_called_once_with("peer-a")

    @pytest.mark.unit
    async def test_cancel_task_calls_catalog(self) -> None:
        """cancel_task looks up the connection."""
        catalog = _mock_catalog()
        client = A2AClient(catalog)
        with pytest.raises(A2AClientError):
            await client.cancel_task("peer-a", "task-1")
        catalog.get.assert_called_once_with("peer-a")

    @pytest.mark.unit
    async def test_client_error_carries_peer_name(self) -> None:
        """A2AClientError carries the peer name."""
        catalog = _mock_catalog(conn_exists=False)
        client = A2AClient(catalog)
        with pytest.raises(A2AClientError) as exc_info:
            await client.get_task("my-peer", "task-1")
        assert exc_info.value.peer_name == "my-peer"

    @pytest.mark.unit
    def test_client_error_str(self) -> None:
        """A2AClientError has a human-readable string."""
        err = A2AClientError("test error", peer_name="p1")
        assert str(err) == "test error"
        assert err.peer_name == "p1"

    @pytest.mark.unit
    async def test_credentials_pulled(self) -> None:
        """Credentials are pulled from catalog for auth header."""
        catalog = _mock_catalog()
        client = A2AClient(catalog)
        with pytest.raises(A2AClientError):
            await client.send_message("peer-a", {})
        catalog.get_credentials.assert_called_once_with("peer-a")
