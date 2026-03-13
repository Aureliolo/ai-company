"""Tests for Mem0 adapter — shared knowledge store (publish, search, retract)."""

from unittest.mock import MagicMock

import pytest

from ai_company.memory.backends.mem0.adapter import (
    _SHARED_NAMESPACE,
    Mem0MemoryBackend,
)
from ai_company.memory.backends.mem0.mappers import _PUBLISHER_KEY
from ai_company.memory.errors import (
    MemoryRetrievalError,
    MemoryStoreError,
)
from ai_company.memory.models import MemoryQuery

from .conftest import (
    make_store_request,
    mem0_add_result,
    mem0_search_result,
)

pytestmark = pytest.mark.timeout(30)


# ── Publish ──────────────────────────────────────────────────────


@pytest.mark.unit
class TestPublish:
    async def test_publish_success(
        self,
        backend: Mem0MemoryBackend,
        mock_client: MagicMock,
    ) -> None:
        mock_client.add.return_value = mem0_add_result("shared-mem-001")

        memory_id = await backend.publish(
            "test-agent-001",
            make_store_request(),
        )

        assert memory_id == "shared-mem-001"
        call_kwargs = mock_client.add.call_args[1]
        assert call_kwargs["user_id"] == _SHARED_NAMESPACE
        assert _PUBLISHER_KEY in call_kwargs["metadata"]
        assert call_kwargs["metadata"][_PUBLISHER_KEY] == "test-agent-001"

    async def test_publish_empty_results_raises(
        self,
        backend: Mem0MemoryBackend,
        mock_client: MagicMock,
    ) -> None:
        mock_client.add.return_value = {"results": []}

        with pytest.raises(MemoryStoreError, match="no results"):
            await backend.publish("test-agent-001", make_store_request())

    async def test_publish_exception_wraps(
        self,
        backend: Mem0MemoryBackend,
        mock_client: MagicMock,
    ) -> None:
        mock_client.add.side_effect = RuntimeError("network error")

        with pytest.raises(MemoryStoreError, match="Failed to publish"):
            await backend.publish("test-agent-001", make_store_request())

    async def test_publish_missing_id_raises(
        self,
        backend: Mem0MemoryBackend,
        mock_client: MagicMock,
    ) -> None:
        """Publish result missing 'id' raises MemoryStoreError."""
        mock_client.add.return_value = {
            "results": [{"memory": "no id", "event": "ADD"}],
        }

        with pytest.raises(MemoryStoreError, match="missing or blank 'id'"):
            await backend.publish("test-agent-001", make_store_request())

    async def test_publish_reraises_memory_error(
        self,
        backend: Mem0MemoryBackend,
        mock_client: MagicMock,
    ) -> None:
        """builtins.MemoryError is re-raised without wrapping."""
        mock_client.add.side_effect = MemoryError("out of memory")
        with pytest.raises(MemoryError):
            await backend.publish("test-agent-001", make_store_request())


# ── SearchShared ─────────────────────────────────────────────────


@pytest.mark.unit
class TestSearchShared:
    async def test_search_shared_with_text(
        self,
        backend: Mem0MemoryBackend,
        mock_client: MagicMock,
    ) -> None:
        mock_client.search.return_value = mem0_search_result(
            [
                {
                    "id": "shared-1",
                    "memory": "shared fact",
                    "score": 0.9,
                    "created_at": "2026-03-12T10:00:00+00:00",
                    "metadata": {
                        "_synthorg_category": "semantic",
                        _PUBLISHER_KEY: "test-agent-002",
                    },
                },
            ],
        )

        query = MemoryQuery(text="find shared", limit=5)
        entries = await backend.search_shared(query)

        assert len(entries) == 1
        assert entries[0].agent_id == "test-agent-002"
        mock_client.search.assert_called_once()
        call_kwargs = mock_client.search.call_args[1]
        assert call_kwargs["user_id"] == _SHARED_NAMESPACE

    async def test_search_shared_without_text(
        self,
        backend: Mem0MemoryBackend,
        mock_client: MagicMock,
    ) -> None:
        mock_client.get_all.return_value = mem0_search_result(
            [
                {
                    "id": "shared-1",
                    "memory": "shared fact",
                    "created_at": "2026-03-12T10:00:00+00:00",
                    "metadata": {
                        _PUBLISHER_KEY: "test-agent-002",
                    },
                },
            ],
        )

        query = MemoryQuery(text=None)
        entries = await backend.search_shared(query)

        assert len(entries) == 1
        mock_client.get_all.assert_called_once()

    async def test_search_shared_exclude_agent(
        self,
        backend: Mem0MemoryBackend,
        mock_client: MagicMock,
    ) -> None:
        mock_client.search.return_value = mem0_search_result(
            [
                {
                    "id": "s1",
                    "memory": "from agent 1",
                    "score": 0.9,
                    "created_at": "2026-03-12T10:00:00+00:00",
                    "metadata": {_PUBLISHER_KEY: "test-agent-001"},
                },
                {
                    "id": "s2",
                    "memory": "from agent 2",
                    "score": 0.8,
                    "created_at": "2026-03-12T10:00:00+00:00",
                    "metadata": {_PUBLISHER_KEY: "test-agent-002"},
                },
            ],
        )

        query = MemoryQuery(text="test")
        entries = await backend.search_shared(
            query,
            exclude_agent="test-agent-001",
        )

        assert len(entries) == 1
        assert entries[0].agent_id == "test-agent-002"

    async def test_search_shared_exception_wraps(
        self,
        backend: Mem0MemoryBackend,
        mock_client: MagicMock,
    ) -> None:
        mock_client.search.side_effect = RuntimeError("search error")

        with pytest.raises(MemoryRetrievalError, match="Failed to search"):
            await backend.search_shared(MemoryQuery(text="test"))

    async def test_search_shared_reraises_memory_error(
        self,
        backend: Mem0MemoryBackend,
        mock_client: MagicMock,
    ) -> None:
        """builtins.MemoryError is re-raised without wrapping."""
        mock_client.search.side_effect = MemoryError("out of memory")
        with pytest.raises(MemoryError):
            await backend.search_shared(MemoryQuery(text="test"))

    async def test_search_shared_no_publisher_uses_namespace(
        self,
        backend: Mem0MemoryBackend,
        mock_client: MagicMock,
    ) -> None:
        """Entries without publisher metadata use the shared namespace."""
        mock_client.search.return_value = mem0_search_result(
            [
                {
                    "id": "shared-1",
                    "memory": "orphan fact",
                    "score": 0.9,
                    "created_at": "2026-03-12T10:00:00+00:00",
                    "metadata": {"_synthorg_category": "semantic"},
                },
            ],
        )

        entries = await backend.search_shared(MemoryQuery(text="test"))
        assert len(entries) == 1
        assert entries[0].agent_id == _SHARED_NAMESPACE


# ── Retract ──────────────────────────────────────────────────────


@pytest.mark.unit
class TestRetract:
    async def test_retract_success(
        self,
        backend: Mem0MemoryBackend,
        mock_client: MagicMock,
    ) -> None:
        mock_client.get.return_value = {
            "id": "shared-001",
            "memory": "shared content",
            "created_at": "2026-03-12T10:00:00+00:00",
            "metadata": {_PUBLISHER_KEY: "test-agent-001"},
        }
        mock_client.delete.return_value = None

        result = await backend.retract("test-agent-001", "shared-001")

        assert result is True
        mock_client.delete.assert_called_once_with("shared-001")

    async def test_retract_not_found(
        self,
        backend: Mem0MemoryBackend,
        mock_client: MagicMock,
    ) -> None:
        mock_client.get.return_value = None

        result = await backend.retract("test-agent-001", "nonexistent")

        assert result is False

    async def test_retract_ownership_mismatch(
        self,
        backend: Mem0MemoryBackend,
        mock_client: MagicMock,
    ) -> None:
        mock_client.get.return_value = {
            "id": "shared-001",
            "memory": "content",
            "created_at": "2026-03-12T10:00:00+00:00",
            "metadata": {_PUBLISHER_KEY: "test-agent-002"},
        }

        with pytest.raises(MemoryStoreError, match="cannot retract"):
            await backend.retract("test-agent-001", "shared-001")

    async def test_retract_no_publisher_raises(
        self,
        backend: Mem0MemoryBackend,
        mock_client: MagicMock,
    ) -> None:
        mock_client.get.return_value = {
            "id": "not-shared-001",
            "memory": "private content",
            "created_at": "2026-03-12T10:00:00+00:00",
            "metadata": {},
        }

        with pytest.raises(MemoryStoreError, match="not a shared memory"):
            await backend.retract("test-agent-001", "not-shared-001")

    async def test_retract_exception_wraps(
        self,
        backend: Mem0MemoryBackend,
        mock_client: MagicMock,
    ) -> None:
        mock_client.get.side_effect = RuntimeError("backend error")

        with pytest.raises(MemoryStoreError, match="Failed to retract"):
            await backend.retract("test-agent-001", "shared-001")

    async def test_retract_reraises_memory_error(
        self,
        backend: Mem0MemoryBackend,
        mock_client: MagicMock,
    ) -> None:
        """builtins.MemoryError is re-raised without wrapping."""
        mock_client.get.side_effect = MemoryError("out of memory")
        with pytest.raises(MemoryError):
            await backend.retract("test-agent-001", "shared-001")

    async def test_retract_delete_failure_wraps(
        self,
        backend: Mem0MemoryBackend,
        mock_client: MagicMock,
    ) -> None:
        """Exception during delete phase wraps in MemoryStoreError."""
        mock_client.get.return_value = {
            "id": "shared-001",
            "memory": "content",
            "created_at": "2026-03-12T10:00:00+00:00",
            "metadata": {_PUBLISHER_KEY: "test-agent-001"},
        }
        mock_client.delete.side_effect = RuntimeError("delete failed")

        with pytest.raises(MemoryStoreError, match="Failed to retract"):
            await backend.retract("test-agent-001", "shared-001")
