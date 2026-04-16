"""Tests for the real ShadowEvaluationGuard."""

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from synthorg.core.agent import AgentIdentity, ModelConfig
from synthorg.core.enums import TaskType
from synthorg.core.task import AcceptanceCriterion, Task
from synthorg.engine.evolution.config import ShadowEvaluationConfig
from synthorg.engine.evolution.guards.shadow_evaluation import (
    ShadowEvaluationGuard,
)
from synthorg.engine.evolution.guards.shadow_protocol import (
    ShadowTaskOutcome,
)
from synthorg.engine.evolution.guards.shadow_providers import (
    ConfiguredShadowTaskProvider,
)
from synthorg.engine.evolution.models import (
    AdaptationAxis,
    AdaptationProposal,
    AdaptationSource,
)

if TYPE_CHECKING:
    from synthorg.versioning.models import VersionSnapshot


def _make_identity(agent_id: str = "agent-001") -> AgentIdentity:
    return AgentIdentity(
        id=uuid4(),
        name="Test Agent",
        role="test-role",
        department="test-dept",
        model=ModelConfig(
            provider="test-provider",
            model_id="test-medium-001",
        ),
        hiring_date=datetime.now(UTC).date(),
    )


def _make_task(task_id: str) -> Task:
    return Task(
        id=task_id,
        title=f"Task {task_id}",
        description=f"Description for {task_id}",
        type=TaskType.DEVELOPMENT,
        project="proj-shadow",
        created_by="test-creator",
        acceptance_criteria=(AcceptanceCriterion(description="Criterion 1"),),
    )


def _make_proposal(
    *,
    agent_id: str = "agent-001",
    axis: AdaptationAxis = AdaptationAxis.IDENTITY,
    changes: dict[str, object] | None = None,
) -> AdaptationProposal:
    return AdaptationProposal(
        agent_id=agent_id,
        axis=axis,
        description="Test proposal",
        changes=changes or {"name": "Evolved"},
        confidence=0.9,
        source=AdaptationSource.SUCCESS,
    )


class _FakeIdentityStore:
    """Minimal IdentityVersionStore stub returning a fixed identity."""

    def __init__(
        self,
        *,
        identity: AgentIdentity | None,
    ) -> None:
        self._identity = identity

    async def put(
        self,
        agent_id: str,
        identity: AgentIdentity,
        *,
        saved_by: str,
    ) -> VersionSnapshot[AgentIdentity]:
        msg = "put() not used by ShadowEvaluationGuard"
        raise NotImplementedError(msg)

    async def get_current(self, agent_id: str) -> AgentIdentity | None:
        return self._identity

    async def get_version(
        self,
        agent_id: str,
        version: int,
    ) -> AgentIdentity | None:
        return None

    async def list_versions(
        self,
        agent_id: str,
    ) -> tuple[VersionSnapshot[AgentIdentity], ...]:
        return ()

    async def set_current(
        self,
        agent_id: str,
        version: int,
    ) -> AgentIdentity:
        msg = "set_current() not used by ShadowEvaluationGuard"
        raise NotImplementedError(msg)


OutcomeFactory = Callable[[bool, AdaptationProposal | None, Task], ShadowTaskOutcome]


class _ScriptedRunner:
    """Configurable runner used in the tests.

    Callers supply an ``outcome_fn(proposal_is_adapted, proposal, task)``
    that returns a ``ShadowTaskOutcome``.  The runner records every call
    for assertions.
    """

    def __init__(self, outcome_fn: OutcomeFactory) -> None:
        self._outcome_fn = outcome_fn
        self.calls: list[tuple[bool, str]] = []

    async def run(
        self,
        *,
        identity: AgentIdentity,
        proposal: AdaptationProposal | None,
        task: Task,
        timeout_seconds: float,
    ) -> ShadowTaskOutcome:
        self.calls.append((proposal is not None, task.id))
        return self._outcome_fn(proposal is not None, proposal, task)


def _baseline_better_scripts(
    *,
    baseline_quality: float,
    adapted_quality: float,
) -> OutcomeFactory:
    def _fn(
        adapted: bool,
        proposal: AdaptationProposal | None,
        task: Task,
    ) -> ShadowTaskOutcome:
        return ShadowTaskOutcome(
            success=True,
            quality_score=adapted_quality if adapted else baseline_quality,
        )

    return _fn


def _config(
    *,
    probe_tasks: tuple[Task, ...] | None = None,
    score_tol: float = 0.05,
    pass_tol: float = 0.10,
) -> ShadowEvaluationConfig:
    tasks = (
        probe_tasks
        if probe_tasks is not None
        else (_make_task("probe-1"), _make_task("probe-2"))
    )
    return ShadowEvaluationConfig(
        probe_tasks=tasks,
        sample_size=5,
        timeout_per_task_seconds=5.0,
        score_regression_tolerance=score_tol,
        pass_rate_regression_tolerance=pass_tol,
    )


def _build_guard(
    *,
    config: ShadowEvaluationConfig,
    runner: _ScriptedRunner,
    identity: AgentIdentity | None,
) -> ShadowEvaluationGuard:
    provider = ConfiguredShadowTaskProvider(config=config)
    store = _FakeIdentityStore(identity=identity)
    return ShadowEvaluationGuard(
        config=config,
        task_provider=provider,
        runner=runner,
        identity_store=store,
    )


@pytest.mark.unit
class TestShadowEvaluationGuardApproval:
    async def test_approves_when_adapted_matches_baseline(self) -> None:
        runner = _ScriptedRunner(
            _baseline_better_scripts(
                baseline_quality=0.8,
                adapted_quality=0.8,
            )
        )
        guard = _build_guard(
            config=_config(),
            runner=runner,
            identity=_make_identity(),
        )
        decision = await guard.evaluate(_make_proposal())
        assert decision.approved is True
        assert "Shadow eval passed" in decision.reason

    async def test_approves_when_adapted_beats_baseline(self) -> None:
        runner = _ScriptedRunner(
            _baseline_better_scripts(
                baseline_quality=0.6,
                adapted_quality=0.9,
            )
        )
        guard = _build_guard(
            config=_config(),
            runner=runner,
            identity=_make_identity(),
        )
        decision = await guard.evaluate(_make_proposal())
        assert decision.approved is True

    async def test_approves_within_tolerance(self) -> None:
        runner = _ScriptedRunner(
            _baseline_better_scripts(
                baseline_quality=0.8,
                adapted_quality=0.77,
            )
        )
        guard = _build_guard(
            config=_config(score_tol=0.05),
            runner=runner,
            identity=_make_identity(),
        )
        decision = await guard.evaluate(_make_proposal())
        assert decision.approved is True


@pytest.mark.unit
class TestShadowEvaluationGuardRejection:
    async def test_rejects_score_regression_beyond_tolerance(self) -> None:
        runner = _ScriptedRunner(
            _baseline_better_scripts(
                baseline_quality=0.9,
                adapted_quality=0.5,
            )
        )
        guard = _build_guard(
            config=_config(score_tol=0.05),
            runner=runner,
            identity=_make_identity(),
        )
        decision = await guard.evaluate(_make_proposal())
        assert decision.approved is False
        assert "mean quality dropped" in decision.reason

    async def test_rejects_pass_rate_regression(self) -> None:
        # Baseline: 2/2 pass, Adapted: 0/2 pass -> pass rate drops 100%
        def _fn(
            adapted: bool,
            proposal: AdaptationProposal | None,
            task: Task,
        ) -> ShadowTaskOutcome:
            if adapted:
                return ShadowTaskOutcome(
                    success=False,
                    error="adapted failure",
                )
            return ShadowTaskOutcome(success=True, quality_score=0.9)

        runner = _ScriptedRunner(_fn)
        guard = _build_guard(
            config=_config(pass_tol=0.1),
            runner=runner,
            identity=_make_identity(),
        )
        decision = await guard.evaluate(_make_proposal())
        assert decision.approved is False
        assert "pass rate dropped" in decision.reason

    async def test_rejects_empty_suite(self) -> None:
        runner = _ScriptedRunner(
            _baseline_better_scripts(
                baseline_quality=0.9,
                adapted_quality=0.9,
            )
        )
        guard = _build_guard(
            config=_config(probe_tasks=()),
            runner=runner,
            identity=_make_identity(),
        )
        decision = await guard.evaluate(_make_proposal())
        assert decision.approved is False
        assert "probe task suite is empty" in decision.reason
        assert runner.calls == []  # runner never invoked

    async def test_rejects_when_identity_missing(self) -> None:
        runner = _ScriptedRunner(
            _baseline_better_scripts(
                baseline_quality=0.9,
                adapted_quality=0.9,
            )
        )
        guard = _build_guard(
            config=_config(),
            runner=runner,
            identity=None,
        )
        decision = await guard.evaluate(_make_proposal())
        assert decision.approved is False
        assert "baseline identity not found" in decision.reason
        assert runner.calls == []

    async def test_rejects_when_baseline_all_fail(self) -> None:
        def _fn(
            adapted: bool,
            proposal: AdaptationProposal | None,
            task: Task,
        ) -> ShadowTaskOutcome:
            return ShadowTaskOutcome(success=False, error="always fails")

        runner = _ScriptedRunner(_fn)
        guard = _build_guard(
            config=_config(),
            runner=runner,
            identity=_make_identity(),
        )
        decision = await guard.evaluate(_make_proposal())
        assert decision.approved is False
        assert "baseline had zero successful runs" in decision.reason

    async def test_counts_runner_exception_as_adapted_failure(self) -> None:
        def _fn(
            adapted: bool,
            proposal: AdaptationProposal | None,
            task: Task,
        ) -> ShadowTaskOutcome:
            if adapted:
                msg = "boom"
                raise RuntimeError(msg)
            return ShadowTaskOutcome(success=True, quality_score=0.9)

        runner = _ScriptedRunner(_fn)
        guard = _build_guard(
            config=_config(pass_tol=0.0),
            runner=runner,
            identity=_make_identity(),
        )
        decision = await guard.evaluate(_make_proposal())
        assert decision.approved is False
        assert "pass rate dropped" in decision.reason


@pytest.mark.unit
class TestShadowEvaluationGuardMetadata:
    async def test_name_is_shadow_evaluation_guard(self) -> None:
        runner = _ScriptedRunner(
            _baseline_better_scripts(
                baseline_quality=0.9,
                adapted_quality=0.9,
            )
        )
        guard = _build_guard(
            config=_config(),
            runner=runner,
            identity=_make_identity(),
        )
        assert guard.name == "ShadowEvaluationGuard"

    async def test_runs_baseline_and_adapted_in_parallel(self) -> None:
        barrier = asyncio.Barrier(2)

        async def _delayed_outcome(
            adapted: bool,
            proposal: AdaptationProposal | None,
            task: Task,
        ) -> ShadowTaskOutcome:
            return ShadowTaskOutcome(success=True, quality_score=0.9)

        async def _run(
            *,
            identity: AgentIdentity,
            proposal: AdaptationProposal | None,
            task: Task,
            timeout_seconds: float,
        ) -> ShadowTaskOutcome:
            # Both baseline and adapted must reach the barrier for this
            # to progress; if the guard ran them sequentially the test
            # would hang.
            async with asyncio.timeout(1.0):
                await barrier.wait()
            return await _delayed_outcome(proposal is not None, proposal, task)

        class _ParallelRunner:
            async def run(
                self,
                *,
                identity: AgentIdentity,
                proposal: AdaptationProposal | None,
                task: Task,
                timeout_seconds: float,
            ) -> ShadowTaskOutcome:
                return await _run(
                    identity=identity,
                    proposal=proposal,
                    task=task,
                    timeout_seconds=timeout_seconds,
                )

        config = _config(probe_tasks=(_make_task("only"),))
        provider = ConfiguredShadowTaskProvider(config=config)
        guard = ShadowEvaluationGuard(
            config=config,
            task_provider=provider,
            runner=_ParallelRunner(),
            identity_store=_FakeIdentityStore(identity=_make_identity()),
        )
        decision = await guard.evaluate(_make_proposal())
        assert decision.approved is True


@pytest.mark.unit
class TestShadowEvaluationGuardAxes:
    async def test_strategy_selection_axis_runs_real_evaluation(self) -> None:
        runner = _ScriptedRunner(
            _baseline_better_scripts(
                baseline_quality=0.8,
                adapted_quality=0.9,
            )
        )
        guard = _build_guard(
            config=_config(),
            runner=runner,
            identity=_make_identity(),
        )
        decision = await guard.evaluate(
            _make_proposal(axis=AdaptationAxis.STRATEGY_SELECTION)
        )
        assert decision.approved is True
        assert any(is_adapted for is_adapted, _ in runner.calls)
        assert any(not is_adapted for is_adapted, _ in runner.calls)

    async def test_prompt_template_axis_runs_real_evaluation(self) -> None:
        runner = _ScriptedRunner(
            _baseline_better_scripts(
                baseline_quality=0.8,
                adapted_quality=0.9,
            )
        )
        guard = _build_guard(
            config=_config(),
            runner=runner,
            identity=_make_identity(),
        )
        decision = await guard.evaluate(
            _make_proposal(axis=AdaptationAxis.PROMPT_TEMPLATE)
        )
        assert decision.approved is True
