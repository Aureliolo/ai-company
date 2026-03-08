"""Round-robin meeting protocol (DESIGN_SPEC Section 5.7).

Participants take sequential turns with full transcript context.
Each agent sees the entire conversation history when contributing,
producing rich contextual dialogue at the cost of quadratic token
growth.
"""

import dataclasses
from datetime import UTC, datetime

from ai_company.communication.meeting.config import RoundRobinConfig  # noqa: TC001
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
    MEETING_BUDGET_EXHAUSTED,
    MEETING_CONTRIBUTION_RECORDED,
    MEETING_PHASE_COMPLETED,
    MEETING_PHASE_STARTED,
    MEETING_SUMMARY_GENERATED,
    MEETING_TOKENS_RECORDED,
)

logger = get_logger(__name__)

# Reserve 20% of budget for the summary phase.
_SUMMARY_RESERVE_FRACTION = 0.20


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


def _build_turn_prompt(
    agenda_text: str,
    transcript: list[str],
    agent_id: str,
) -> str:
    """Build a turn prompt with agenda, transcript, and instruction."""
    parts = [agenda_text, ""]
    if transcript:
        parts.append("Transcript so far:")
        parts.extend(transcript)
        parts.append("")
    parts.append(
        f"It is your turn, {agent_id}. Share your thoughts on the agenda items."
    )
    return "\n".join(parts)


def _build_summary_prompt(
    agenda_text: str,
    transcript: list[str],
) -> str:
    """Build a summary prompt for the leader."""
    parts = [agenda_text, "", "Full transcript:"]
    parts.extend(transcript)
    parts.append("")
    parts.append(
        "Please summarize this meeting. List the key decisions made "
        "and any action items with assignees. Format decisions as a "
        "numbered list and action items as a bulleted list."
    )
    return "\n".join(parts)


class RoundRobinProtocol:
    """Round-robin meeting protocol implementation.

    Participants speak in order, each seeing the full transcript.
    The leader optionally produces a final summary.

    Args:
        config: Round-robin protocol configuration.
    """

    __slots__ = ("_config",)

    def __init__(self, config: RoundRobinConfig) -> None:
        self._config = config

    def get_protocol_type(self) -> MeetingProtocolType:
        """Return the protocol type."""
        return MeetingProtocolType.ROUND_ROBIN

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
        """Execute the round-robin meeting protocol.

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
        transcript: list[str] = []
        agenda_text = _build_agenda_prompt(agenda)
        turn_number = 0
        budget_exhausted = False

        summary_reserve = int(token_budget * _SUMMARY_RESERVE_FRACTION)
        discussion_budget = token_budget - summary_reserve

        logger.info(
            MEETING_PHASE_STARTED,
            meeting_id=meeting_id,
            phase=MeetingPhase.ROUND_ROBIN_TURN,
            participant_count=len(participant_ids),
        )

        for _round_idx in range(self._config.max_turns_per_agent):
            if budget_exhausted:
                break
            for participant_id in participant_ids:
                if turn_number >= self._config.max_total_turns:
                    break
                if tracker.used >= discussion_budget:
                    budget_exhausted = True
                    logger.warning(
                        MEETING_BUDGET_EXHAUSTED,
                        meeting_id=meeting_id,
                        tokens_used=tracker.used,
                        token_budget=token_budget,
                    )
                    break

                prompt = _build_turn_prompt(
                    agenda_text,
                    transcript,
                    participant_id,
                )
                tokens_available = min(
                    discussion_budget - tracker.used,
                    tracker.remaining,
                )

                logger.debug(
                    MEETING_AGENT_CALLED,
                    meeting_id=meeting_id,
                    agent_id=participant_id,
                    turn_number=turn_number,
                )

                response = await agent_caller(
                    participant_id,
                    prompt,
                    tokens_available,
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
                    phase=MeetingPhase.ROUND_ROBIN_TURN,
                    turn_number=turn_number,
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                    timestamp=now,
                )
                contributions.append(contribution)
                transcript.append(f"[{participant_id}]: {response.content}")

                logger.debug(
                    MEETING_CONTRIBUTION_RECORDED,
                    meeting_id=meeting_id,
                    agent_id=participant_id,
                    turn_number=turn_number,
                )

                turn_number += 1

            if turn_number >= self._config.max_total_turns:
                break

        logger.info(
            MEETING_PHASE_COMPLETED,
            meeting_id=meeting_id,
            phase=MeetingPhase.ROUND_ROBIN_TURN,
            total_turns=turn_number,
        )

        # Summary phase
        summary = ""
        if self._config.leader_summarizes and not tracker.is_exhausted:
            logger.info(
                MEETING_PHASE_STARTED,
                meeting_id=meeting_id,
                phase=MeetingPhase.SUMMARY,
            )

            summary_prompt = _build_summary_prompt(agenda_text, transcript)
            summary_response = await agent_caller(
                leader_id,
                summary_prompt,
                tracker.remaining,
            )
            tracker.record(
                summary_response.input_tokens,
                summary_response.output_tokens,
            )
            summary = summary_response.content

            summary_contribution = MeetingContribution(
                agent_id=leader_id,
                content=summary,
                phase=MeetingPhase.SUMMARY,
                turn_number=turn_number,
                input_tokens=summary_response.input_tokens,
                output_tokens=summary_response.output_tokens,
                timestamp=datetime.now(UTC),
            )
            contributions.append(summary_contribution)

            logger.info(
                MEETING_SUMMARY_GENERATED,
                meeting_id=meeting_id,
                leader_id=leader_id,
            )
            logger.info(
                MEETING_PHASE_COMPLETED,
                meeting_id=meeting_id,
                phase=MeetingPhase.SUMMARY,
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
            protocol_type=MeetingProtocolType.ROUND_ROBIN,
            leader_id=leader_id,
            participant_ids=participant_ids,
            agenda=agenda,
            contributions=tuple(contributions),
            summary=summary,
            total_input_tokens=tracker.input_tokens,
            total_output_tokens=tracker.output_tokens,
            started_at=started_at,
            ended_at=ended_at,
        )
