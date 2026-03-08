"""Meeting orchestrator — lifecycle manager (DESIGN_SPEC Section 5.7).

Manages the full meeting lifecycle: validates inputs, selects the
configured protocol, executes the meeting, optionally creates tasks
from action items, and records audit trail entries.
"""

from collections.abc import Mapping  # noqa: TC003
from uuid import uuid4

from ai_company.communication.meeting.config import MeetingProtocolConfig  # noqa: TC001
from ai_company.communication.meeting.enums import (
    MeetingProtocolType,
    MeetingStatus,
)
from ai_company.communication.meeting.errors import (
    MeetingBudgetExhaustedError,
    MeetingError,
    MeetingParticipantError,
    MeetingProtocolNotFoundError,
)
from ai_company.communication.meeting.models import (
    MeetingAgenda,
    MeetingRecord,
)
from ai_company.communication.meeting.protocol import (  # noqa: TC001
    AgentCaller,
    MeetingProtocol,
    TaskCreator,
)
from ai_company.observability import get_logger
from ai_company.observability.events.meeting import (
    MEETING_ACTION_ITEM_EXTRACTED,
    MEETING_COMPLETED,
    MEETING_FAILED,
    MEETING_STARTED,
    MEETING_TASK_CREATED,
)

logger = get_logger(__name__)


class MeetingOrchestrator:
    """Lifecycle manager for meeting execution.

    Coordinates protocol selection, execution, task creation from
    action items, and audit trail recording.  Meeting records are
    stored in memory (persistence is M5 scope).

    Args:
        protocol_registry: Mapping of protocol types to implementations.
        agent_caller: Callback to invoke agents during meetings.
        task_creator: Optional callback to create tasks from action items.
    """

    __slots__ = (
        "_agent_caller",
        "_protocol_registry",
        "_records",
        "_task_creator",
    )

    def __init__(
        self,
        *,
        protocol_registry: Mapping[MeetingProtocolType, MeetingProtocol],
        agent_caller: AgentCaller,
        task_creator: TaskCreator | None = None,
    ) -> None:
        self._protocol_registry = protocol_registry
        self._agent_caller = agent_caller
        self._task_creator = task_creator
        self._records: list[MeetingRecord] = []

    async def run_meeting(  # noqa: PLR0913
        self,
        *,
        meeting_type_name: str,
        protocol_config: MeetingProtocolConfig,
        agenda: MeetingAgenda,
        leader_id: str,
        participant_ids: tuple[str, ...],
        token_budget: int,
    ) -> MeetingRecord:
        """Execute a meeting and return the audit record.

        Args:
            meeting_type_name: Name of the meeting type from config.
            protocol_config: Protocol configuration to use.
            agenda: The meeting agenda.
            leader_id: ID of the agent leading the meeting.
            participant_ids: IDs of participating agents.
            token_budget: Maximum tokens for the meeting.

        Returns:
            Meeting record with status and optional minutes.

        Raises:
            MeetingProtocolNotFoundError: If the configured protocol
                is not in the registry.
            MeetingParticipantError: If participant list is empty.
        """
        meeting_id = f"mtg-{uuid4().hex[:12]}"
        protocol_type = protocol_config.protocol

        # Validate
        self._validate_participants(
            meeting_id,
            leader_id,
            participant_ids,
        )

        protocol = self._resolve_protocol(meeting_id, protocol_type)

        logger.info(
            MEETING_STARTED,
            meeting_id=meeting_id,
            meeting_type=meeting_type_name,
            protocol=protocol_type,
            leader_id=leader_id,
            participant_count=len(participant_ids),
            token_budget=token_budget,
        )

        try:
            minutes = await protocol.run(
                meeting_id=meeting_id,
                agenda=agenda,
                leader_id=leader_id,
                participant_ids=participant_ids,
                agent_caller=self._agent_caller,
                token_budget=token_budget,
            )
        except MeetingBudgetExhaustedError as exc:
            record = MeetingRecord(
                meeting_id=meeting_id,
                meeting_type_name=meeting_type_name,
                protocol_type=protocol_type,
                status=MeetingStatus.BUDGET_EXHAUSTED,
                error_message=str(exc),
                token_budget=token_budget,
            )
            self._records.append(record)
            logger.warning(
                MEETING_FAILED,
                meeting_id=meeting_id,
                status=MeetingStatus.BUDGET_EXHAUSTED,
                error=str(exc),
            )
            return record
        except (MeetingError, Exception) as exc:
            record = MeetingRecord(
                meeting_id=meeting_id,
                meeting_type_name=meeting_type_name,
                protocol_type=protocol_type,
                status=MeetingStatus.FAILED,
                error_message=str(exc),
                token_budget=token_budget,
            )
            self._records.append(record)
            logger.exception(
                MEETING_FAILED,
                meeting_id=meeting_id,
                status=MeetingStatus.FAILED,
                error=str(exc),
            )
            return record

        # Create tasks from action items if configured
        if (
            self._task_creator is not None
            and protocol_config.structured_phases.auto_create_tasks
            and minutes.action_items
        ):
            logger.info(
                MEETING_ACTION_ITEM_EXTRACTED,
                meeting_id=meeting_id,
                action_item_count=len(minutes.action_items),
            )
            for action_item in minutes.action_items:
                self._task_creator(
                    action_item.description,
                    action_item.assignee_id,
                    action_item.priority,
                )
                logger.debug(
                    MEETING_TASK_CREATED,
                    meeting_id=meeting_id,
                    description=action_item.description,
                    assignee=action_item.assignee_id,
                )

        record = MeetingRecord(
            meeting_id=meeting_id,
            meeting_type_name=meeting_type_name,
            protocol_type=protocol_type,
            status=MeetingStatus.COMPLETED,
            minutes=minutes,
            token_budget=token_budget,
        )
        self._records.append(record)

        logger.info(
            MEETING_COMPLETED,
            meeting_id=meeting_id,
            total_tokens=minutes.total_tokens,
            contributions=len(minutes.contributions),
        )

        return record

    def get_records(self) -> tuple[MeetingRecord, ...]:
        """Return all meeting audit records.

        Returns:
            Tuple of meeting records in chronological order.
        """
        return tuple(self._records)

    def _validate_participants(
        self,
        meeting_id: str,
        leader_id: str,
        participant_ids: tuple[str, ...],
    ) -> None:
        """Validate participant configuration.

        Raises:
            MeetingParticipantError: If participants are empty or leader
                is in participants.
        """
        if not participant_ids:
            msg = "At least one participant is required"
            raise MeetingParticipantError(
                msg,
                context={"meeting_id": meeting_id},
            )
        if leader_id in participant_ids:
            msg = (
                f"Leader {leader_id!r} must not be in participant_ids "
                f"(leader participates implicitly)"
            )
            raise MeetingParticipantError(
                msg,
                context={
                    "meeting_id": meeting_id,
                    "leader_id": leader_id,
                },
            )

    def _resolve_protocol(
        self,
        meeting_id: str,
        protocol_type: MeetingProtocolType,
    ) -> MeetingProtocol:
        """Look up the protocol implementation.

        Raises:
            MeetingProtocolNotFoundError: If not registered.
        """
        protocol = self._protocol_registry.get(protocol_type)
        if protocol is None:
            msg = f"Protocol {protocol_type!r} is not registered"
            raise MeetingProtocolNotFoundError(
                msg,
                context={
                    "meeting_id": meeting_id,
                    "protocol_type": protocol_type,
                },
            )
        return protocol
