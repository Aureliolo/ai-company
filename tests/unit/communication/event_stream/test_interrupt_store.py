"""Tests for InterruptStore."""

import asyncio
from datetime import UTC, datetime
from typing import Any

import pytest

from synthorg.communication.event_stream.interrupt import (
    Interrupt,
    InterruptResolution,
    InterruptStore,
    InterruptType,
    ResumeDecision,
)

_TS = datetime(2026, 4, 13, tzinfo=UTC)


def _make_interrupt(**overrides: Any) -> Interrupt:
    defaults: dict[str, Any] = {
        "id": "int-001",
        "type": InterruptType.TOOL_APPROVAL,
        "session_id": "session-abc",
        "agent_id": "agent-eng-001",
        "created_at": _TS,
        "timeout_seconds": 300.0,
        "tool_name": "deploy_service",
    }
    defaults.update(overrides)
    return Interrupt(**defaults)


def _make_resolution(
    interrupt_id: str = "int-001",
    **overrides: Any,
) -> InterruptResolution:
    defaults: dict[str, Any] = {
        "interrupt_id": interrupt_id,
        "decision": ResumeDecision.APPROVE,
        "resolved_at": datetime(2026, 4, 13, 0, 5, tzinfo=UTC),
        "resolved_by": "admin-user",
    }
    defaults.update(overrides)
    return InterruptResolution(**defaults)


@pytest.mark.unit
class TestInterruptStore:
    async def test_create_and_get(self) -> None:
        store = InterruptStore()
        interrupt = _make_interrupt()
        await store.create(interrupt)
        result = await store.get("int-001")
        assert result is not None
        assert result.id == "int-001"

    async def test_get_nonexistent_returns_none(self) -> None:
        store = InterruptStore()
        result = await store.get("nonexistent")
        assert result is None

    async def test_create_duplicate_raises(self) -> None:
        store = InterruptStore()
        await store.create(_make_interrupt())
        with pytest.raises(ValueError, match="already exists"):
            await store.create(_make_interrupt())

    async def test_list_pending_all(self) -> None:
        store = InterruptStore()
        await store.create(_make_interrupt(id="i1"))
        await store.create(_make_interrupt(id="i2"))
        pending = await store.list_pending()
        assert len(pending) == 2

    async def test_list_pending_by_session(self) -> None:
        store = InterruptStore()
        await store.create(_make_interrupt(id="i1", session_id="s1"))
        await store.create(_make_interrupt(id="i2", session_id="s2"))
        pending = await store.list_pending(session_id="s1")
        assert len(pending) == 1
        assert pending[0].id == "i1"

    async def test_resolve_returns_interrupt(self) -> None:
        store = InterruptStore()
        await store.create(_make_interrupt())
        resolution = _make_resolution()
        result = await store.resolve(resolution)
        assert result is not None
        assert result.id == "int-001"

    async def test_resolve_removes_from_pending(self) -> None:
        store = InterruptStore()
        await store.create(_make_interrupt())
        await store.resolve(_make_resolution())
        result = await store.get("int-001")
        assert result is None

    async def test_resolve_nonexistent_returns_none(self) -> None:
        store = InterruptStore()
        result = await store.resolve(_make_resolution(interrupt_id="nope"))
        assert result is None

    async def test_resolve_signals_waiter(self) -> None:
        store = InterruptStore()
        await store.create(_make_interrupt())

        async def _resolve_after_delay() -> None:
            await asyncio.sleep(0.01)
            await store.resolve(_make_resolution())

        task = asyncio.create_task(_resolve_after_delay())
        result = await store.wait_for_resolution("int-001", timeout=5.0)
        await task
        assert result is not None
        assert result.decision == ResumeDecision.APPROVE

    async def test_wait_for_resolution_timeout(self) -> None:
        store = InterruptStore()
        await store.create(_make_interrupt())
        result = await store.wait_for_resolution("int-001", timeout=0.01)
        assert result is None

    async def test_wait_for_nonexistent_returns_none(self) -> None:
        store = InterruptStore()
        result = await store.wait_for_resolution("nonexistent", timeout=0.01)
        assert result is None
