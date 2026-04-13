"""Tests for EvalLoopCoordinator."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from synthorg.hr.evaluation.config import EvalLoopConfig
from synthorg.hr.evaluation.loop_coordinator import EvalLoopCoordinator


def _make_coordinator(
    *,
    config: EvalLoopConfig | None = None,
    task_metrics: tuple[MagicMock, ...] = (),
    eval_report: MagicMock | None = None,
) -> EvalLoopCoordinator:
    """Build an EvalLoopCoordinator with mocked dependencies."""
    tracker = MagicMock()
    tracker.get_task_metrics.return_value = task_metrics

    evaluation = MagicMock()
    # evaluate must return None (indicating skip) to avoid Pydantic
    # validation of MagicMock as EvaluationReport in EvalCycleReport.
    if eval_report is not None:
        evaluation.evaluate = AsyncMock(return_value=eval_report)
    else:
        evaluation.evaluate = AsyncMock(return_value=None)

    scorer = MagicMock()
    training = MagicMock()
    dataset_builder = MagicMock()
    benchmark_registry = MagicMock()
    benchmark_registry.list_registered.return_value = ()

    return EvalLoopCoordinator(
        performance_tracker=tracker,
        evaluation_service=evaluation,
        trajectory_scorer=scorer,
        training_service=training,
        dataset_builder=dataset_builder,
        benchmark_registry=benchmark_registry,
        config=config,
    )


def _make_task_record(agent_id: str = "agent-1") -> MagicMock:
    record = MagicMock()
    record.agent_id = agent_id
    return record


@pytest.mark.unit
class TestEvalLoopCoordinatorInit:
    """EvalLoopCoordinator construction."""

    def test_default_config(self) -> None:
        coordinator = _make_coordinator()
        assert coordinator.config.enabled is True

    def test_custom_config(self) -> None:
        config = EvalLoopConfig(enabled=False)
        coordinator = _make_coordinator(config=config)
        assert coordinator.config.enabled is False


@pytest.mark.unit
class TestEvalLoopCoordinatorRunCycle:
    """EvalLoopCoordinator.run_cycle()."""

    async def test_run_cycle_empty_window(self) -> None:
        coordinator = _make_coordinator()
        report = await coordinator.run_cycle(window=timedelta(hours=1))
        assert report.agents_evaluated == 0
        assert report.agent_reports == ()
        assert report.observations == ()
        assert report.proposed_actions == ()
        assert report.training_triggered is False

    async def test_run_cycle_with_agents(self) -> None:
        records = (
            _make_task_record("agent-1"),
            _make_task_record("agent-2"),
            _make_task_record("agent-1"),  # duplicate
        )
        coordinator = _make_coordinator(task_metrics=records)
        report = await coordinator.run_cycle(window=timedelta(hours=1))
        # 2 unique agents
        assert report.agents_evaluated == 2

    async def test_run_cycle_with_explicit_agent_ids(self) -> None:
        coordinator = _make_coordinator()
        report = await coordinator.run_cycle(
            window=timedelta(hours=1),
            agent_ids=("agent-x",),
        )
        assert report.agents_evaluated == 1

    async def test_run_cycle_report_timing(self) -> None:
        coordinator = _make_coordinator()
        before = datetime.now(UTC)
        report = await coordinator.run_cycle(window=timedelta(hours=1))
        assert report.duration_seconds >= 0.0
        assert report.window_end >= before
        assert report.window_start < report.window_end

    async def test_run_cycle_stubs_return_empty(self) -> None:
        coordinator = _make_coordinator()
        report = await coordinator.run_cycle(window=timedelta(hours=1))
        assert report.observations == ()
        assert report.proposed_actions == ()

    async def test_run_cycle_no_benchmarks_by_default(self) -> None:
        coordinator = _make_coordinator()
        report = await coordinator.run_cycle(window=timedelta(hours=1))
        assert report.benchmark_results == ()

    async def test_run_cycle_benchmarks_when_enabled(self) -> None:
        config = EvalLoopConfig(benchmark_on_cycle=True)
        coordinator = _make_coordinator(config=config)
        report = await coordinator.run_cycle(window=timedelta(hours=1))
        assert report.benchmark_results == ()  # No benchmarks registered


@pytest.mark.unit
class TestEvalLoopCoordinatorEvaluateOne:
    """EvalLoopCoordinator._evaluate_one() isolation."""

    async def test_evaluate_one_success(self) -> None:
        mock_report = MagicMock()
        coordinator = _make_coordinator(eval_report=mock_report)
        result = await coordinator._evaluate_one("agent-1")
        assert result is mock_report

    async def test_evaluate_one_failure_returns_none(self) -> None:
        coordinator = _make_coordinator()
        coordinator._evaluation.evaluate = AsyncMock(
            side_effect=RuntimeError("eval failed"),
        )
        result = await coordinator._evaluate_one("agent-1")
        assert result is None


@pytest.mark.unit
class TestEvalLoopCoordinatorCollectAgentIds:
    """EvalLoopCoordinator._collect_agent_ids()."""

    def test_deduplicates_ids(self) -> None:
        records = (
            _make_task_record("a"),
            _make_task_record("b"),
            _make_task_record("a"),
        )
        coordinator = _make_coordinator(task_metrics=records)
        ids = coordinator._collect_agent_ids(
            since=datetime(2020, 1, 1, tzinfo=UTC),
        )
        assert ids == ("a", "b")

    def test_empty_records(self) -> None:
        coordinator = _make_coordinator()
        ids = coordinator._collect_agent_ids(
            since=datetime(2020, 1, 1, tzinfo=UTC),
        )
        assert ids == ()
