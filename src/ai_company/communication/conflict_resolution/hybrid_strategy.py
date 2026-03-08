"""Hybrid conflict resolution strategy (DESIGN_SPEC §5.6).

Strategy 4: Combines automated review with optional human escalation.
If a ``JudgeEvaluator`` is provided and returns a clear winner,
auto-resolves.  On ambiguity (or no evaluator), falls back to
authority or human escalation based on configuration.
"""

from datetime import UTC, datetime
from uuid import uuid4

from ai_company.communication.conflict_resolution._helpers import (
    find_loser,
    find_position,
    pick_highest_seniority,
)
from ai_company.communication.conflict_resolution.config import (  # noqa: TC001
    HybridConfig,
)
from ai_company.communication.conflict_resolution.models import (
    Conflict,
    ConflictResolution,
    ConflictResolutionOutcome,
    DissentRecord,
)
from ai_company.communication.conflict_resolution.protocol import (  # noqa: TC001
    ConflictResolver,
    JudgeEvaluator,
)
from ai_company.communication.delegation.hierarchy import (  # noqa: TC001
    HierarchyResolver,
)
from ai_company.communication.enums import ConflictResolutionStrategy
from ai_company.observability import get_logger
from ai_company.observability.events.conflict import (
    CONFLICT_AMBIGUOUS_RESULT,
    CONFLICT_AUTHORITY_FALLBACK,
    CONFLICT_HYBRID_AUTO_RESOLVED,
    CONFLICT_HYBRID_REVIEW,
)

logger = get_logger(__name__)


class HybridResolver:
    """Resolve conflicts via hybrid automated review + escalation.

    When a ``JudgeEvaluator`` (``review_evaluator``) is provided,
    it evaluates the positions.  If the result matches a conflict
    participant, auto-resolves.  Otherwise:

    - ``escalate_on_ambiguity=True`` → delegate to human resolver
    - ``escalate_on_ambiguity=False`` → fall back to authority

    When no evaluator is provided, falls back to authority.

    Args:
        hierarchy: Resolved organizational hierarchy.
        config: Hybrid strategy configuration.
        human_resolver: Human escalation resolver for ambiguous cases.
        review_evaluator: Optional LLM-based reviewer.
    """

    __slots__ = (
        "_config",
        "_hierarchy",
        "_human_resolver",
        "_review_evaluator",
    )

    def __init__(
        self,
        *,
        hierarchy: HierarchyResolver,
        config: HybridConfig,
        human_resolver: ConflictResolver,
        review_evaluator: JudgeEvaluator | None = None,
    ) -> None:
        self._hierarchy = hierarchy
        self._config = config
        self._human_resolver = human_resolver
        self._review_evaluator = review_evaluator

    async def resolve(self, conflict: Conflict) -> ConflictResolution:
        """Resolve via hybrid review — auto-resolve or escalate.

        Args:
            conflict: The conflict to resolve.

        Returns:
            Resolution decision.
        """
        logger.info(
            CONFLICT_HYBRID_REVIEW,
            conflict_id=conflict.id,
            has_evaluator=self._review_evaluator is not None,
        )

        if self._review_evaluator is None:
            logger.warning(
                CONFLICT_AUTHORITY_FALLBACK,
                conflict_id=conflict.id,
                strategy="hybrid",
                reason="no_review_evaluator",
            )
            return self._authority_fallback(conflict)

        winning_agent_id, reasoning = await self._review_evaluator.evaluate(
            conflict,
            self._config.review_agent,
        )

        # Check if the winner is an actual participant
        winner_pos = find_position(conflict, winning_agent_id)
        if winner_pos is not None:
            logger.info(
                CONFLICT_HYBRID_AUTO_RESOLVED,
                conflict_id=conflict.id,
                winner=winning_agent_id,
            )
            return ConflictResolution(
                conflict_id=conflict.id,
                outcome=ConflictResolutionOutcome.RESOLVED_BY_HYBRID,
                winning_agent_id=winning_agent_id,
                winning_position=winner_pos.position,
                decided_by=self._config.review_agent,
                reasoning=reasoning,
                resolved_at=datetime.now(UTC),
            )

        # Ambiguous result — winner not found in positions
        logger.warning(
            CONFLICT_AMBIGUOUS_RESULT,
            conflict_id=conflict.id,
            returned_winner=winning_agent_id,
            reasoning=reasoning,
            participants=[p.agent_id for p in conflict.positions],
            escalate=self._config.escalate_on_ambiguity,
        )

        if self._config.escalate_on_ambiguity:
            return await self._human_resolver.resolve(conflict)

        return self._authority_fallback(conflict)

    def build_dissent_record(
        self,
        conflict: Conflict,
        resolution: ConflictResolution,
    ) -> DissentRecord:
        """Build dissent record for the hybrid resolution.

        Args:
            conflict: The original conflict.
            resolution: The resolution decision.

        Returns:
            Dissent record.
        """
        if resolution.outcome == ConflictResolutionOutcome.ESCALATED_TO_HUMAN:
            # Delegate to human resolver's dissent record logic
            first_pos = conflict.positions[0]
            return DissentRecord(
                id=f"dissent-{uuid4().hex[:12]}",
                conflict=conflict,
                resolution=resolution,
                dissenting_agent_id=first_pos.agent_id,
                dissenting_position=first_pos.position,
                strategy_used=ConflictResolutionStrategy.HYBRID,
                timestamp=datetime.now(UTC),
                metadata=(("escalation_reason", "ambiguous_review"),),
            )

        loser = find_loser(conflict, resolution)
        return DissentRecord(
            id=f"dissent-{uuid4().hex[:12]}",
            conflict=conflict,
            resolution=resolution,
            dissenting_agent_id=loser.agent_id,
            dissenting_position=loser.position,
            strategy_used=ConflictResolutionStrategy.HYBRID,
            timestamp=datetime.now(UTC),
        )

    def _authority_fallback(
        self,
        conflict: Conflict,
    ) -> ConflictResolution:
        """Fall back to authority-based resolution.

        Callers are responsible for logging ``CONFLICT_AUTHORITY_FALLBACK``
        with the appropriate reason before calling this method.

        Args:
            conflict: The conflict to resolve.

        Returns:
            Resolution with ``RESOLVED_BY_HYBRID`` outcome.
        """
        best = pick_highest_seniority(conflict)

        return ConflictResolution(
            conflict_id=conflict.id,
            outcome=ConflictResolutionOutcome.RESOLVED_BY_HYBRID,
            winning_agent_id=best.agent_id,
            winning_position=best.position,
            decided_by="authority_fallback",
            reasoning=(
                f"Hybrid fallback: authority-based — "
                f"{best.agent_id} ({best.agent_level}) has highest "
                f"seniority"
            ),
            resolved_at=datetime.now(UTC),
        )
