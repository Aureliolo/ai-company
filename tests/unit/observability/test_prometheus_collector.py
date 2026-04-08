"""Tests for the Prometheus metrics collector."""

from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest
from prometheus_client import generate_latest

from synthorg.observability.prometheus_collector import PrometheusCollector


def _mock_app_state(  # noqa: PLR0913
    *,
    has_cost_tracker: bool = False,
    has_agent_registry: bool = False,
    has_task_engine: bool = False,
    total_cost: float = 0.0,
    agents: tuple[object, ...] = (),
    tasks: tuple[object, ...] = (),
    budget_total_monthly: float | None = None,
) -> MagicMock:
    """Build a mock AppState with configurable service availability."""
    state = MagicMock()
    type(state).has_cost_tracker = PropertyMock(return_value=has_cost_tracker)
    type(state).has_agent_registry = PropertyMock(
        return_value=has_agent_registry,
    )
    type(state).has_task_engine = PropertyMock(return_value=has_task_engine)

    if has_cost_tracker:
        tracker = AsyncMock()
        tracker.get_total_cost = AsyncMock(return_value=total_cost)
        if budget_total_monthly is not None:
            budget_cfg = MagicMock()
            budget_cfg.total_monthly = budget_total_monthly
            tracker.budget_config = budget_cfg
        else:
            tracker.budget_config = None
        type(state).cost_tracker = PropertyMock(return_value=tracker)

    if has_agent_registry:
        registry = AsyncMock()
        registry.list_active = AsyncMock(return_value=agents)
        type(state).agent_registry = PropertyMock(return_value=registry)

    if has_task_engine:
        engine = AsyncMock()
        engine.list_tasks = AsyncMock(return_value=(tasks, len(tasks)))
        type(state).task_engine = PropertyMock(return_value=engine)

    return state


def _make_agent(
    *,
    status: str = "active",
    access_level: str = "standard",
) -> MagicMock:
    """Build a mock AgentIdentity with status and trust level."""
    agent = MagicMock()
    agent.status = status
    agent.tools.access_level = access_level
    agent.id = f"agent-{status}-{access_level}"
    return agent


def _make_task(
    *,
    status: str = "created",
    assigned_to: str | None = None,
) -> MagicMock:
    """Build a mock Task with a given status and optional agent."""
    task = MagicMock()
    task.status = status
    task.assigned_to = assigned_to
    return task


@pytest.mark.unit
class TestPrometheusCollectorInit:
    """Tests for collector initialization."""

    def test_creates_registry(self) -> None:
        collector = PrometheusCollector()
        assert collector.registry is not None

    def test_registry_is_isolated(self) -> None:
        c1 = PrometheusCollector()
        c2 = PrometheusCollector()
        assert c1.registry is not c2.registry

    def test_generate_latest_returns_bytes(self) -> None:
        collector = PrometheusCollector()
        output = generate_latest(collector.registry)
        assert isinstance(output, bytes)

    def test_info_metric_present(self) -> None:
        collector = PrometheusCollector()
        output = generate_latest(collector.registry).decode()
        assert "synthorg_app_info" in output


@pytest.mark.unit
class TestPrometheusCollectorRefresh:
    """Tests for the async refresh method."""

    async def test_refresh_with_no_services(self) -> None:
        collector = PrometheusCollector()
        state = _mock_app_state()
        await collector.refresh(state)
        output = generate_latest(collector.registry).decode()
        assert "synthorg_app_info" in output

    async def test_refresh_updates_cost_total(self) -> None:
        collector = PrometheusCollector()
        state = _mock_app_state(has_cost_tracker=True, total_cost=42.5)
        await collector.refresh(state)
        output = generate_latest(collector.registry).decode()
        assert "synthorg_cost_total" in output
        assert "42.5" in output

    async def test_refresh_updates_agent_count_with_trust_level(self) -> None:
        collector = PrometheusCollector()
        agents = (
            _make_agent(status="active", access_level="standard"),
            _make_agent(status="active", access_level="elevated"),
            _make_agent(status="onboarding", access_level="restricted"),
        )
        state = _mock_app_state(has_agent_registry=True, agents=agents)
        await collector.refresh(state)
        output = generate_latest(collector.registry).decode()
        assert "synthorg_active_agents_total" in output
        assert 'trust_level="standard"' in output
        assert 'trust_level="elevated"' in output

    async def test_refresh_updates_task_counts(self) -> None:
        collector = PrometheusCollector()
        tasks = (
            _make_task(status="created"),
            _make_task(status="in_progress"),
            _make_task(status="in_progress"),
            _make_task(status="completed"),
        )
        state = _mock_app_state(has_task_engine=True, tasks=tasks)
        await collector.refresh(state)
        output = generate_latest(collector.registry).decode()
        assert "synthorg_tasks_total" in output
        assert 'status="in_progress"' in output

    async def test_refresh_updates_budget_utilization(self) -> None:
        collector = PrometheusCollector()
        state = _mock_app_state(
            has_cost_tracker=True,
            total_cost=50.0,
            budget_total_monthly=200.0,
        )
        await collector.refresh(state)
        output = generate_latest(collector.registry).decode()
        assert "synthorg_budget_used_percent" in output
        assert "synthorg_budget_monthly_usd" in output
        assert "25.0" in output  # 50/200 * 100

    async def test_refresh_skips_budget_when_no_config(self) -> None:
        collector = PrometheusCollector()
        state = _mock_app_state(
            has_cost_tracker=True,
            total_cost=50.0,
            budget_total_monthly=None,
        )
        await collector.refresh(state)
        # Should not error -- budget metrics simply not set

    async def test_refresh_skips_unavailable_services(self) -> None:
        collector = PrometheusCollector()
        state = _mock_app_state(
            has_cost_tracker=False,
            has_agent_registry=False,
            has_task_engine=False,
        )
        await collector.refresh(state)

    async def test_cost_tracker_error_does_not_block_agents(self) -> None:
        """Partial failure: cost tracker fails, agent registry succeeds."""
        collector = PrometheusCollector()
        agents = (_make_agent(status="active"),)
        state = _mock_app_state(
            has_cost_tracker=True,
            has_agent_registry=True,
            agents=agents,
        )
        state.cost_tracker.get_total_cost = AsyncMock(
            side_effect=RuntimeError("tracker down"),
        )
        await collector.refresh(state)
        output = generate_latest(collector.registry).decode()
        assert "synthorg_active_agents_total" in output

    async def test_agent_registry_error_does_not_block_tasks(self) -> None:
        """Partial failure: agent registry fails, task engine succeeds."""
        collector = PrometheusCollector()
        tasks = (_make_task(status="created"),)
        state = _mock_app_state(
            has_agent_registry=True,
            has_task_engine=True,
            tasks=tasks,
        )
        state.agent_registry.list_active = AsyncMock(
            side_effect=RuntimeError("registry down"),
        )
        await collector.refresh(state)
        output = generate_latest(collector.registry).decode()
        assert "synthorg_tasks_total" in output


@pytest.mark.unit
class TestPrometheusCollectorSecurityVerdicts:
    """Tests for security verdict counter."""

    def test_record_verdict_increments_counter(self) -> None:
        collector = PrometheusCollector()
        collector.record_security_verdict("allow")
        collector.record_security_verdict("allow")
        collector.record_security_verdict("deny")
        output = generate_latest(collector.registry).decode()
        assert "synthorg_security_evaluations_total" in output
        assert 'verdict="allow"' in output
        assert 'verdict="deny"' in output


@pytest.mark.unit
class TestPrometheusCollectorCoordination:
    """Tests for push-updated coordination metrics."""

    def test_record_coordination_metrics(self) -> None:
        collector = PrometheusCollector()
        collector.record_coordination_metrics(
            efficiency=0.85,
            overhead_percent=15.0,
        )
        output = generate_latest(collector.registry).decode()
        assert "synthorg_coordination_efficiency" in output
        assert "synthorg_coordination_overhead_percent" in output


@pytest.mark.unit
class TestPrometheusCollectorOutput:
    """Tests for the exposition format output."""

    async def test_output_is_valid_exposition_format(self) -> None:
        collector = PrometheusCollector()
        state = _mock_app_state(
            has_cost_tracker=True,
            total_cost=10.0,
            has_agent_registry=True,
            agents=(
                _make_agent(status="active"),
                _make_agent(status="active"),
            ),
        )
        await collector.refresh(state)
        output = generate_latest(collector.registry)
        assert isinstance(output, bytes)
        text = output.decode()
        assert "# HELP" in text
        assert "# TYPE" in text

    async def test_custom_prefix(self) -> None:
        collector = PrometheusCollector(prefix="myorg")
        output = generate_latest(collector.registry).decode()
        assert "myorg_app_info" in output
        assert "synthorg_app_info" not in output
