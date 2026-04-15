"""Self-improvement service orchestrator.

Central service that ties together signal aggregation, rule
evaluation, strategy dispatch, guard chain, rollout execution,
and Chief of Staff confidence learning.
"""

import asyncio
from typing import TYPE_CHECKING

from synthorg.core.types import NotBlankStr
from synthorg.meta.chief_of_staff.events import (
    COS_LEARNING_ENABLED,
    COS_OUTCOME_RECORD_FAILED,
)
from synthorg.meta.chief_of_staff.models import ProposalOutcome
from synthorg.meta.chief_of_staff.outcome_store import MemoryBackendOutcomeStore
from synthorg.meta.factory import (
    build_appliers,
    build_confidence_adjuster,
    build_guards,
    build_regression_detector,
    build_rollout_strategies,
    build_rule_engine,
    build_strategies,
)
from synthorg.meta.models import (
    GuardVerdict,
    ImprovementProposal,
    OrgSignalSnapshot,
    ProposalStatus,
    RolloutResult,
)
from synthorg.observability import get_logger
from synthorg.observability.events.meta import (
    META_CYCLE_COMPLETED,
    META_CYCLE_NO_TRIGGERS,
    META_CYCLE_STARTED,
    META_PROPOSAL_GUARD_REJECTED,
)

if TYPE_CHECKING:
    from synthorg.memory.protocol import MemoryBackend
    from synthorg.meta.chief_of_staff.protocol import ConfidenceAdjuster
    from synthorg.meta.config import SelfImprovementConfig
    from synthorg.meta.models import RuleMatch
    from synthorg.meta.protocol import ImprovementStrategy

logger = get_logger(__name__)


class SelfImprovementService:
    """Orchestrates the self-improvement meta-loop cycle.

    1. Evaluates signal snapshot against rules.
    2. Dispatches to strategies for matching altitudes.
    3. Adjusts proposal confidence via historical learning.
    4. Runs proposals through the guard chain.
    5. Returns proposals that passed all guards (ready for approval).

    Args:
        config: Self-improvement configuration.
        memory_backend: Memory backend for outcome learning.
    """

    def __init__(
        self,
        *,
        config: SelfImprovementConfig,
        memory_backend: MemoryBackend | None = None,
    ) -> None:
        self._config = config
        self._rule_engine = build_rule_engine(config)
        self._strategies = build_strategies(config)
        self._guards = build_guards(config)
        self._appliers = build_appliers()
        self._detector = build_regression_detector()
        self._rollout_strategies = build_rollout_strategies()

        # Chief of Staff learning.
        self._outcome_store: MemoryBackendOutcomeStore | None = None
        self._confidence_adjuster: ConfidenceAdjuster | None = None
        if config.chief_of_staff.learning_enabled and memory_backend is not None:
            self._outcome_store = MemoryBackendOutcomeStore(
                backend=memory_backend,
                agent_id=NotBlankStr("chief-of-staff"),
                min_outcomes=config.chief_of_staff.min_outcomes,
            )
            self._confidence_adjuster = build_confidence_adjuster(config)
            logger.info(
                COS_LEARNING_ENABLED,
                strategy=config.chief_of_staff.adjuster_strategy,
            )

    async def run_cycle(
        self,
        snapshot: OrgSignalSnapshot,
    ) -> tuple[ImprovementProposal, ...]:
        """Run a complete improvement cycle.

        Evaluates rules, generates proposals, filters through
        guards, and returns proposals ready for human approval.

        Args:
            snapshot: Current org-wide signal snapshot.

        Returns:
            Proposals that passed all guards (awaiting approval).
        """
        logger.info(META_CYCLE_STARTED)

        # Step 1: Evaluate rules.
        matches = self._rule_engine.evaluate(snapshot)
        if not matches:
            logger.info(META_CYCLE_NO_TRIGGERS)
            return ()

        # Step 2: Generate proposals from strategies (parallel).
        all_proposals = await self._dispatch_strategies(snapshot, matches)

        # Step 2.5: Adjust confidence via historical learning.
        if self._confidence_adjuster is not None and self._outcome_store is not None:
            all_proposals = [
                await self._confidence_adjuster.adjust(p, self._outcome_store)
                for p in all_proposals
            ]

        # Step 3: Filter through guard chain.
        approved: list[ImprovementProposal] = []
        for proposal in all_proposals:
            passed = True
            for guard in self._guards:
                result = await guard.evaluate(proposal)
                if result.verdict == GuardVerdict.REJECTED:
                    logger.info(
                        META_PROPOSAL_GUARD_REJECTED,
                        guard=guard.name,
                        proposal_id=str(proposal.id),
                        reason=result.reason,
                    )
                    passed = False
                    break
            if passed:
                approved.append(proposal)

        logger.info(
            META_CYCLE_COMPLETED,
            total_matches=len(matches),
            proposals_generated=len(all_proposals),
            proposals_approved=len(approved),
        )
        return tuple(approved)

    async def execute_rollout(
        self,
        proposal: ImprovementProposal,
    ) -> RolloutResult:
        """Execute a rollout for an approved proposal.

        Args:
            proposal: The human-approved proposal.

        Returns:
            Rollout result.
        """
        if proposal.status is not ProposalStatus.APPROVED:
            msg = (
                f"Proposal {proposal.id} must be approved before "
                f"rollout; current status is {proposal.status.value}"
            )
            logger.error(msg, proposal_id=str(proposal.id))
            raise ValueError(msg)

        applier = self._appliers.get(proposal.altitude)
        if applier is None:
            msg = f"No applier for altitude {proposal.altitude}"
            logger.error(msg, altitude=proposal.altitude.value)
            raise ValueError(msg)

        strategy_name = proposal.rollout_strategy.value
        rollout = self._rollout_strategies.get(strategy_name)
        if rollout is None:
            msg = f"No rollout strategy '{strategy_name}'"
            logger.error(msg, strategy=strategy_name)
            raise ValueError(msg)

        return await rollout.execute(
            proposal=proposal,
            applier=applier,
            detector=self._detector,
        )

    async def _dispatch_strategies(
        self,
        snapshot: OrgSignalSnapshot,
        matches: tuple[RuleMatch, ...],
    ) -> list[ImprovementProposal]:
        """Run strategies in parallel via TaskGroup."""
        results: list[ImprovementProposal] = []

        async def _run(
            strategy: ImprovementStrategy,
            relevant: tuple[RuleMatch, ...],
        ) -> tuple[ImprovementProposal, ...]:
            return await strategy.propose(
                snapshot=snapshot,
                triggered_rules=relevant,
            )

        pairs: list[tuple[ImprovementStrategy, tuple[RuleMatch, ...]]] = []
        for strategy in self._strategies:
            relevant = tuple(
                m for m in matches if strategy.altitude in m.suggested_altitudes
            )
            if relevant:
                pairs.append((strategy, relevant))

        if pairs:
            async with asyncio.TaskGroup() as tg:
                tasks = [tg.create_task(_run(s, r)) for s, r in pairs]
            for task in tasks:
                results.extend(task.result())

        return results

    async def record_decision(
        self,
        proposal: ImprovementProposal,
    ) -> None:
        """Record a decided proposal as an outcome for learning.

        Called by the approval API after a human approves or
        rejects a proposal. Silently returns if learning is
        disabled or the proposal lacks decision fields.

        Args:
            proposal: The decided proposal.
        """
        if self._outcome_store is None:
            return
        if proposal.decided_at is None or proposal.decided_by is None:
            return
        if proposal.status not in (
            ProposalStatus.APPROVED,
            ProposalStatus.REJECTED,
        ):
            return
        decision = (
            "approved" if proposal.status is ProposalStatus.APPROVED else "rejected"
        )
        outcome = ProposalOutcome(
            proposal_id=proposal.id,
            title=proposal.title,
            altitude=proposal.altitude,
            source_rule=proposal.source_rule,
            decision=decision,
            confidence_at_decision=proposal.confidence,
            decided_at=proposal.decided_at,
            decided_by=proposal.decided_by,
            decision_reason=proposal.decision_reason,
        )
        try:
            await self._outcome_store.record_outcome(outcome)
        except Exception:
            logger.exception(
                COS_OUTCOME_RECORD_FAILED,
                proposal_id=str(proposal.id),
            )
