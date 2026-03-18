"""Unit tests for AgentEngine auto-loop selection integration."""

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest
import structlog.testing

from synthorg.budget.config import BudgetAlertConfig, BudgetConfig
from synthorg.budget.enforcer import BudgetEnforcer
from synthorg.budget.tracker import CostTracker
from synthorg.core.agent import AgentIdentity
from synthorg.core.enums import Complexity, TaskStatus, TaskType
from synthorg.core.task import Task
from synthorg.engine.agent_engine import AgentEngine
from synthorg.engine.loop_selector import AutoLoopConfig
from synthorg.engine.react_loop import ReactLoop
from synthorg.engine.run_result import AgentRunResult
from synthorg.observability.events.execution import (
    EXECUTION_LOOP_AUTO_SELECTED,
)

if TYPE_CHECKING:
    from .conftest import MockCompletionProvider

from .conftest import make_completion_response as _make_completion_response

pytestmark = pytest.mark.timeout(30)


# ── Helpers ──────────────────────────────────────────────────


def _make_task_with_complexity(
    *,
    complexity: Complexity,
    agent_id: str,
) -> Task:
    """Build a task with specific complexity for auto-loop tests."""
    return Task(
        id="task-auto-001",
        title="Auto-loop test task",
        description="A task for testing auto-loop selection.",
        type=TaskType.DEVELOPMENT,
        project="proj-001",
        created_by="manager",
        assigned_to=agent_id,
        status=TaskStatus.ASSIGNED,
        estimated_complexity=complexity,
    )


# ── Auto-loop selection ──────────────────────────────────────


@pytest.mark.unit
class TestAutoLoopSelection:
    """AgentEngine with auto_loop_config selects loop per task complexity."""

    async def test_simple_task_uses_react(
        self,
        sample_agent_with_personality: AgentIdentity,
        mock_provider_factory: type[MockCompletionProvider],
    ) -> None:
        response = _make_completion_response()
        provider = mock_provider_factory([response])
        engine = AgentEngine(
            provider=provider,
            auto_loop_config=AutoLoopConfig(),
        )
        task = _make_task_with_complexity(
            complexity=Complexity.SIMPLE,
            agent_id=str(sample_agent_with_personality.id),
        )

        with structlog.testing.capture_logs() as logs:
            result = await engine.run(
                identity=sample_agent_with_personality,
                task=task,
            )

        assert isinstance(result, AgentRunResult)
        selected_events = [
            e for e in logs if e.get("event") == EXECUTION_LOOP_AUTO_SELECTED
        ]
        assert len(selected_events) == 1
        assert selected_events[0]["selected_loop"] == "react"

    async def test_medium_task_uses_plan_execute(
        self,
        sample_agent_with_personality: AgentIdentity,
        mock_provider_factory: type[MockCompletionProvider],
    ) -> None:
        # Plan-execute needs: 1 planning response + 1 execution response
        plan_response = _make_completion_response(
            content=("1. Implement the feature\nExpected: Feature works correctly"),
        )
        exec_response = _make_completion_response(content="Done.")
        provider = mock_provider_factory([plan_response, exec_response])
        engine = AgentEngine(
            provider=provider,
            auto_loop_config=AutoLoopConfig(),
        )
        task = _make_task_with_complexity(
            complexity=Complexity.MEDIUM,
            agent_id=str(sample_agent_with_personality.id),
        )

        with structlog.testing.capture_logs() as logs:
            result = await engine.run(
                identity=sample_agent_with_personality,
                task=task,
            )

        assert isinstance(result, AgentRunResult)
        selected_events = [
            e for e in logs if e.get("event") == EXECUTION_LOOP_AUTO_SELECTED
        ]
        assert len(selected_events) == 1
        assert selected_events[0]["selected_loop"] == "plan_execute"


# ── Mutual exclusivity ──────────────────────────────────────


@pytest.mark.unit
class TestAutoLoopWithExplicitLoop:
    """execution_loop and auto_loop_config are mutually exclusive."""

    def test_both_raises_value_error(
        self,
        mock_provider_factory: type[MockCompletionProvider],
    ) -> None:
        provider = mock_provider_factory([])
        with pytest.raises(ValueError, match="mutually exclusive"):
            AgentEngine(
                provider=provider,
                execution_loop=ReactLoop(),
                auto_loop_config=AutoLoopConfig(),
            )


# ── Budget-aware selection ───────────────────────────────────


@pytest.mark.unit
class TestAutoLoopBudgetAware:
    """Budget state influences loop selection for complex tasks."""

    async def test_complex_tight_budget_uses_plan_execute(
        self,
        sample_agent_with_personality: AgentIdentity,
        mock_provider_factory: type[MockCompletionProvider],
    ) -> None:
        """Complex + tight budget => plan_execute (not hybrid)."""
        plan_response = _make_completion_response(
            content=("1. Implement the feature\nExpected: Feature works correctly"),
        )
        exec_response = _make_completion_response(content="Done.")
        provider = mock_provider_factory([plan_response, exec_response])

        cfg = BudgetConfig(
            total_monthly=100.0,
            alerts=BudgetAlertConfig(warn_at=70, critical_at=85, hard_stop_at=100),
        )
        tracker = CostTracker(budget_config=cfg)
        enforcer = BudgetEnforcer(budget_config=cfg, cost_tracker=tracker)

        engine = AgentEngine(
            provider=provider,
            auto_loop_config=AutoLoopConfig(budget_tight_threshold=80),
            budget_enforcer=enforcer,
        )

        task = _make_task_with_complexity(
            complexity=Complexity.COMPLEX,
            agent_id=str(sample_agent_with_personality.id),
        )

        # Mock utilization at 90% (above 80% threshold)
        with (
            patch.object(
                enforcer,
                "get_budget_utilization_pct",
                new_callable=AsyncMock,
                return_value=90.0,
            ),
            structlog.testing.capture_logs() as logs,
        ):
            result = await engine.run(
                identity=sample_agent_with_personality,
                task=task,
            )

        assert isinstance(result, AgentRunResult)
        selected_events = [
            e for e in logs if e.get("event") == EXECUTION_LOOP_AUTO_SELECTED
        ]
        assert len(selected_events) == 1
        assert selected_events[0]["selected_loop"] == "plan_execute"

    async def test_complex_ok_budget_uses_hybrid_fallback(
        self,
        sample_agent_with_personality: AgentIdentity,
        mock_provider_factory: type[MockCompletionProvider],
    ) -> None:
        """Complex + OK budget => hybrid -> fallback to plan_execute."""
        plan_response = _make_completion_response(
            content=("1. Implement the feature\nExpected: Feature works correctly"),
        )
        exec_response = _make_completion_response(content="Done.")
        provider = mock_provider_factory([plan_response, exec_response])

        cfg = BudgetConfig(
            total_monthly=100.0,
            alerts=BudgetAlertConfig(warn_at=70, critical_at=85, hard_stop_at=100),
        )
        tracker = CostTracker(budget_config=cfg)
        enforcer = BudgetEnforcer(budget_config=cfg, cost_tracker=tracker)

        engine = AgentEngine(
            provider=provider,
            auto_loop_config=AutoLoopConfig(),
            budget_enforcer=enforcer,
        )

        task = _make_task_with_complexity(
            complexity=Complexity.COMPLEX,
            agent_id=str(sample_agent_with_personality.id),
        )

        # Mock utilization at 30% (well below threshold)
        with (
            patch.object(
                enforcer,
                "get_budget_utilization_pct",
                new_callable=AsyncMock,
                return_value=30.0,
            ),
            structlog.testing.capture_logs() as logs,
        ):
            result = await engine.run(
                identity=sample_agent_with_personality,
                task=task,
            )

        assert isinstance(result, AgentRunResult)
        selected_events = [
            e for e in logs if e.get("event") == EXECUTION_LOOP_AUTO_SELECTED
        ]
        assert len(selected_events) == 1
        # Hybrid not implemented -> falls back to plan_execute
        assert selected_events[0]["selected_loop"] == "plan_execute"


# ── Budget error fallback ────────────────────────────────────


@pytest.mark.unit
class TestAutoLoopFallbackOnBudgetError:
    """Budget query failure => proceeds without budget awareness."""

    async def test_budget_error_still_selects_loop(
        self,
        sample_agent_with_personality: AgentIdentity,
        mock_provider_factory: type[MockCompletionProvider],
    ) -> None:
        plan_response = _make_completion_response(
            content=("1. Implement the feature\nExpected: Feature works correctly"),
        )
        exec_response = _make_completion_response(content="Done.")
        provider = mock_provider_factory([plan_response, exec_response])

        cfg = BudgetConfig(
            total_monthly=100.0,
            alerts=BudgetAlertConfig(warn_at=70, critical_at=85, hard_stop_at=100),
        )
        tracker = CostTracker(budget_config=cfg)
        enforcer = BudgetEnforcer(budget_config=cfg, cost_tracker=tracker)

        engine = AgentEngine(
            provider=provider,
            auto_loop_config=AutoLoopConfig(),
            budget_enforcer=enforcer,
        )

        task = _make_task_with_complexity(
            complexity=Complexity.COMPLEX,
            agent_id=str(sample_agent_with_personality.id),
        )

        # Budget query fails -> returns None -> no downgrade
        with (
            patch.object(
                enforcer,
                "get_budget_utilization_pct",
                new_callable=AsyncMock,
                return_value=None,
            ),
            structlog.testing.capture_logs() as logs,
        ):
            result = await engine.run(
                identity=sample_agent_with_personality,
                task=task,
            )

        assert isinstance(result, AgentRunResult)
        selected_events = [
            e for e in logs if e.get("event") == EXECUTION_LOOP_AUTO_SELECTED
        ]
        assert len(selected_events) == 1
        # Hybrid -> fallback to plan_execute (no budget downgrade since None)
        assert selected_events[0]["selected_loop"] == "plan_execute"
