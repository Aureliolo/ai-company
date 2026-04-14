"""Tests for the outbound A2A client."""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
import respx

from synthorg.a2a.client import A2AClient, A2AClientError
from synthorg.a2a.models import A2ATaskState


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


def _make_client(
    catalog: AsyncMock | None = None,
) -> A2AClient:
    """Create a client with an injected httpx client (no real I/O)."""
    return A2AClient(
        catalog or _mock_catalog(),
        http_client=httpx.AsyncClient(),
    )


class TestA2AClient:
    """Outbound A2A client tests."""

    @pytest.mark.unit
    async def test_connection_not_found(self) -> None:
        """Raises when peer connection doesn't exist."""
        catalog = _mock_catalog(conn_exists=False)
        client = _make_client(catalog)
        with pytest.raises(A2AClientError, match="not found"):
            await client.get_task("missing-peer", "task-1")

    @pytest.mark.unit
    async def test_no_base_url(self) -> None:
        """Raises when peer has no base_url."""
        catalog = _mock_catalog(base_url="")
        client = _make_client(catalog)
        with pytest.raises(A2AClientError, match="no base_url"):
            await client.send_message("peer-a", {"test": True})

    @pytest.mark.unit
    @respx.mock
    async def test_send_message_success(self) -> None:
        """send_message returns a task on success."""
        respx.post("https://peer.example.com/api/v1/a2a").mock(
            return_value=httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": "1",
                    "result": {"id": "task-99", "state": "submitted"},
                },
            ),
        )
        catalog = _mock_catalog()
        client = _make_client(catalog)
        task = await client.send_message("peer-a", {"msg": "hi"})

        assert task.id == "task-99"
        assert task.state == A2ATaskState.SUBMITTED
        catalog.get.assert_called_once_with("peer-a")

    @pytest.mark.unit
    @respx.mock
    async def test_get_task_success(self) -> None:
        """get_task returns the remote task state."""
        respx.post("https://peer.example.com/api/v1/a2a").mock(
            return_value=httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": "1",
                    "result": {"id": "t-1", "state": "working"},
                },
            ),
        )
        catalog = _mock_catalog()
        client = _make_client(catalog)
        task = await client.get_task("peer-a", "t-1")

        assert task.id == "t-1"
        assert task.state == A2ATaskState.WORKING

    @pytest.mark.unit
    @respx.mock
    async def test_cancel_task_success(self) -> None:
        """cancel_task returns the cancelled task."""
        respx.post("https://peer.example.com/api/v1/a2a").mock(
            return_value=httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": "1",
                    "result": {"id": "t-1", "state": "canceled"},
                },
            ),
        )
        catalog = _mock_catalog()
        client = _make_client(catalog)
        task = await client.cancel_task("peer-a", "t-1")
        assert task.state == A2ATaskState.CANCELED

    @pytest.mark.unit
    @respx.mock
    async def test_remote_error_raises(self) -> None:
        """Remote JSON-RPC error raises A2AClientError."""
        respx.post("https://peer.example.com/api/v1/a2a").mock(
            return_value=httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": "1",
                    "error": {"code": -32001, "message": "Not found"},
                },
            ),
        )
        catalog = _mock_catalog()
        client = _make_client(catalog)
        with pytest.raises(A2AClientError, match="Not found"):
            await client.get_task("peer-a", "t-1")

    @pytest.mark.unit
    @respx.mock
    async def test_http_error_raises(self) -> None:
        """HTTP 500 raises A2AClientError."""
        respx.post("https://peer.example.com/api/v1/a2a").mock(
            return_value=httpx.Response(
                500,
                text="Internal Server Error",
            ),
        )
        catalog = _mock_catalog()
        client = _make_client(catalog)
        with pytest.raises(A2AClientError, match="returned 500"):
            await client.send_message("peer-a", {})

    @pytest.mark.unit
    @respx.mock
    async def test_credentials_injected_as_api_key(self) -> None:
        """API key from catalog is injected as X-API-Key header."""
        route = respx.post(
            "https://peer.example.com/api/v1/a2a",
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": "1",
                    "result": {"id": "t-1", "state": "submitted"},
                },
            ),
        )
        catalog = _mock_catalog(
            credentials={"api_key": "secret-abc", "auth_scheme": "api_key"},
        )
        client = _make_client(catalog)
        await client.send_message("peer-a", {})

        assert route.called
        req = route.calls[0].request
        assert req.headers["x-api-key"] == "secret-abc"

    @pytest.mark.unit
    async def test_client_error_carries_peer_name(self) -> None:
        """A2AClientError carries the peer name."""
        catalog = _mock_catalog(conn_exists=False)
        client = _make_client(catalog)
        with pytest.raises(A2AClientError) as exc_info:
            await client.get_task("my-peer", "task-1")
        assert exc_info.value.peer_name == "my-peer"

    @pytest.mark.unit
    def test_client_error_str(self) -> None:
        """A2AClientError has a human-readable string."""
        err = A2AClientError("test error", peer_name="p1")
        assert str(err) == "test error"
        assert err.peer_name == "p1"
