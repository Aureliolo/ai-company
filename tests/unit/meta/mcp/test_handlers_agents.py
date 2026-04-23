"""Smoke tests for agent domain MCP handlers.

The handler universe is big and half of it shims onto services that
don't yet expose a clean read method (personality registry, activity
feed, etc.).  The unit suite here covers:

- Every handler is callable with an empty/minimal arg dict and returns
  a syntactically valid envelope (``status`` is ``ok``/``error``/
  ``not_implemented``).  This is the regression guard.
- For tools that DO have a clean service shim, a happy-path test
  exercises the service call.
- ``synthorg_agents_delete`` gets the full destructive-op workout
  (guardrail branches + audit event on success).
"""

import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
import structlog.testing

from synthorg.core.agent import AgentIdentity
from synthorg.meta.mcp.handlers.agents import AGENT_HANDLERS
from synthorg.observability.events.mcp import (
    MCP_DESTRUCTIVE_OP_EXECUTED,
    MCP_HANDLER_GUARDRAIL_VIOLATED,
)
from tests.unit.meta.mcp.conftest import make_test_actor

pytestmark = pytest.mark.unit


@pytest.fixture
def identity() -> SimpleNamespace:
    """Minimal agent-identity stub exposing the fields handlers read."""
    return SimpleNamespace(
        id="agent-1",
        name="alpha",
        autonomy_level=None,
        model_dump=lambda mode="json": {"id": "agent-1", "name": "alpha"},
    )


@pytest.fixture
def fake_app_state(identity: SimpleNamespace) -> SimpleNamespace:
    """App state stub with registry/performance mocks."""
    registry = AsyncMock()
    registry.list_active.return_value = (identity,)
    registry.get_by_name.return_value = identity
    registry.get.return_value = identity
    registry.unregister.return_value = identity

    tracker = AsyncMock()
    tracker.get_snapshot.return_value = None
    tracker.get_collaboration_score.return_value = 0.75

    return SimpleNamespace(
        agent_registry=registry,
        performance_tracker=tracker,
    )


@pytest.fixture
def actor() -> AgentIdentity:
    return make_test_actor(name="ops")


def _parse(result: str) -> dict[str, Any]:
    body: dict[str, Any] = json.loads(result)
    assert body["status"] in {"ok", "error"}, (
        f"legacy envelope leaked: status={body['status']!r}"
    )
    return body


class TestAllAgentHandlersReturnValidEnvelope:
    """Every handler must return a well-formed envelope on a basic call."""

    @pytest.mark.parametrize(
        "tool_name",
        list(AGENT_HANDLERS.keys()),
    )
    async def test_basic_envelope(
        self,
        tool_name: str,
        fake_app_state: SimpleNamespace,
        actor: AgentIdentity,
    ) -> None:
        handler = AGENT_HANDLERS[tool_name]
        # Minimal arg set likely accepted by each handler; destructive
        # ops fail guardrails but still return a valid envelope.
        args: dict[str, Any] = {
            "agent_name": "alpha",
            "agent_id": "agent-1",
            "name": "alpha",
            "role": "engineer",
            "department": "Engineering",
            "session_id": "sess-1",
            "level": "FULL",
        }
        result = await handler(
            app_state=fake_app_state,
            arguments=args,
            actor=actor,
        )
        _parse(result)


class TestAgentsList:
    async def test_happy_path(
        self,
        fake_app_state: SimpleNamespace,
        identity: SimpleNamespace,
    ) -> None:
        handler = AGENT_HANDLERS["synthorg_agents_list"]
        result = await handler(
            app_state=fake_app_state,
            arguments={},
            actor=None,
        )
        body = _parse(result)
        assert body["status"] == "ok"
        assert body["data"] == [{"id": "agent-1", "name": "alpha"}]
        assert body["pagination"]["total"] == 1


class TestAgentsGet:
    async def test_not_found(
        self,
        fake_app_state: SimpleNamespace,
    ) -> None:
        fake_app_state.agent_registry.get_by_name.return_value = None
        handler = AGENT_HANDLERS["synthorg_agents_get"]
        body = _parse(
            await handler(
                app_state=fake_app_state,
                arguments={"agent_name": "missing"},
                actor=None,
            ),
        )
        assert body["status"] == "error"
        assert body["domain_code"] == "not_found"


class TestAgentsDelete:
    """Full destructive-op workout."""

    async def test_happy_path_fires_audit_event(
        self,
        fake_app_state: SimpleNamespace,
        identity: SimpleNamespace,
        actor: AgentIdentity,
    ) -> None:
        handler = AGENT_HANDLERS["synthorg_agents_delete"]
        with structlog.testing.capture_logs() as logs:
            body = _parse(
                await handler(
                    app_state=fake_app_state,
                    arguments={
                        "agent_name": "alpha",
                        "reason": "retiring role",
                        "confirm": True,
                    },
                    actor=actor,
                ),
            )
        assert body["status"] == "ok"
        audit = [e for e in logs if e.get("event") == MCP_DESTRUCTIVE_OP_EXECUTED]
        assert len(audit) == 1

    async def test_missing_confirm_blocked(
        self,
        fake_app_state: SimpleNamespace,
        actor: AgentIdentity,
    ) -> None:
        handler = AGENT_HANDLERS["synthorg_agents_delete"]
        with structlog.testing.capture_logs() as logs:
            body = _parse(
                await handler(
                    app_state=fake_app_state,
                    arguments={"agent_name": "alpha", "reason": "x"},
                    actor=actor,
                ),
            )
        assert body["status"] == "error"
        assert body["domain_code"] == "guardrail_violated"
        events = {e.get("event") for e in logs}
        assert MCP_HANDLER_GUARDRAIL_VIOLATED in events
        assert MCP_DESTRUCTIVE_OP_EXECUTED not in events

    async def test_missing_actor_blocked(
        self,
        fake_app_state: SimpleNamespace,
    ) -> None:
        handler = AGENT_HANDLERS["synthorg_agents_delete"]
        body = _parse(
            await handler(
                app_state=fake_app_state,
                arguments={
                    "agent_name": "alpha",
                    "reason": "x",
                    "confirm": True,
                },
                actor=None,
            ),
        )
        assert body["status"] == "error"
        assert body["domain_code"] == "guardrail_violated"

    async def test_not_found(
        self,
        fake_app_state: SimpleNamespace,
        actor: AgentIdentity,
    ) -> None:
        fake_app_state.agent_registry.get_by_name.return_value = None
        handler = AGENT_HANDLERS["synthorg_agents_delete"]
        body = _parse(
            await handler(
                app_state=fake_app_state,
                arguments={
                    "agent_name": "missing",
                    "reason": "cleanup",
                    "confirm": True,
                },
                actor=actor,
            ),
        )
        assert body["status"] == "error"
        assert body["domain_code"] == "not_found"


class TestNotSupportedHandlers:
    """Tools whose service surface isn't exposed return a clean error."""

    @pytest.mark.parametrize(
        "tool_name",
        [
            "synthorg_agents_create",
            "synthorg_agents_update",
            "synthorg_agents_get_activity",
            "synthorg_agents_get_history",
            "synthorg_agents_get_health",
            "synthorg_personalities_list",
            "synthorg_personalities_get",
            "synthorg_training_list_sessions",
            "synthorg_training_get_session",
            "synthorg_training_start_session",
            "synthorg_autonomy_update",
            "synthorg_collaboration_get_calibration",
        ],
    )
    async def test_returns_not_supported(
        self,
        tool_name: str,
        fake_app_state: SimpleNamespace,
    ) -> None:
        handler = AGENT_HANDLERS[tool_name]
        body = _parse(
            await handler(app_state=fake_app_state, arguments={}, actor=None),
        )
        assert body["status"] == "error"
        assert body["domain_code"] == "not_supported"
