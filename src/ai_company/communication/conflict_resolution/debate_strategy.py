"""Structured debate + judge conflict resolution strategy (DESIGN_SPEC §5.6).

Strategy 2: A judge evaluates both positions and picks a winner.
If a ``JudgeEvaluator`` is provided, it uses LLM-based judging.
Otherwise, falls back to authority-based resolution (highest
seniority among positions wins).
"""

from datetime import UTC, datetime
from uuid import uuid4

from ai_company.communication.conflict_resolution._helpers import (
    find_loser,
    find_position_or_raise,
    pick_highest_seniority,
)
from ai_company.communication.conflict_resolution.config import (  # noqa: TC001
    DebateConfig,
)
from ai_company.communication.conflict_resolution.models import (
    Conflict,
    ConflictResolution,
    ConflictResolutionOutcome,
    DissentRecord,
)
from ai_company.communication.conflict_resolution.protocol import (  # noqa: TC001
    JudgeEvaluator,
)
from ai_company.communication.delegation.hierarchy import (  # noqa: TC001
    HierarchyResolver,
)
from ai_company.communication.enums import ConflictResolutionStrategy
from ai_company.communication.errors import ConflictHierarchyError
from ai_company.observability import get_logger
from ai_company.observability.events.conflict import (
    CONFLICT_AUTHORITY_FALLBACK,
    CONFLICT_DEBATE_JUDGE_DECIDED,
    CONFLICT_DEBATE_STARTED,
    CONFLICT_HIERARCHY_ERROR,
    CONFLICT_LCM_LOOKUP,
)

logger = get_logger(__name__)


class DebateResolver:
    """Resolve conflicts via structured debate with a judge.

    When a ``JudgeEvaluator`` is provided, the judge evaluates
    both positions using LLM reasoning.  When absent, falls back
    to authority-based resolution (highest seniority wins).

    Args:
        hierarchy: Resolved organizational hierarchy.
        config: Debate strategy configuration.
        judge_evaluator: Optional LLM-based judge (fallback: authority).
    """

    __slots__ = ("_config", "_hierarchy", "_judge_evaluator")

    def __init__(
        self,
        *,
        hierarchy: HierarchyResolver,
        config: DebateConfig,
        judge_evaluator: JudgeEvaluator | None = None,
    ) -> None:
        self._hierarchy = hierarchy
        self._config = config
        self._judge_evaluator = judge_evaluator

    async def resolve(self, conflict: Conflict) -> ConflictResolution:
        """Resolve via debate — judge picks a winner.

        Args:
            conflict: The conflict to resolve.

        Returns:
            Resolution with ``RESOLVED_BY_DEBATE`` outcome.

        Raises:
            ConflictStrategyError: If the judge returns a winning
                agent ID not found in the conflict positions.
            ConflictHierarchyError: If LCM lookup fails when needed.
        """
        judge_id = self._determine_judge(conflict)

        logger.info(
            CONFLICT_DEBATE_STARTED,
            conflict_id=conflict.id,
            judge=judge_id,
        )

        if self._judge_evaluator is not None:
            winning_agent_id, reasoning = await self._judge_evaluator.evaluate(
                conflict,
                judge_id,
            )
        else:
            logger.warning(
                CONFLICT_AUTHORITY_FALLBACK,
                conflict_id=conflict.id,
                strategy="debate",
                reason="no_judge_evaluator",
            )
            winning_agent_id, reasoning = self._authority_fallback(conflict)

        winning_pos = find_position_or_raise(conflict, winning_agent_id)

        logger.info(
            CONFLICT_DEBATE_JUDGE_DECIDED,
            conflict_id=conflict.id,
            judge=judge_id,
            winner=winning_agent_id,
        )

        return ConflictResolution(
            conflict_id=conflict.id,
            outcome=ConflictResolutionOutcome.RESOLVED_BY_DEBATE,
            winning_agent_id=winning_agent_id,
            winning_position=winning_pos.position,
            decided_by=judge_id,
            reasoning=reasoning,
            resolved_at=datetime.now(UTC),
        )

    def build_dissent_record(
        self,
        conflict: Conflict,
        resolution: ConflictResolution,
    ) -> DissentRecord:
        """Build dissent record for the losing debater.

        Args:
            conflict: The original conflict.
            resolution: The resolution decision.

        Returns:
            Dissent record preserving the overruled reasoning.
        """
        loser = find_loser(conflict, resolution)
        return DissentRecord(
            id=f"dissent-{uuid4().hex[:12]}",
            conflict=conflict,
            resolution=resolution,
            dissenting_agent_id=loser.agent_id,
            dissenting_position=loser.position,
            strategy_used=ConflictResolutionStrategy.DEBATE,
            timestamp=datetime.now(UTC),
            metadata=(("judge", resolution.decided_by),),
        )

    def _determine_judge(self, conflict: Conflict) -> str:
        """Determine the judge agent for this conflict.

        For N-party conflicts with ``"shared_manager"``, finds the
        lowest common manager of all participants iteratively.

        Args:
            conflict: The conflict being judged.

        Returns:
            Agent name to act as judge.

        Raises:
            ConflictHierarchyError: If ``"shared_manager"`` is
                configured but no LCM exists.
        """
        if self._config.judge == "shared_manager":
            lcm: str | None = self._hierarchy.get_lowest_common_manager(
                conflict.positions[0].agent_id,
                conflict.positions[1].agent_id,
            )
            for pos in conflict.positions[2:]:
                if lcm is None:
                    break
                lcm = self._hierarchy.get_lowest_common_manager(
                    lcm,
                    pos.agent_id,
                )
            logger.debug(
                CONFLICT_LCM_LOOKUP,
                conflict_id=conflict.id,
                agents=[p.agent_id for p in conflict.positions],
                lcm=lcm,
            )
            if lcm is None:
                msg = (
                    "No shared manager for conflict participants — cannot select judge"
                )
                logger.warning(
                    CONFLICT_HIERARCHY_ERROR,
                    conflict_id=conflict.id,
                    agents=[p.agent_id for p in conflict.positions],
                    error=msg,
                )
                raise ConflictHierarchyError(
                    msg,
                    context={
                        "conflict_id": conflict.id,
                        "agents": [p.agent_id for p in conflict.positions],
                    },
                )
            return lcm

        if self._config.judge == "ceo":
            # Walk from first position to hierarchy root
            ancestors = self._hierarchy.get_ancestors(
                conflict.positions[0].agent_id,
            )
            if ancestors:
                return ancestors[-1]
            # Agent has no ancestors — they are the root
            return conflict.positions[0].agent_id

        # Named agent
        return self._config.judge

    @staticmethod
    def _authority_fallback(
        conflict: Conflict,
    ) -> tuple[str, str]:
        """Fall back to authority when no judge evaluator is available.

        Args:
            conflict: The conflict to resolve.

        Returns:
            Tuple of ``(winning_agent_id, reasoning)``.
        """
        best = pick_highest_seniority(conflict)
        return (
            best.agent_id,
            (
                f"Debate fallback: authority-based judging — "
                f"{best.agent_id} ({best.agent_level}) has highest "
                f"seniority"
            ),
        )
