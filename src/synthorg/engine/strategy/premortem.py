"""Premortem analysis for strategic decision-making.

Implements "premortem" analysis where participants imagine a decision has
failed and work backward to identify likely failure modes, risks, and
hidden assumptions. This helps surface weaknesses in a proposal before
execution.
"""

import asyncio
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from synthorg.communication.meeting.models import AgentResponse  # noqa: TC001
from synthorg.communication.meeting.protocol import AgentCaller  # noqa: TC001
from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.engine.strategy.models import (
    PremortemConfig,
    PremortemParticipation,
    RiskCard,
)
from synthorg.observability import get_logger

logger = get_logger(__name__)

_MIN_RESPONSE_LENGTH: int = 50


class FailureMode(BaseModel):
    """A potential failure mode identified during premortem.

    Attributes:
        description: Description of how the decision could fail.
        likelihood: Likelihood of this failure mode (low/medium/high).
        impact: Impact severity if this failure occurs (low/medium/high).
        mitigation: Proposed mitigation or preventive action.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    description: NotBlankStr = Field(
        description="Description of how the decision could fail"
    )
    likelihood: Literal["low", "medium", "high"] = Field(
        default="medium",
        description="Likelihood of this failure mode",
    )
    impact: Literal["low", "medium", "high"] = Field(
        default="medium",
        description="Impact severity if this failure occurs",
    )
    mitigation: NotBlankStr = Field(
        default="No mitigation identified",
        description="Proposed mitigation or preventive action",
    )


class PremortermOutput(BaseModel):
    """Aggregated output from premortem analysis.

    Attributes:
        failure_modes: Potential failure modes identified.
        assumptions: Key assumptions underlying the decision.
        risk_card: Optional risk assessment metadata.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    failure_modes: tuple[FailureMode, ...] = Field(
        default=(),
        description="Potential failure modes identified",
    )
    assumptions: tuple[str, ...] = Field(
        default=(),
        description="Key assumptions underlying the decision",
    )
    risk_card: RiskCard | None = Field(
        default=None,
        description="Risk assessment metadata (optional)",
    )


@runtime_checkable
class PremortermExecutor(Protocol):
    """Execute premortem analysis on meeting synthesis.

    Implementations conduct a premortem activity where participants
    imagine a decision has failed and work backward to identify risks,
    failure modes, and hidden assumptions.
    """

    async def execute(
        self,
        *,
        synthesis_text: str,
        participant_ids: tuple[NotBlankStr, ...],
        agent_caller: AgentCaller,
        config: PremortemConfig,
        token_budget: int,
    ) -> PremortermOutput:
        """Conduct premortem analysis.

        Args:
            synthesis_text: Summary of the decision/proposal to analyze.
            participant_ids: IDs of agents participating in premortem.
            agent_caller: Callback to invoke agents.
            config: Premortem configuration.
            token_budget: Maximum tokens for all premortem calls.

        Returns:
            Aggregated premortem analysis output.
        """
        ...


class DefaultPremortermExecutor:
    """Default premortem executor with configurable participant selection.

    Conducts parallel premortem by invoking selected participants with
    a structured prompt asking them to imagine the decision failed and
    identify failure modes, risks, and assumptions. Aggregates results
    into a unified output.
    """

    async def execute(
        self,
        *,
        synthesis_text: str,
        participant_ids: tuple[NotBlankStr, ...],
        agent_caller: AgentCaller,
        config: PremortemConfig,
        token_budget: int,
    ) -> PremortermOutput:
        """Conduct premortem analysis.

        Args:
            synthesis_text: Summary of the decision/proposal to analyze.
            participant_ids: IDs of agents participating in premortem.
            agent_caller: Callback to invoke agents.
            config: Premortem configuration.
            token_budget: Maximum tokens for all premortem calls.

        Returns:
            Aggregated premortem analysis output.
        """
        # Handle NONE configuration
        if config.participants == PremortemParticipation.NONE:
            return PremortermOutput()

        # Select participants based on configuration
        selected_participants = participant_ids
        if config.participants == PremortemParticipation.STRATEGIC:
            # In production, this would filter by agent seniority/role.
            # For now, take approximately the first half.
            half = max(1, len(participant_ids) // 2)
            selected_participants = participant_ids[:half]

        # Return empty if no participants selected
        if not selected_participants:
            return PremortermOutput()

        # Build premortem prompt
        prompt = (
            f"The following decision has been made:\n\n{synthesis_text}\n\n"
            "Imagine this decision was implemented and failed spectacularly. "
            "Working backward from the failure, identify:\n"
            "1. How did it fail? (describe the failure mode)\n"
            "2. What is the likelihood? (low/medium/high)\n"
            "3. What would be the impact? (low/medium/high)\n"
            "4. How could it have been prevented? (mitigation)\n\n"
            "Also identify key assumptions underlying this decision that "
            "could be wrong. Be specific and concrete."
        )

        # Distribute tokens evenly across participants
        tokens_per_agent = max(1, token_budget // len(selected_participants))

        # Pre-allocate result slots for deterministic ordering
        result_slots: list[AgentResponse | None] = [None] * len(
            selected_participants,
        )

        async def _call_and_store(idx: int, pid: NotBlankStr) -> None:
            result_slots[idx] = await agent_caller(pid, prompt, tokens_per_agent)

        async with asyncio.TaskGroup() as tg:
            for idx, pid in enumerate(selected_participants):
                tg.create_task(_call_and_store(idx, pid))

        responses: list[AgentResponse] = [r for r in result_slots if r is not None]

        # Parse and aggregate failure modes and assumptions
        all_failure_modes: list[FailureMode] = []
        all_assumptions: list[str] = []

        for response in responses:
            content = response.content
            # Simple heuristic parsing: extract first relevant section
            if len(content) > _MIN_RESPONSE_LENGTH:
                # If response contains failure discussion, create a mode entry
                if any(
                    word in content.lower()
                    for word in ["fail", "risk", "problem", "wrong"]
                ):
                    # Take first ~200 chars as failure description
                    desc = content[:200].strip()
                    all_failure_modes.append(
                        FailureMode(
                            description=desc,
                            mitigation="See full premortem response",
                        )
                    )

                # If response mentions assumptions, extract them
                if "assumption" in content.lower():
                    # Take first ~150 chars as assumption
                    assumption = content[:150].strip()
                    all_assumptions.append(assumption)

        return PremortermOutput(
            failure_modes=tuple(all_failure_modes),
            assumptions=tuple(all_assumptions),
        )
