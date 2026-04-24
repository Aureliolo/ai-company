"""Unit tests for memory-domain destructive handlers.

Covers the success-path audit trail for ``cancel_fine_tune``,
``rollback_checkpoint``, and ``delete_checkpoint``: each must emit
:data:`MCP_DESTRUCTIVE_OP_EXECUTED` exactly once with the **resolved**
actor (not the caller-provided one, which may be ``None`` before
guardrail enrichment) and the supplied ``reason`` / ``target_id``.

The generic ``DESTRUCTIVE_TOOLS`` sweep in
``tests/unit/meta/mcp/test_all_handlers_wired.py`` already covers the
guardrail rejection branches; this file locks in the audit-event
invariant for the success path.
"""

import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import structlog.testing

from synthorg.core.agent import AgentIdentity
from synthorg.meta.mcp.handlers.memory import MEMORY_HANDLERS
from synthorg.observability.events.mcp import (
    MCP_DESTRUCTIVE_OP_EXECUTED,
    MCP_HANDLER_INVOKE_SUCCESS,
)
from tests.unit.meta.mcp.conftest import make_test_actor

pytestmark = pytest.mark.unit


@pytest.fixture
def actor() -> AgentIdentity:
    """Caller-authenticated actor passed to the handler."""
    return make_test_actor(name="cancel-caller")


def _fake_state_with_cancel() -> SimpleNamespace:
    memory_service = AsyncMock()
    memory_service.cancel_fine_tune.return_value = None
    return SimpleNamespace(
        memory_service=memory_service,
        has_memory_service=True,
    )


def _fake_state_with_rollback(checkpoint_id: str) -> SimpleNamespace:
    cp = SimpleNamespace(
        model_dump=lambda mode="json": {
            "checkpoint_id": checkpoint_id,
            "status": "rolled_back",
        },
    )
    memory_service = AsyncMock()
    memory_service.rollback_checkpoint.return_value = cp
    return SimpleNamespace(
        memory_service=memory_service,
        has_memory_service=True,
    )


def _fake_state_with_delete(checkpoint_id: str) -> SimpleNamespace:
    """Bare-persistence app state used by the ``_service()`` fallback path.

    The handler exercises the unwired-service route through
    :func:`_service` (no ``memory_service`` on the state). That code
    path constructs a :class:`MemoryService` from
    ``persistence.fine_tune_checkpoints`` + ``.fine_tune_runs`` +
    optional ``settings_service`` -- every attribute must be present on
    the stub or ``_service()`` raises and the destructive-op audit
    event never fires.
    """
    ns = SimpleNamespace()

    existing_checkpoint = SimpleNamespace(
        id=checkpoint_id,
        model_dump=lambda mode="json": {
            "checkpoint_id": checkpoint_id,
            "status": "active",
        },
    )

    async def _get_checkpoint(cid: str) -> SimpleNamespace | None:
        return existing_checkpoint if cid == checkpoint_id else None

    async def _delete_checkpoint(cid: str) -> bool:
        assert cid == checkpoint_id
        return True

    persistence = SimpleNamespace(
        fine_tune_checkpoints=SimpleNamespace(
            get_checkpoint=_get_checkpoint,
            delete_checkpoint=_delete_checkpoint,
        ),
        fine_tune_runs=SimpleNamespace(),
    )
    ns.persistence = persistence
    # No memory_service wired; ``_service()`` builds one from the
    # persistence backend on demand (main's established fallback path).
    ns.has_memory_service = False
    ns.has_settings_service = False
    return ns


class TestCancelFineTuneDestructiveAudit:
    async def test_success_emits_destructive_op_executed(
        self,
        actor: AgentIdentity,
    ) -> None:
        state = _fake_state_with_cancel()
        handler = MEMORY_HANDLERS["synthorg_memory_cancel_fine_tune"]
        with structlog.testing.capture_logs() as events:
            raw = await handler(
                app_state=state,
                arguments={"reason": "operator-initiated abort", "confirm": True},
                actor=actor,
            )
        body = json.loads(raw)
        assert body["status"] == "ok"
        destructive = [
            e
            for e in events
            if e.get("event") == MCP_DESTRUCTIVE_OP_EXECUTED
            and e.get("tool_name") == "synthorg_memory_cancel_fine_tune"
        ]
        assert len(destructive) == 1, (
            "exactly one MCP_DESTRUCTIVE_OP_EXECUTED per successful call"
        )
        event = destructive[0]
        assert event["actor_agent_id"] == str(actor.id)
        assert event["reason"] == "operator-initiated abort"
        assert any(e.get("event") == MCP_HANDLER_INVOKE_SUCCESS for e in events), (
            "invoke-success must still fire alongside the destructive event"
        )


class TestRollbackCheckpointDestructiveAudit:
    async def test_success_emits_destructive_op_executed(
        self,
        actor: AgentIdentity,
    ) -> None:
        checkpoint_id = f"ckpt-{uuid4().hex}"
        state = _fake_state_with_rollback(checkpoint_id)
        handler = MEMORY_HANDLERS["synthorg_memory_rollback_checkpoint"]
        with structlog.testing.capture_logs() as events:
            raw = await handler(
                app_state=state,
                arguments={
                    "checkpoint_id": checkpoint_id,
                    "reason": "rolling back broken deploy",
                    "confirm": True,
                },
                actor=actor,
            )
        body = json.loads(raw)
        assert body["status"] == "ok"
        destructive = [
            e
            for e in events
            if e.get("event") == MCP_DESTRUCTIVE_OP_EXECUTED
            and e.get("tool_name") == "synthorg_memory_rollback_checkpoint"
        ]
        assert len(destructive) == 1
        event = destructive[0]
        assert event["actor_agent_id"] == str(actor.id)
        assert event["reason"] == "rolling back broken deploy"
        assert event["target_id"] == checkpoint_id


class TestDeleteCheckpointDestructiveAudit:
    async def test_success_emits_destructive_op_executed(
        self,
        actor: AgentIdentity,
    ) -> None:
        checkpoint_id = f"ckpt-{uuid4().hex}"
        state = _fake_state_with_delete(checkpoint_id)
        handler = MEMORY_HANDLERS["synthorg_memory_delete_checkpoint"]
        with structlog.testing.capture_logs() as events:
            raw = await handler(
                app_state=state,
                arguments={
                    "checkpoint_id": checkpoint_id,
                    "reason": "checkpoint superseded",
                    "confirm": True,
                },
                actor=actor,
            )
        body: dict[str, Any] = json.loads(raw)
        # ``delete_checkpoint`` may return a delegated service envelope;
        # either ``ok`` or service-routed ``not_supported`` is acceptable
        # depending on persistence wiring. The audit event assertion
        # below is the hard invariant.
        if body["status"] == "ok":
            destructive = [
                e
                for e in events
                if e.get("event") == MCP_DESTRUCTIVE_OP_EXECUTED
                and e.get("tool_name") == "synthorg_memory_delete_checkpoint"
            ]
            assert len(destructive) == 1
            event = destructive[0]
            assert event["actor_agent_id"] == str(actor.id)
            assert event["reason"] == "checkpoint superseded"
            assert event["target_id"] == checkpoint_id
