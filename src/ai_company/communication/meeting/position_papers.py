"""Position-papers meeting protocol (DESIGN_SPEC Section 5.7).

Each participant writes an independent position paper in parallel,
then a synthesizer combines all papers into decisions and action
items.  This is the cheapest protocol — O(n) tokens with no ordering
bias and no quadratic context growth.
"""

import asyncio
import dataclasses
from datetime import UTC, datetime

from ai_company.communication.meeting.config import PositionPapersConfig  # noqa: TC001
from ai_company.communication.meeting.enums import (
    MeetingPhase,
    MeetingProtocolType,
)
from ai_company.communication.meeting.models import (
    MeetingAgenda,
    MeetingContribution,
    MeetingMinutes,
)
from ai_company.communication.meeting.protocol import AgentCaller  # noqa: TC001
from ai_company.observability import get_logger
from ai_company.observability.events.meeting import (
    MEETING_AGENT_CALLED,
    MEETING_AGENT_RESPONDED,
    MEETING_CONTRIBUTION_RECORDED,
    MEETING_PHASE_COMPLETED,
    MEETING_PHASE_STARTED,
    MEETING_SUMMARY_GENERATED,
    MEETING_TOKENS_RECORDED,
)

logger = get_logger(__name__)


@dataclasses.dataclass
class _TokenTracker:
    """Mutable token budget tracker scoped to a single meeting execution."""

    budget: int
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def used(self) -> int:
        """Total tokens consumed so far."""
        return self.input_tokens + self.output_tokens

    @property
    def remaining(self) -> int:
        """Tokens remaining in the budget."""
        return max(0, self.budget - self.used)

    @property
    def is_exhausted(self) -> bool:
        """Whether the budget is fully consumed."""
        return self.remaining == 0

    def record(self, input_tokens: int, output_tokens: int) -> None:
        """Record token usage from an agent call."""
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens


def _build_agenda_prompt(agenda: MeetingAgenda) -> str:
    """Build the initial agenda prompt text."""
    parts = [f"Meeting: {agenda.title}"]
    if agenda.context:
        parts.append(f"Context: {agenda.context}")
    if agenda.items:
        parts.append("Agenda items:")
        for i, item in enumerate(agenda.items, 1):
            entry = f"  {i}. {item.title}"
            if item.description:
                entry += f" — {item.description}"
            parts.append(entry)
    return "\n".join(parts)


def _build_position_prompt(agenda_text: str, agent_id: str) -> str:
    """Build a position paper prompt for an agent."""
    return (
        f"{agenda_text}\n\n"
        f"{agent_id}, please write your position paper on the agenda "
        f"items above. Share your analysis, recommendations, and any "
        f"concerns you have."
    )


def _build_synthesis_prompt(
    agenda_text: str,
    papers: list[tuple[str, str]],
) -> str:
    """Build a synthesis prompt from all position papers."""
    parts = [agenda_text, "", "Position papers submitted:"]
    for agent_id, content in papers:
        parts.append(f"\n--- {agent_id} ---")
        parts.append(content)
    parts.append("")
    parts.append(
        "Please synthesize these position papers. Identify areas of "
        "agreement, conflicts, and produce a list of decisions and "
        "action items with assignees."
    )
    return "\n".join(parts)


class PositionPapersProtocol:
    """Position-papers meeting protocol implementation.

    All participants write position papers in parallel, then a
    synthesizer combines them into decisions and action items.

    Args:
        config: Position papers protocol configuration.
    """

    __slots__ = ("_config",)

    def __init__(self, config: PositionPapersConfig) -> None:
        self._config = config

    def get_protocol_type(self) -> MeetingProtocolType:
        """Return the protocol type."""
        return MeetingProtocolType.POSITION_PAPERS

    async def run(  # noqa: PLR0913
        self,
        *,
        meeting_id: str,
        agenda: MeetingAgenda,
        leader_id: str,
        participant_ids: tuple[str, ...],
        agent_caller: AgentCaller,
        token_budget: int,
    ) -> MeetingMinutes:
        """Execute the position-papers meeting protocol.

        Args:
            meeting_id: Unique meeting identifier.
            agenda: The meeting agenda.
            leader_id: ID of the meeting leader.
            participant_ids: IDs of participating agents.
            agent_caller: Callback to invoke agents.
            token_budget: Maximum tokens for the meeting.

        Returns:
            Complete meeting minutes.
        """
        started_at = datetime.now(UTC)
        tracker = _TokenTracker(budget=token_budget)
        contributions: list[MeetingContribution] = []
        agenda_text = _build_agenda_prompt(agenda)

        # Determine synthesizer agent
        synthesizer_id = (
            leader_id
            if self._config.synthesizer == "meeting_leader"
            else self._config.synthesizer
        )

        # Phase 1: Parallel position papers
        logger.info(
            MEETING_PHASE_STARTED,
            meeting_id=meeting_id,
            phase=MeetingPhase.POSITION_PAPER,
            participant_count=len(participant_ids),
        )

        papers: list[tuple[str, str]] = []
        paper_contributions: list[MeetingContribution] = []

        async def _collect_paper(
            participant_id: str,
            turn: int,
        ) -> None:
            prompt = _build_position_prompt(agenda_text, participant_id)
            max_tokens = min(
                self._config.max_tokens_per_position,
                tracker.remaining,
            )

            logger.debug(
                MEETING_AGENT_CALLED,
                meeting_id=meeting_id,
                agent_id=participant_id,
                phase=MeetingPhase.POSITION_PAPER,
            )

            response = await agent_caller(
                participant_id,
                prompt,
                max_tokens,
            )
            tracker.record(response.input_tokens, response.output_tokens)

            logger.debug(
                MEETING_AGENT_RESPONDED,
                meeting_id=meeting_id,
                agent_id=participant_id,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
            )

            now = datetime.now(UTC)
            contribution = MeetingContribution(
                agent_id=participant_id,
                content=response.content,
                phase=MeetingPhase.POSITION_PAPER,
                turn_number=turn,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                timestamp=now,
            )
            papers.append((participant_id, response.content))
            paper_contributions.append(contribution)

            logger.debug(
                MEETING_CONTRIBUTION_RECORDED,
                meeting_id=meeting_id,
                agent_id=participant_id,
            )

        async with asyncio.TaskGroup() as tg:
            for idx, pid in enumerate(participant_ids):
                tg.create_task(_collect_paper(pid, idx))

        contributions.extend(paper_contributions)

        logger.info(
            MEETING_PHASE_COMPLETED,
            meeting_id=meeting_id,
            phase=MeetingPhase.POSITION_PAPER,
            papers_collected=len(papers),
        )

        # Phase 2: Synthesis
        logger.info(
            MEETING_PHASE_STARTED,
            meeting_id=meeting_id,
            phase=MeetingPhase.SYNTHESIS,
            synthesizer=synthesizer_id,
        )

        synthesis_prompt = _build_synthesis_prompt(agenda_text, papers)
        synthesis_response = await agent_caller(
            synthesizer_id,
            synthesis_prompt,
            tracker.remaining,
        )
        tracker.record(
            synthesis_response.input_tokens,
            synthesis_response.output_tokens,
        )

        turn_number = len(participant_ids)
        synthesis_contribution = MeetingContribution(
            agent_id=synthesizer_id,
            content=synthesis_response.content,
            phase=MeetingPhase.SYNTHESIS,
            turn_number=turn_number,
            input_tokens=synthesis_response.input_tokens,
            output_tokens=synthesis_response.output_tokens,
            timestamp=datetime.now(UTC),
        )
        contributions.append(synthesis_contribution)

        logger.info(
            MEETING_SUMMARY_GENERATED,
            meeting_id=meeting_id,
            leader_id=synthesizer_id,
        )
        logger.info(
            MEETING_PHASE_COMPLETED,
            meeting_id=meeting_id,
            phase=MeetingPhase.SYNTHESIS,
        )

        logger.debug(
            MEETING_TOKENS_RECORDED,
            meeting_id=meeting_id,
            input_tokens=tracker.input_tokens,
            output_tokens=tracker.output_tokens,
            total_tokens=tracker.used,
            budget=token_budget,
        )

        ended_at = datetime.now(UTC)
        return MeetingMinutes(
            meeting_id=meeting_id,
            protocol_type=MeetingProtocolType.POSITION_PAPERS,
            leader_id=leader_id,
            participant_ids=participant_ids,
            agenda=agenda,
            contributions=tuple(contributions),
            summary=synthesis_response.content,
            total_input_tokens=tracker.input_tokens,
            total_output_tokens=tracker.output_tokens,
            started_at=started_at,
            ended_at=ended_at,
        )
