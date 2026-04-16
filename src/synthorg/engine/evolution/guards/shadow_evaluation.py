"""Shadow evaluation guard.

Runs the adapted agent (proposal applied in a sandboxed way, never
persisted) and the baseline agent side by side against a probe task
suite, then approves the proposal only when the adapted agent does not
regress beyond the configured tolerances.

The guard composes pluggable pieces:

* ``ShadowTaskProvider`` -- sources the probe suite
  (``ConfiguredShadowTaskProvider`` or ``RecentTaskHistoryProvider``).
* ``ShadowAgentRunner`` -- executes a single task against an identity
  (+ optional proposal); the caller wires this to ``AgentEngine`` in
  production and supplies a deterministic fake in tests.
* ``IdentityVersionStore`` -- source of the current identity used as
  the baseline.

The decision predicate is strict: approve iff the score regression is
at or below ``score_regression_tolerance`` **and** the pass-rate
regression is at or below ``pass_rate_regression_tolerance * baseline``.
An empty probe suite, or any baseline failure, rejects the proposal --
shadow eval cannot approve into the void.
"""

import asyncio
import statistics
from typing import TYPE_CHECKING

from synthorg.engine.evolution.guards.shadow_protocol import ShadowTaskOutcome
from synthorg.engine.evolution.models import (
    AdaptationDecision,
    AdaptationProposal,
)
from synthorg.observability import get_logger
from synthorg.observability.events.evolution import (
    EVOLUTION_GUARDS_PASSED,
    EVOLUTION_GUARDS_REJECTED,
    EVOLUTION_SHADOW_COMPLETED,
    EVOLUTION_SHADOW_EMPTY_SUITE,
    EVOLUTION_SHADOW_INCONCLUSIVE,
    EVOLUTION_SHADOW_REGRESSION,
    EVOLUTION_SHADOW_STARTED,
    EVOLUTION_SHADOW_TASK_FAILED,
)

if TYPE_CHECKING:
    from synthorg.core.agent import AgentIdentity
    from synthorg.core.task import Task
    from synthorg.engine.evolution.config import ShadowEvaluationConfig
    from synthorg.engine.evolution.guards.shadow_protocol import (
        ShadowAgentRunner,
        ShadowTaskProvider,
    )
    from synthorg.engine.identity.store.protocol import IdentityVersionStore

logger = get_logger(__name__)


class _ShadowAggregate:
    """Aggregate stats from one side (baseline or adapted) of a run."""

    __slots__ = ("errors", "pass_rate", "score_mean", "success_count", "total")

    def __init__(
        self,
        *,
        outcomes: tuple[ShadowTaskOutcome, ...],
    ) -> None:
        self.total = len(outcomes)
        self.success_count = sum(1 for o in outcomes if o.success)
        self.pass_rate = self.success_count / self.total if self.total else 0.0
        scores = [o.quality_score for o in outcomes if o.quality_score is not None]
        self.score_mean = statistics.fmean(scores) if scores else None
        self.errors = tuple(o.error for o in outcomes if o.error is not None)


class ShadowEvaluationGuard:
    """Approve a proposal iff an adapted shadow run does not regress.

    Args:
        config: Shadow evaluation configuration (sample size, tolerances,
            timeouts, evaluator id).
        task_provider: Sources the probe task suite.
        runner: Executes a single task against a given identity and
            proposal (baseline runs pass ``proposal=None``).
        identity_store: Read-only source of the current identity.
    """

    def __init__(
        self,
        *,
        config: ShadowEvaluationConfig,
        task_provider: ShadowTaskProvider,
        runner: ShadowAgentRunner,
        identity_store: IdentityVersionStore,
    ) -> None:
        """Store dependencies."""
        self._config = config
        self._task_provider = task_provider
        self._runner = runner
        self._identity_store = identity_store

    @property
    def name(self) -> str:
        """Guard name."""
        return "ShadowEvaluationGuard"

    async def evaluate(
        self,
        proposal: AdaptationProposal,
    ) -> AdaptationDecision:
        """Run shadow evaluation and decide.

        Args:
            proposal: Proposal under review.

        Returns:
            ``AdaptationDecision`` approving or rejecting the proposal
            with an evidence-bearing reason.
        """
        logger.info(
            EVOLUTION_SHADOW_STARTED,
            proposal_id=str(proposal.id),
            agent_id=proposal.agent_id,
            axis=proposal.axis.value,
            guard_name=self.name,
        )

        tasks = await self._task_provider.sample(
            agent_id=proposal.agent_id,
            sample_size=self._config.sample_size,
        )
        if not tasks:
            return self._reject(
                proposal,
                event=EVOLUTION_SHADOW_EMPTY_SUITE,
                reason=(
                    "Shadow eval rejected: probe task suite is empty "
                    f"(provider={self._task_provider.name})"
                ),
            )

        identity = await self._identity_store.get_current(proposal.agent_id)
        if identity is None:
            return self._reject(
                proposal,
                event=EVOLUTION_SHADOW_INCONCLUSIVE,
                reason=(
                    "Shadow eval inconclusive: baseline identity not "
                    f"found for agent {proposal.agent_id}"
                ),
            )

        baseline, adapted = await self._run_both_passes(
            identity=identity,
            proposal=proposal,
            tasks=tasks,
        )

        baseline_stats = _ShadowAggregate(outcomes=baseline)
        adapted_stats = _ShadowAggregate(outcomes=adapted)

        if baseline_stats.success_count == 0:
            return self._reject(
                proposal,
                event=EVOLUTION_SHADOW_INCONCLUSIVE,
                reason=(
                    "Shadow eval inconclusive: baseline had zero "
                    f"successful runs across {baseline_stats.total} "
                    "probe tasks"
                ),
            )

        regression_reason = self._find_regression(
            baseline=baseline_stats,
            adapted=adapted_stats,
        )
        logger.info(
            EVOLUTION_SHADOW_COMPLETED,
            proposal_id=str(proposal.id),
            agent_id=proposal.agent_id,
            axis=proposal.axis.value,
            baseline_pass_rate=baseline_stats.pass_rate,
            adapted_pass_rate=adapted_stats.pass_rate,
            baseline_score=baseline_stats.score_mean,
            adapted_score=adapted_stats.score_mean,
            guard_name=self.name,
        )
        if regression_reason is not None:
            return self._reject(
                proposal,
                event=EVOLUTION_SHADOW_REGRESSION,
                reason=regression_reason,
            )
        return self._approve(
            proposal,
            baseline=baseline_stats,
            adapted=adapted_stats,
        )

    async def _run_both_passes(
        self,
        *,
        identity: AgentIdentity,
        proposal: AdaptationProposal,
        tasks: tuple[Task, ...],
    ) -> tuple[tuple[ShadowTaskOutcome, ...], tuple[ShadowTaskOutcome, ...]]:
        """Run baseline + adapted passes concurrently via ``TaskGroup``."""
        baseline_outcomes: tuple[ShadowTaskOutcome, ...] = ()
        adapted_outcomes: tuple[ShadowTaskOutcome, ...] = ()

        async def _baseline() -> None:
            nonlocal baseline_outcomes
            baseline_outcomes = await self._run_pass(
                identity=identity,
                proposal=None,
                tasks=tasks,
                label="baseline",
                proposal_id=str(proposal.id),
            )

        async def _adapted() -> None:
            nonlocal adapted_outcomes
            adapted_outcomes = await self._run_pass(
                identity=identity,
                proposal=proposal,
                tasks=tasks,
                label="adapted",
                proposal_id=str(proposal.id),
            )

        async with asyncio.TaskGroup() as tg:
            tg.create_task(_baseline())
            tg.create_task(_adapted())

        return baseline_outcomes, adapted_outcomes

    async def _run_pass(
        self,
        *,
        identity: AgentIdentity,
        proposal: AdaptationProposal | None,
        tasks: tuple[Task, ...],
        label: str,
        proposal_id: str,
    ) -> tuple[ShadowTaskOutcome, ...]:
        """Execute every task in a pass, converting errors to failed outcomes.

        Each task is wrapped in a safe-default helper so one task's
        failure never cancels the group.  ``MemoryError`` and
        ``RecursionError`` still propagate.
        """

        async def _one(task: Task) -> ShadowTaskOutcome:
            try:
                return await self._runner.run(
                    identity=identity,
                    proposal=proposal,
                    task=task,
                    timeout_seconds=self._config.timeout_per_task_seconds,
                )
            except MemoryError, RecursionError:
                raise
            except Exception as exc:
                logger.warning(
                    EVOLUTION_SHADOW_TASK_FAILED,
                    proposal_id=proposal_id,
                    pass_label=label,
                    task_id=task.id,
                    error=str(exc)[:200],
                )
                return ShadowTaskOutcome(
                    success=False,
                    quality_score=None,
                    error=str(exc)[:200] or "unknown runner error",
                )

        outcomes: list[ShadowTaskOutcome] = []
        async with asyncio.TaskGroup() as tg:
            coros = [tg.create_task(_one(t)) for t in tasks]
        outcomes.extend(c.result() for c in coros)
        return tuple(outcomes)

    def _find_regression(
        self,
        *,
        baseline: _ShadowAggregate,
        adapted: _ShadowAggregate,
    ) -> str | None:
        """Return a rejection reason string when adapted regresses, else None."""
        reasons: list[str] = []

        pass_rate_delta = baseline.pass_rate - adapted.pass_rate
        pass_rate_budget = (
            baseline.pass_rate * self._config.pass_rate_regression_tolerance
        )
        if pass_rate_delta > pass_rate_budget:
            reasons.append(
                f"pass rate dropped from {baseline.pass_rate:.2%} to "
                f"{adapted.pass_rate:.2%} "
                f"(tolerance {pass_rate_budget:.2%})"
            )

        if baseline.score_mean is not None and adapted.score_mean is not None:
            score_delta = baseline.score_mean - adapted.score_mean
            if score_delta > self._config.score_regression_tolerance:
                reasons.append(
                    f"mean quality dropped from {baseline.score_mean:.2f} "
                    f"to {adapted.score_mean:.2f} "
                    f"(tolerance {self._config.score_regression_tolerance:.2f})"
                )
        elif baseline.score_mean is not None and adapted.score_mean is None:
            reasons.append(
                "adapted run produced no gradable outcomes "
                f"while baseline mean was {baseline.score_mean:.2f}"
            )

        if not reasons:
            return None
        return "Shadow eval regression: " + "; ".join(reasons)

    def _approve(
        self,
        proposal: AdaptationProposal,
        *,
        baseline: _ShadowAggregate,
        adapted: _ShadowAggregate,
    ) -> AdaptationDecision:
        """Build an approval decision with a summary reason."""
        score_adapted = (
            f"{adapted.score_mean:.2f}" if adapted.score_mean is not None else "n/a"
        )
        score_baseline = (
            f"{baseline.score_mean:.2f}" if baseline.score_mean is not None else "n/a"
        )
        reason = (
            "Shadow eval passed: "
            f"pass rate {baseline.pass_rate:.2%} -> {adapted.pass_rate:.2%}, "
            f"mean score {score_baseline} -> {score_adapted} "
            f"across {baseline.total} probe tasks"
        )
        logger.info(
            EVOLUTION_GUARDS_PASSED,
            proposal_id=str(proposal.id),
            guard_name=self.name,
        )
        return AdaptationDecision(
            proposal_id=proposal.id,
            approved=True,
            guard_name=self.name,
            reason=reason,
        )

    def _reject(
        self,
        proposal: AdaptationProposal,
        *,
        event: str,
        reason: str,
    ) -> AdaptationDecision:
        """Build a rejection decision, logging the triggering event."""
        logger.warning(
            event,
            proposal_id=str(proposal.id),
            agent_id=proposal.agent_id,
            axis=proposal.axis.value,
            guard_name=self.name,
            reason=reason,
        )
        logger.info(
            EVOLUTION_GUARDS_REJECTED,
            proposal_id=str(proposal.id),
            guard_name=self.name,
        )
        return AdaptationDecision(
            proposal_id=proposal.id,
            approved=False,
            guard_name=self.name,
            reason=reason,
        )
