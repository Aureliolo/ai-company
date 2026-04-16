"""Self-improvement service orchestrator.

Central service that ties together signal aggregation, rule
evaluation, strategy dispatch, guard chain, rollout execution,
and Chief of Staff confidence learning.
"""

import asyncio
from typing import TYPE_CHECKING, Literal

from synthorg.core.types import NotBlankStr
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
    ProposalAltitude,
    ProposalStatus,
    RegressionThresholds,
    RegressionVerdict,
    RolloutOutcome,
    RolloutResult,
)
from synthorg.meta.rules.builtin import default_rules
from synthorg.meta.telemetry.factory import build_analytics_emitter
from synthorg.observability import get_logger
from synthorg.observability.events.chief_of_staff import (
    COS_CONFIDENCE_ADJUSTMENT_FAILED,
    COS_LEARNING_ENABLED,
    COS_OUTCOME_RECORD_FAILED,
    COS_OUTCOME_SKIPPED,
)
from synthorg.observability.events.cross_deployment import (
    XDEPLOY_EVENT_EMIT_FAILED,
)
from synthorg.observability.events.meta import (
    META_CODE_GITHUB_CREDS_INVALID,
    META_CODE_GITHUB_CREDS_VALID,
    META_CYCLE_COMPLETED,
    META_CYCLE_NO_TRIGGERS,
    META_CYCLE_STARTED,
    META_PROPOSAL_GUARD_REJECTED,
    META_ROLLOUT_PRECONDITION_FAILED,
    META_ROLLOUT_REGRESSION_DETECTED,
    META_SERVICE_CLOSE_FAILED,
)

if TYPE_CHECKING:
    from synthorg.memory.protocol import MemoryBackend
    from synthorg.meta.appliers.architecture_applier import (
        ArchitectureApplierContext,
    )
    from synthorg.meta.appliers.config_applier import ConfigProvider
    from synthorg.meta.appliers.prompt_applier import PromptApplierContext
    from synthorg.meta.chief_of_staff.protocol import ConfidenceAdjuster
    from synthorg.meta.config import SelfImprovementConfig
    from synthorg.meta.models import RuleMatch
    from synthorg.meta.protocol import (
        ImprovementStrategy,
        ProposalApplier,
        RolloutStrategy,
    )
    from synthorg.meta.telemetry.protocol import AnalyticsEmitter
    from synthorg.providers.base import BaseCompletionProvider

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
        provider: Completion provider for LLM-based strategies.
            When code_modification_enabled is True but provider is
            None, the code modification strategy is silently skipped.
        config_provider: Zero-arg callable returning the current
            ``RootConfig`` snapshot.  Required for
            ``ConfigApplier.dry_run``; callers that omit it get an
            applier whose ``dry_run`` rejects with an explicit error.
        prompt_context: Read-only view of prompt-scope targets wired
            into ``PromptApplier.dry_run``.  Callers that omit it get
            an applier whose ``dry_run`` rejects with an explicit
            error.
        architecture_context: Read-only view of role / department /
            workflow registries wired into
            ``ArchitectureApplier.dry_run``.  Callers that omit it
            get an applier whose ``dry_run`` rejects with an explicit
            error.
    """

    def __init__(  # noqa: PLR0913
        self,
        *,
        config: SelfImprovementConfig,
        memory_backend: MemoryBackend | None = None,
        provider: BaseCompletionProvider | None = None,
        config_provider: ConfigProvider | None = None,
        prompt_context: PromptApplierContext | None = None,
        architecture_context: ArchitectureApplierContext | None = None,
    ) -> None:
        self._config = config
        self._rule_engine = build_rule_engine(config)
        self._strategies = build_strategies(config, provider=provider)
        self._guards = build_guards(config)
        self._appliers = build_appliers(
            config,
            config_provider=config_provider,
            prompt_context=prompt_context,
            architecture_context=architecture_context,
        )
        self._detector = build_regression_detector()
        self._rollout_strategies = build_rollout_strategies(config)

        # Cross-deployment analytics emitter.
        builtin_names = frozenset(r.name for r in default_rules())
        self._analytics_emitter: AnalyticsEmitter | None = build_analytics_emitter(
            config, builtin_rule_names=builtin_names
        )

        # Chief of Staff learning.
        self._outcome_store: MemoryBackendOutcomeStore | None = None
        self._confidence_adjuster: ConfidenceAdjuster | None = None
        if config.chief_of_staff.learning_enabled:
            if memory_backend is None:
                logger.warning(
                    COS_OUTCOME_RECORD_FAILED,
                    reason="learning_enabled_but_no_memory_backend",
                )
            else:
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

    async def validate_prerequisites(self) -> None:
        """Validate startup prerequisites.

        Verifies the GitHub token when code modification is enabled
        by pinging the GitHub API.

        Raises:
            GitHubAuthError: If the GitHub token is invalid.
            GitHubAPIError: On other GitHub API failures.
        """
        if not self._config.code_modification_enabled:
            return
        from synthorg.meta.appliers.code_applier import (  # noqa: PLC0415
            CodeApplier,
        )

        applier = self._appliers.get(ProposalAltitude.CODE_MODIFICATION)
        if applier is None or not isinstance(applier, CodeApplier):
            return
        from synthorg.meta.appliers.github_client import (  # noqa: PLC0415
            GitHubAPIError,
        )

        try:
            await applier.verify_github_token()
        except GitHubAPIError:
            logger.exception(
                META_CODE_GITHUB_CREDS_INVALID,
                reason="token_verification_failed",
            )
            raise
        logger.info(META_CODE_GITHUB_CREDS_VALID)

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
        # Uses return_exceptions=True so a single failed adjustment
        # does not discard results from successful adjustments.
        if self._confidence_adjuster is not None and self._outcome_store is not None:
            results = await asyncio.gather(
                *(
                    self._confidence_adjuster.adjust(
                        p,
                        self._outcome_store,
                    )
                    for p in all_proposals
                ),
                return_exceptions=True,
            )
            adjusted: list[ImprovementProposal] = []
            for original, adj_result in zip(
                all_proposals,
                results,
                strict=True,
            ):
                if isinstance(adj_result, BaseException):
                    logger.warning(
                        COS_CONFIDENCE_ADJUSTMENT_FAILED,
                        proposal_id=str(original.id),
                    )
                    adjusted.append(original)
                else:
                    adjusted.append(adj_result)
            all_proposals = adjusted

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

    def _build_regression_thresholds(self) -> RegressionThresholds:
        """Build RegressionThresholds from the service config."""
        rc = self._config.regression
        return RegressionThresholds(
            quality_drop=rc.quality_drop_threshold,
            cost_increase=rc.cost_increase_threshold,
            error_rate_increase=rc.error_rate_increase_threshold,
            success_rate_drop=rc.success_rate_drop_threshold,
        )

    async def execute_rollout(
        self,
        proposal: ImprovementProposal,
        *,
        baseline: OrgSignalSnapshot | None = None,
        current: OrgSignalSnapshot | None = None,
    ) -> RolloutResult:
        """Execute a rollout for an approved proposal.

        If ``baseline`` and ``current`` snapshots are provided, the
        tiered regression detector is invoked after the rollout
        completes.  On regression, the result is updated with the
        detection verdict.

        Args:
            proposal: The human-approved proposal.
            baseline: Signal snapshot taken before the rollout.
            current: Signal snapshot taken after the observation
                window completes.

        Returns:
            Rollout result (may include regression verdict).
        """
        applier, rollout = self._validate_rollout_preconditions(proposal)
        result = await rollout.execute(
            proposal=proposal,
            applier=applier,
            detector=self._detector,
        )
        result = await self._post_rollout_regression_check(
            result,
            proposal,
            baseline=baseline,
            current=current,
        )
        if self._analytics_emitter is not None:
            await self._analytics_emitter.emit_rollout(
                result,
                proposal=proposal,
            )
        return result

    def _validate_rollout_preconditions(
        self,
        proposal: ImprovementProposal,
    ) -> tuple[ProposalApplier, RolloutStrategy]:
        """Validate proposal status, applier, and strategy exist."""
        if proposal.status is not ProposalStatus.APPROVED:
            logger.error(
                META_ROLLOUT_PRECONDITION_FAILED,
                proposal_id=str(proposal.id),
                reason="not_approved",
                status=proposal.status.value,
            )
            msg = (
                f"Proposal {proposal.id} must be approved before "
                f"rollout; current status is {proposal.status.value}"
            )
            raise ValueError(msg)
        applier = self._appliers.get(proposal.altitude)
        if applier is None:
            logger.error(
                META_ROLLOUT_PRECONDITION_FAILED,
                proposal_id=str(proposal.id),
                reason="no_applier",
                altitude=proposal.altitude.value,
            )
            msg = f"No applier for altitude {proposal.altitude}"
            raise ValueError(msg)
        strategy_name = proposal.rollout_strategy.value
        rollout = self._rollout_strategies.get(strategy_name)
        if rollout is None:
            logger.error(
                META_ROLLOUT_PRECONDITION_FAILED,
                proposal_id=str(proposal.id),
                reason="no_strategy",
                strategy=strategy_name,
            )
            msg = f"No rollout strategy '{strategy_name}'"
            raise ValueError(msg)
        return applier, rollout

    async def _post_rollout_regression_check(
        self,
        result: RolloutResult,
        proposal: ImprovementProposal,
        *,
        baseline: OrgSignalSnapshot | None,
        current: OrgSignalSnapshot | None,
    ) -> RolloutResult:
        """Run tiered regression detection after a successful rollout."""
        if (
            baseline is None
            or current is None
            or result.outcome != RolloutOutcome.SUCCESS
        ):
            return result
        thresholds = self._build_regression_thresholds()
        regression = await self._detector.check(
            baseline=baseline,
            current=current,
            thresholds=thresholds,
        )
        if regression.verdict == RegressionVerdict.NO_REGRESSION:
            return result
        logger.warning(
            META_ROLLOUT_REGRESSION_DETECTED,
            proposal_id=str(proposal.id),
            verdict=regression.verdict.value,
            breached_metric=regression.breached_metric,
        )
        return result.model_copy(
            update={
                "outcome": RolloutOutcome.REGRESSED,
                "regression_verdict": regression.verdict,
                "details": (
                    f"Regression detected: {regression.verdict.value}"
                    f" on {regression.breached_metric or 'unknown'}"
                ),
            },
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
        """Record a decided proposal for learning and analytics.

        Called by the approval API after a human approves or
        rejects a proposal. Emits analytics telemetry independently
        of Chief of Staff learning (outcome_store).

        Args:
            proposal: The decided proposal.
        """
        if proposal.decided_at is None or proposal.decided_by is None:
            logger.info(
                COS_OUTCOME_SKIPPED,
                proposal_id=str(proposal.id),
                reason="missing_decision_context",
            )
            return
        if proposal.status not in (
            ProposalStatus.APPROVED,
            ProposalStatus.REJECTED,
        ):
            logger.info(
                COS_OUTCOME_SKIPPED,
                proposal_id=str(proposal.id),
                reason="non_terminal_status",
                status=proposal.status.value,
            )
            return
        decision: Literal["approved", "rejected"] = (
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

        # Record outcome for Chief of Staff learning (if enabled).
        if self._outcome_store is not None:
            try:
                await self._outcome_store.record_outcome(outcome)
            except Exception:
                logger.exception(
                    COS_OUTCOME_RECORD_FAILED,
                    proposal_id=str(proposal.id),
                )

        # Emit anonymized event for cross-deployment analytics.
        # emit_decision handles its own exceptions internally.
        if self._analytics_emitter is not None:
            await self._analytics_emitter.emit_decision(
                outcome,
                proposal=proposal,
            )

    async def close(self) -> None:
        """Flush analytics emitter, close appliers, and release resources."""
        for applier in self._appliers.values():
            close = getattr(applier, "aclose", None)
            if close is not None:
                try:
                    await close()
                except Exception:
                    logger.exception(
                        META_SERVICE_CLOSE_FAILED,
                        reason="applier_close_failed",
                        altitude=str(applier.altitude),
                    )
        if self._analytics_emitter is not None:
            try:
                await self._analytics_emitter.close()
            except Exception:
                logger.exception(
                    XDEPLOY_EVENT_EMIT_FAILED,
                    reason="emitter_close_failed",
                )
