"""Sprint configuration models -- ceremony definitions and sprint settings.

Integrates with the meeting protocol system via ``MeetingProtocolType``
and ``MeetingFrequency`` from the communication module.
"""

from collections import Counter
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from synthorg.communication.meeting.enums import MeetingProtocolType
from synthorg.communication.meeting.frequency import MeetingFrequency
from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.observability import get_logger

logger = get_logger(__name__)


class SprintCeremonyConfig(BaseModel):
    """Configuration for a single sprint ceremony.

    Links a ceremony name to a meeting protocol type and recurrence
    frequency from the communication subsystem.

    Attributes:
        name: Ceremony identifier (e.g. ``"sprint_planning"``).
        protocol: Meeting protocol type to use.
        frequency: How often the ceremony occurs.
        duration_tokens: Token budget for the meeting.
        participants: Department names or ``"all"``.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    name: NotBlankStr = Field(
        description="Ceremony identifier",
    )
    protocol: MeetingProtocolType = Field(
        description="Meeting protocol type",
    )
    frequency: MeetingFrequency = Field(
        description="Recurrence frequency",
    )
    duration_tokens: int = Field(
        default=5000,
        ge=100,
        le=50_000,
        description="Token budget for the meeting",
    )
    participants: tuple[NotBlankStr, ...] = Field(
        default=(),
        description='Department names or "all"',
    )


class SprintConfig(BaseModel):
    """Agile sprint workflow configuration.

    Attributes:
        duration_days: Default sprint duration in days.
        max_tasks_per_sprint: Maximum tasks allowed in a sprint backlog.
        velocity_window: Number of recent sprints for rolling velocity
            average.
        ceremonies: Sprint ceremony definitions.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    duration_days: int = Field(
        default=14,
        ge=1,
        le=90,
        description="Default sprint duration in days",
    )
    max_tasks_per_sprint: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Maximum tasks per sprint backlog",
    )
    velocity_window: int = Field(
        default=3,
        ge=1,
        le=20,
        description="Sprints for rolling velocity average",
    )
    ceremonies: tuple[SprintCeremonyConfig, ...] = Field(
        default=(
            SprintCeremonyConfig(
                name="sprint_planning",
                protocol=MeetingProtocolType.STRUCTURED_PHASES,
                frequency=MeetingFrequency.BI_WEEKLY,
            ),
            SprintCeremonyConfig(
                name="daily_standup",
                protocol=MeetingProtocolType.ROUND_ROBIN,
                frequency=MeetingFrequency.PER_SPRINT_DAY,
                duration_tokens=2000,
            ),
            SprintCeremonyConfig(
                name="sprint_review",
                protocol=MeetingProtocolType.ROUND_ROBIN,
                frequency=MeetingFrequency.BI_WEEKLY,
            ),
            SprintCeremonyConfig(
                name="retrospective",
                protocol=MeetingProtocolType.POSITION_PAPERS,
                frequency=MeetingFrequency.BI_WEEKLY,
                duration_tokens=3000,
            ),
        ),
        description="Sprint ceremony definitions",
    )

    @model_validator(mode="after")
    def _validate_unique_ceremony_names(self) -> Self:
        """Reject duplicate ceremony names."""
        names = [c.name for c in self.ceremonies]
        if len(names) != len(set(names)):
            dupes = sorted(n for n, count in Counter(names).items() if count > 1)
            msg = f"Duplicate ceremony names: {dupes}"
            raise ValueError(msg)
        return self
