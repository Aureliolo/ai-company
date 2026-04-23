"""META-MCP-2 acceptance sweep for the full 204-tool MCP surface.

The unit sweep in ``tests/unit/meta/mcp/test_all_handlers_wired.py``
already asserts parity between the registry and the handler map, and
guardrail rejection shape for the destructive subset.  This integration
sweep layers the META-MCP-2 acceptance criterion on top:

1. **Zero ``MCP_HANDLER_SERVICE_FALLBACK`` emissions** for any read or
   invoke path. The legacy ``service_fallback()`` helper stays in
   ``common.py`` for future surgical use, but it must have zero call
   sites in the handler tree after META-MCP-2.
2. **Capability-gap envelopes are the *only* ``not_supported`` source**.
   Tools whose underlying primitive does not yet expose the required
   method emit ``MCP_HANDLER_CAPABILITY_GAP`` (INFO) instead, which
   carries the same ``domain_code="not_supported"`` wire envelope
   without polluting the legacy event channel.
3. **Every tool returns a well-formed envelope** -- ``status`` is
   always ``"ok"`` or ``"error"``, never ``"not_implemented"``.
"""

import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import structlog.testing

from synthorg.core.agent import AgentIdentity
from synthorg.hr.performance.models import CollaborationScoreResult
from synthorg.meta.mcp.domains import build_full_registry
from synthorg.meta.mcp.handlers import build_handler_map
from synthorg.observability.events.mcp import MCP_HANDLER_SERVICE_FALLBACK
from tests.unit.meta.mcp.conftest import make_test_actor

pytestmark = pytest.mark.integration


def _sync_dumped(data: dict[str, Any]) -> MagicMock:
    mock = MagicMock()
    mock.model_dump = MagicMock(return_value=data)
    for k, v in data.items():
        setattr(mock, k, v)
    return mock


def _mkversion_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.list_versions.return_value = ()
    repo.count_versions.return_value = 0
    repo.get_version.return_value = None
    return repo


@pytest.fixture
def fake_app_state() -> SimpleNamespace:
    """Wide-blast stub covering every primitive the handlers probe."""
    ns = SimpleNamespace()

    dummy_task = _sync_dumped({"id": "task-1", "title": "x"})

    defrepo = AsyncMock()
    defrepo.list_definitions.return_value = ()
    defrepo.get.return_value = None
    defrepo.delete.return_value = False
    ns.persistence = SimpleNamespace(
        workflow_definitions=defrepo,
        workflow_versions=AsyncMock(),
        budget_config_versions=_mkversion_repo(),
        fine_tune_checkpoints=AsyncMock(),
        fine_tune_runs=AsyncMock(),
    )

    engine = AsyncMock()
    engine.list_tasks.return_value = ((), 0)
    engine.get_task.return_value = None
    engine.update_task.return_value = dummy_task
    engine.cancel_task.return_value = dummy_task
    engine.delete_task.return_value = True
    engine.transition_task.return_value = (dummy_task, None)
    ns.task_engine = engine

    registry = AsyncMock()
    registry.list_active.return_value = ()
    registry.get_by_name.return_value = None
    registry.get.return_value = None
    ns.agent_registry = registry

    ns.performance_tracker = AsyncMock()
    ns.performance_tracker.get_snapshot.return_value = None
    ns.performance_tracker.get_collaboration_score.return_value = (
        CollaborationScoreResult(
            score=0.0,
            strategy_name="test-strategy",
            confidence=0.5,
        )
    )

    ns.cost_tracker = AsyncMock()
    ns.cost_tracker.get_records.return_value = ()
    ns.cost_tracker.get_agent_cost.return_value = 0.0
    ns.config_resolver = AsyncMock()
    ns.config_resolver.get_budget_config.return_value = _sync_dumped(
        {"currency": "USD"},
    )

    ns.approval_store = AsyncMock()
    ns.approval_store.list_items.return_value = ()
    ns.approval_store.get.return_value = None

    ns.persistence.fine_tune_checkpoints.list_checkpoints.return_value = (
        (),
        0,
    )
    ns.persistence.fine_tune_checkpoints.get_checkpoint.return_value = None

    ns.has_task_engine = True
    ns.has_cost_tracker = True
    ns.has_agent_registry = True
    ns.has_settings_service = False
    ns.settings_service = None

    ns._dummy_task = dummy_task
    return ns


@pytest.fixture
def actor() -> AgentIdentity:
    return make_test_actor()


_BLAST_ARGS: dict[str, Any] = {
    "agent_name": "alpha",
    "agent_id": "agent-1",
    "approval_id": "approval-1",
    "task_id": "task-1",
    "workflow_id": "wf-1",
    "subworkflow_id": "sw-1",
    "execution_id": "ex-1",
    "checkpoint_id": "cp-1",
    "version_num": 1,
    "title": "x",
    "description": "y",
    "action_type": "deploy",
    "risk_level": "medium",
    "confirm": True,
    "reason": "test",
    "name": "alpha",
    "role": "engineer",
    "department": "Engineering",
    "session_id": "sess-1",
    "level": "FULL",
    "updates": {},
    "target_status": "in_progress",
    "steps": [],
    "status": "pending",
}


class TestNoServiceFallbackEvents:
    """Acceptance gate: zero MCP_HANDLER_SERVICE_FALLBACK events after META-MCP-2."""

    async def test_invoking_every_tool_emits_no_service_fallback_event(
        self,
        fake_app_state: SimpleNamespace,
        actor: AgentIdentity,
    ) -> None:
        handlers = build_handler_map()
        with structlog.testing.capture_logs() as events:
            for handler in handlers.values():
                await handler(
                    app_state=fake_app_state,
                    arguments=dict(_BLAST_ARGS),
                    actor=actor,
                )
        fallback_events = [
            e for e in events if e.get("event") == MCP_HANDLER_SERVICE_FALLBACK
        ]
        assert not fallback_events, (
            f"MCP_HANDLER_SERVICE_FALLBACK must be unused after META-MCP-2, "
            f"but {len(fallback_events)} emissions fired: "
            f"{[e.get('tool_name') for e in fallback_events]}"
        )

    async def test_every_tool_returns_well_formed_envelope(
        self,
        fake_app_state: SimpleNamespace,
        actor: AgentIdentity,
    ) -> None:
        """Each tool returns ``status`` in {ok, error}, with mandatory keys."""
        registry = build_full_registry()
        handlers = build_handler_map()
        for tool_name in registry.get_names():
            handler = handlers[tool_name]
            raw = await handler(
                app_state=fake_app_state,
                arguments=dict(_BLAST_ARGS),
                actor=actor,
            )
            body = json.loads(raw)
            assert body["status"] in {"ok", "error"}, (
                f"{tool_name} returned unexpected status {body.get('status')!r}"
            )
            if body["status"] == "error":
                assert "message" in body, f"{tool_name} error lacks message"


class TestToolSurfaceCount:
    """Pin the tool count at 204 to catch accidental add/remove regressions."""

    def test_total_tool_count_is_204(self) -> None:
        registry = build_full_registry()
        assert registry.tool_count == 204

    def test_no_orphan_handlers(self) -> None:
        registry = build_full_registry()
        handlers = build_handler_map()
        orphans = set(handlers.keys()) - set(registry.get_names())
        assert not orphans
        missing = set(registry.get_names()) - set(handlers.keys())
        assert not missing
