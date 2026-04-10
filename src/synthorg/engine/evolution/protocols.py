"""Protocols for the agent evolution system.

Defines the four pluggable strategy interfaces (trigger, proposer,
guard, adapter) and the context model passed through the pipeline.
"""

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.engine.evolution.models import (
    AdaptationAxis,  # noqa: TC001
    AdaptationDecision,  # noqa: TC001
    AdaptationProposal,  # noqa: TC001
)

if TYPE_CHECKING:
    from synthorg.core.agent import AgentIdentity
    from synthorg.hr.performance.models import (
        AgentPerformanceSnapshot,
        TaskMetricRecord,
    )
    from synthorg.memory.models import MemoryEntry


class EvolutionContext(BaseModel):
    """Context bag passed through the evolution pipeline.

    Assembled by ``EvolutionService`` before invoking proposers.
    Contains the agent's current identity, performance snapshot,
    recent task results, and relevant procedural memories.

    Attributes:
        agent_id: Target agent identifier.
        identity: Current agent identity snapshot.
        performance_snapshot: Latest performance snapshot (or None
            if insufficient data).
        recent_task_results: Recent task metric records.
        recent_procedural_memories: Relevant procedural memory entries.
        triggered_at: When the evolution was triggered.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    agent_id: NotBlankStr
    identity: AgentIdentity
    performance_snapshot: AgentPerformanceSnapshot | None = None
    recent_task_results: tuple[TaskMetricRecord, ...] = ()
    recent_procedural_memories: tuple[MemoryEntry, ...] = ()
    triggered_at: AwareDatetime = Field(
        default_factory=lambda: __import__("datetime").datetime.now(
            __import__("datetime").UTC,
        ),
    )


@runtime_checkable
class EvolutionTrigger(Protocol):
    """Determines when evolution should run for an agent.

    Implementations include per-task triggers, inflection-based
    triggers, batched/scheduled triggers, and composites.
    """

    @property
    def name(self) -> str:
        """Human-readable trigger name."""
        ...

    async def should_trigger(
        self,
        *,
        agent_id: NotBlankStr,
        context: EvolutionContext,
    ) -> bool:
        """Decide whether evolution should proceed.

        Args:
            agent_id: Agent to evaluate.
            context: Current evolution context.

        Returns:
            True if evolution should run for this agent.
        """
        ...


@runtime_checkable
class AdaptationProposer(Protocol):
    """Generates adaptation proposals from evolution context.

    Implementations include separate-analyzer (EvoSkill strict),
    self-report (lighter, success-path), and composite routing.
    """

    @property
    def name(self) -> str:
        """Human-readable proposer name."""
        ...

    async def propose(
        self,
        *,
        agent_id: NotBlankStr,
        context: EvolutionContext,
    ) -> tuple[AdaptationProposal, ...]:
        """Generate zero or more adaptation proposals.

        Args:
            agent_id: Agent to generate proposals for.
            context: Evolution context with identity, performance,
                and memory data.

        Returns:
            Tuple of proposals (empty if no adaptations suggested).
        """
        ...


@runtime_checkable
class AdaptationGuard(Protocol):
    """Validates an adaptation proposal before it is applied.

    Implementations include rate limiting, review gates,
    rollback monitoring, shadow evaluation, and composites.
    """

    @property
    def name(self) -> str:
        """Human-readable guard name."""
        ...

    async def evaluate(
        self,
        proposal: AdaptationProposal,
    ) -> AdaptationDecision:
        """Evaluate whether a proposal should be applied.

        Args:
            proposal: The adaptation proposal to evaluate.

        Returns:
            Decision with approval/rejection and rationale.
        """
        ...


@runtime_checkable
class AdaptationAdapter(Protocol):
    """Applies an approved adaptation proposal.

    Implementations include identity mutation, strategy selection
    updates, and prompt template injection.
    """

    @property
    def name(self) -> str:
        """Human-readable adapter name."""
        ...

    @property
    def axis(self) -> AdaptationAxis:
        """Which adaptation axis this adapter handles."""
        ...

    async def apply(
        self,
        proposal: AdaptationProposal,
        agent_id: NotBlankStr,
    ) -> None:
        """Apply the approved adaptation.

        Args:
            proposal: The approved proposal to apply.
            agent_id: Target agent.

        Raises:
            AdaptationError: If the adaptation cannot be applied.
        """
        ...


# Rebuild EvolutionContext model with forward references resolved at runtime.
from synthorg.core.agent import AgentIdentity  # noqa: E402
from synthorg.hr.performance.models import (  # noqa: E402
    AgentPerformanceSnapshot,
    TaskMetricRecord,
)
from synthorg.memory.models import MemoryEntry  # noqa: E402

EvolutionContext.model_rebuild()
