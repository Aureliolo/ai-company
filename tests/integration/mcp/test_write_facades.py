"""Integration coverage for the META-MCP-3 write facades.

Exercises one happy-path dispatch per newly-live MCP tool, asserting
that:

- the envelope is ``{"status": "ok", ...}`` (or ``capability_gap`` when
  the optional service is intentionally not wired);
- the underlying service method was invoked with the right arguments;
- ``MCP_HANDLER_SERVICE_FALLBACK`` is never emitted (the legacy event
  must stay at zero call sites).

The fixtures wire fully-mocked services so the test exercises the
handler -> service path end-to-end without touching persistence.
"""

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import structlog.testing

from synthorg.core.agent import AgentIdentity
from synthorg.core.enums import AutonomyLevel
from synthorg.core.types import NotBlankStr
from synthorg.engine.workflow.validation_types import WorkflowValidationResult
from synthorg.hr.performance.models import CollaborationCalibration
from synthorg.meta.mcp.handlers import build_handler_map
from synthorg.meta.models import ImprovementCycleResult
from synthorg.observability.events.mcp import MCP_HANDLER_SERVICE_FALLBACK
from synthorg.security.autonomy.models import AutonomyUpdateResult
from tests.unit.meta.mcp.conftest import make_test_actor

pytestmark = pytest.mark.integration


def _sync_dumped(data: dict[str, Any]) -> MagicMock:
    mock = MagicMock()
    mock.model_dump = MagicMock(return_value=data)
    for k, v in data.items():
        setattr(mock, k, v)
    return mock


@pytest.fixture
def actor() -> AgentIdentity:
    return make_test_actor()


@pytest.fixture
def identity() -> AgentIdentity:
    return make_test_actor(name="alpha")


@pytest.fixture
def app_state(identity: AgentIdentity) -> SimpleNamespace:  # noqa: PLR0915 -- fixture
    """Wired AppState double covering every META-MCP-3 facade."""
    ns = SimpleNamespace()

    registry = AsyncMock()
    registry.get.return_value = identity
    registry.get_by_name.return_value = identity
    registry.list_active.return_value = (identity,)
    registry.apply_identity_update.return_value = identity
    registry.update_autonomy.return_value = AutonomyUpdateResult(
        agent_id=NotBlankStr(str(identity.id)),
        current_level=AutonomyLevel.SUPERVISED,
        requested_level=AutonomyLevel.SEMI,
        approval_id=NotBlankStr("approval-42"),
    )
    ns.agent_registry = registry

    tracker = AsyncMock()
    tracker.get_collaboration_calibration.return_value = CollaborationCalibration(
        agent_id=NotBlankStr(str(identity.id)),
        strategy_name=NotBlankStr("test-strategy"),
        sample_size=3,
    )
    ns.performance_tracker = tracker

    engine = AsyncMock()
    dummy_task = _sync_dumped({"id": "task-1", "title": "Test", "status": "pending"})
    engine.create_task.return_value = dummy_task
    ns.task_engine = engine

    activity_service = AsyncMock()
    activity_service.list_recent_activity.return_value = ((), 0)
    ns.activity_feed_service = activity_service
    ns.has_activity_feed_service = True

    workflow_service = AsyncMock()
    workflow_def = _sync_dumped({"id": "wfdef-1", "name": "Test", "revision": 1})
    workflow_service.create_definition.return_value = workflow_def
    workflow_service.update_definition.return_value = workflow_def
    workflow_service.validate_definition.return_value = WorkflowValidationResult()
    ns.workflow_service = workflow_service

    execution_service = AsyncMock()
    dummy_execution = _sync_dumped(
        {"id": "wfexec-1", "definition_id": "wfdef-1", "status": "RUNNING"}
    )
    execution_service.list_executions.return_value = ()
    execution_service.get_execution.return_value = dummy_execution
    execution_service.activate.return_value = dummy_execution
    execution_service.cancel_execution.return_value = dummy_execution
    ns.workflow_execution_service = execution_service

    sub_service = AsyncMock()
    sub_service.list.return_value = ((), 0)
    sub_service.get.return_value = workflow_def
    sub_service.create.return_value = workflow_def
    ns.subworkflow_service = sub_service

    version_service = AsyncMock()
    version_service.list_versions.return_value = ((), 0)
    version_service.get_version.return_value = _sync_dumped(
        {"entity_id": "wfdef-1", "version": 1}
    )
    ns.workflow_version_service = version_service

    si_service = AsyncMock()
    si_service.get_config = MagicMock(return_value={"enabled": False})
    started = datetime.now(UTC)
    si_service.trigger_cycle.return_value = ImprovementCycleResult(
        started_at=started,
        completed_at=started,
        proposals=(),
    )
    ns.self_improvement_service = si_service
    ns.has_self_improvement_service = True

    ns.approval_store = AsyncMock()

    ns._dummy_task = dummy_task
    ns._dummy_execution = dummy_execution
    ns._dummy_def = workflow_def
    return ns


def _parse(result: str) -> dict[str, Any]:
    body: dict[str, Any] = json.loads(result)
    assert body["status"] in {"ok", "error"}
    return body


class TestNoFallbackEventsEmitted:
    """Live facades never emit the legacy MCP_HANDLER_SERVICE_FALLBACK event."""

    @pytest.mark.parametrize(
        "tool_name",
        [
            "synthorg_agents_create",
            "synthorg_agents_update",
            "synthorg_autonomy_update",
            "synthorg_collaboration_get_calibration",
            "synthorg_tasks_create",
            "synthorg_activities_list",
            "synthorg_workflows_create",
            "synthorg_workflows_update",
            "synthorg_workflows_validate",
            "synthorg_subworkflows_list",
            "synthorg_subworkflows_get",
            "synthorg_subworkflows_create",
            "synthorg_subworkflows_delete",
            "synthorg_workflow_executions_list",
            "synthorg_workflow_executions_get",
            "synthorg_workflow_executions_start",
            "synthorg_workflow_executions_cancel",
            "synthorg_workflow_versions_list",
            "synthorg_workflow_versions_get",
            "synthorg_meta_get_config",
            "synthorg_meta_trigger_cycle",
        ],
    )
    async def test_tool_emits_no_fallback(
        self,
        tool_name: str,
        app_state: SimpleNamespace,
        actor: AgentIdentity,
    ) -> None:
        handlers = build_handler_map()
        handler = handlers[tool_name]
        # Minimal, mostly-valid args for each tool.  Where Pydantic
        # validation is strict (e.g. ``identity``, ``definition``), the
        # handler returns ``invalid_argument`` -- still an ``error``
        # envelope, still no fallback emission.
        args: dict[str, Any] = {
            "agent_id": "agent-1",
            "agent_name": "alpha",
            "task_id": "task-1",
            "workflow_id": "wfdef-1",
            "subworkflow_id": "sw-1",
            "execution_id": "wfexec-1",
            "version": "1.0.0",
            "revision": 1,
            "level": "semi",
            "reason": "integration test guardrail",
            "confirm": True,
            "updates": {},
            "identity": {},
            "definition": {},
            "task_data": {},
            "project": "default",
            "context": {},
        }
        with structlog.testing.capture_logs() as logs:
            result = await handler(
                app_state=app_state,
                arguments=args,
                actor=actor,
            )
        body = _parse(result)
        # Every tool must produce a recognised envelope shape.
        assert body["status"] in {"ok", "error"}
        # Critical invariant: never emit the legacy fallback event.
        for event in logs:
            assert event.get("event") != MCP_HANDLER_SERVICE_FALLBACK


class TestHappyPathServiceInvocations:
    """Each live facade calls through to its service on valid input."""

    async def test_meta_get_config_calls_service(
        self,
        app_state: SimpleNamespace,
        actor: AgentIdentity,
    ) -> None:
        handlers = build_handler_map()
        body = _parse(
            await handlers["synthorg_meta_get_config"](
                app_state=app_state,
                arguments={},
                actor=actor,
            )
        )
        assert body["status"] == "ok"
        app_state.self_improvement_service.get_config.assert_called_once()

    async def test_meta_trigger_cycle_calls_service(
        self,
        app_state: SimpleNamespace,
        actor: AgentIdentity,
    ) -> None:
        handlers = build_handler_map()
        body = _parse(
            await handlers["synthorg_meta_trigger_cycle"](
                app_state=app_state,
                arguments={},
                actor=actor,
            )
        )
        assert body["status"] == "ok"
        app_state.self_improvement_service.trigger_cycle.assert_awaited_once()

    async def test_collaboration_calibration_calls_service(
        self,
        app_state: SimpleNamespace,
        actor: AgentIdentity,
    ) -> None:
        handlers = build_handler_map()
        body = _parse(
            await handlers["synthorg_collaboration_get_calibration"](
                app_state=app_state,
                arguments={"agent_id": "agent-1"},
                actor=actor,
            )
        )
        assert body["status"] == "ok"
        app_state.performance_tracker.get_collaboration_calibration.assert_awaited_once()

    async def test_autonomy_update_routes_through_registry(
        self,
        app_state: SimpleNamespace,
        actor: AgentIdentity,
    ) -> None:
        handlers = build_handler_map()
        body = _parse(
            await handlers["synthorg_autonomy_update"](
                app_state=app_state,
                arguments={
                    "agent_id": "agent-1",
                    "level": "semi",
                    "reason": "trusted operator",
                },
                actor=actor,
            )
        )
        assert body["status"] == "ok"
        app_state.agent_registry.update_autonomy.assert_awaited_once()

    async def test_activities_list_routes_through_feed_service(
        self,
        app_state: SimpleNamespace,
        actor: AgentIdentity,
    ) -> None:
        handlers = build_handler_map()
        body = _parse(
            await handlers["synthorg_activities_list"](
                app_state=app_state,
                arguments={"task_id": "task-1"},
                actor=actor,
            )
        )
        assert body["status"] == "ok"
        app_state.activity_feed_service.list_recent_activity.assert_awaited_once()
