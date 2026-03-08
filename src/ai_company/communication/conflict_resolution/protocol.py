"""Conflict resolution protocol interfaces (DESIGN_SPEC §5.6).

Defines the pluggable strategy interface that varies per resolution
approach (``resolve`` + ``build_dissent_record``).  Detection logic
lives on the service, not the protocol, because it is strategy-agnostic.
"""

from typing import Protocol

from ai_company.communication.conflict_resolution.models import (  # noqa: TC001
    Conflict,
    ConflictResolution,
    DissentRecord,
)
from ai_company.core.types import NotBlankStr  # noqa: TC001


class ConflictResolver(Protocol):
    """Protocol for conflict resolution strategies.

    Each strategy implements ``resolve`` (async, may need LLM calls)
    and ``build_dissent_record`` (sync, builds the audit artifact).
    """

    async def resolve(self, conflict: Conflict) -> ConflictResolution:
        """Resolve a conflict and produce a decision.

        Args:
            conflict: The conflict to resolve.

        Returns:
            Resolution decision.
        """
        ...

    def build_dissent_record(
        self,
        conflict: Conflict,
        resolution: ConflictResolution,
    ) -> DissentRecord:
        """Build an audit record for the losing position.

        Args:
            conflict: The original conflict.
            resolution: The resolution decision.

        Returns:
            Dissent record preserving the overruled reasoning.
        """
        ...


class JudgeEvaluator(Protocol):
    """Protocol for LLM-based judge evaluation.

    Used by debate and hybrid strategies.  When absent, strategies
    fall back to authority-based judging.
    """

    async def evaluate(
        self,
        conflict: Conflict,
        judge_agent_id: NotBlankStr,
    ) -> tuple[str, str]:
        """Evaluate conflict positions and pick a winner.

        Args:
            conflict: The conflict with agent positions.
            judge_agent_id: The agent acting as judge.

        Returns:
            Tuple of ``(winning_agent_id, reasoning)``.
        """
        ...
