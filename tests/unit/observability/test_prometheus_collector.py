"""Tests for the Prometheus metrics collector."""

from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest
from prometheus_client import generate_latest

from synthorg.observability.prometheus_collector import PrometheusCollector


def _mock_app_state(
    *,
    has_cost_tracker: bool = False,
    has_agent_registry: bool = False,
    total_cost: float = 0.0,
    agent_count: int = 0,
    agents: tuple[object, ...] = (),
) -> MagicMock:
    """Build a mock AppState with configurable service availability."""
    state = MagicMock()
    type(state).has_cost_tracker = PropertyMock(return_value=has_cost_tracker)
    type(state).has_agent_registry = PropertyMock(
        return_value=has_agent_registry,
    )
    type(state).has_task_engine = PropertyMock(return_value=False)

    if has_cost_tracker:
        tracker = AsyncMock()
        tracker.get_total_cost = AsyncMock(return_value=total_cost)
        tracker.budget_config = None
        type(state).cost_tracker = PropertyMock(return_value=tracker)

    if has_agent_registry:
        registry = AsyncMock()
        registry.agent_count = AsyncMock(return_value=agent_count)
        registry.list_active = AsyncMock(return_value=agents)
        type(state).agent_registry = PropertyMock(return_value=registry)

    return state


def _make_agent(*, status: str = "active") -> MagicMock:
    """Build a mock AgentIdentity with a given status."""
    agent = MagicMock()
    agent.status = status
    agent.id = f"agent-{status}"
    return agent


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
        # Should not error; info metric still present
        assert "synthorg_app_info" in output

    async def test_refresh_updates_cost_total(self) -> None:
        collector = PrometheusCollector()
        state = _mock_app_state(has_cost_tracker=True, total_cost=42.5)
        await collector.refresh(state)
        output = generate_latest(collector.registry).decode()
        assert "synthorg_cost_total" in output
        assert "42.5" in output

    async def test_refresh_updates_agent_count(self) -> None:
        collector = PrometheusCollector()
        agents = (
            _make_agent(status="active"),
            _make_agent(status="active"),
            _make_agent(status="onboarding"),
        )
        state = _mock_app_state(
            has_agent_registry=True,
            agent_count=3,
            agents=agents,
        )
        await collector.refresh(state)
        output = generate_latest(collector.registry).decode()
        assert "synthorg_agents_total" in output

    async def test_refresh_skips_unavailable_services(self) -> None:
        collector = PrometheusCollector()
        state = _mock_app_state(
            has_cost_tracker=False,
            has_agent_registry=False,
        )
        # Should not raise
        await collector.refresh(state)

    async def test_refresh_handles_service_errors(self) -> None:
        collector = PrometheusCollector()
        state = _mock_app_state(has_cost_tracker=True)
        state.cost_tracker.get_total_cost = AsyncMock(
            side_effect=RuntimeError("tracker down"),
        )
        # Should not raise -- errors are logged, not propagated
        await collector.refresh(state)


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
        # Check label values present
        assert 'verdict="allow"' in output
        assert 'verdict="deny"' in output


@pytest.mark.unit
class TestPrometheusCollectorOutput:
    """Tests for the exposition format output."""

    async def test_output_is_valid_exposition_format(self) -> None:
        collector = PrometheusCollector()
        state = _mock_app_state(
            has_cost_tracker=True,
            total_cost=10.0,
            has_agent_registry=True,
            agent_count=2,
            agents=(
                _make_agent(status="active"),
                _make_agent(status="active"),
            ),
        )
        await collector.refresh(state)
        output = generate_latest(collector.registry)
        assert isinstance(output, bytes)
        text = output.decode()
        # Exposition format uses HELP and TYPE lines
        assert "# HELP" in text
        assert "# TYPE" in text

    async def test_custom_prefix(self) -> None:
        collector = PrometheusCollector(prefix="myorg")
        output = generate_latest(collector.registry).decode()
        assert "myorg_app_info" in output
        assert "synthorg_app_info" not in output
