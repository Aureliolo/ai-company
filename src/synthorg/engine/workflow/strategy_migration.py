"""Strategy migration detection and notification.

When the ceremony scheduling strategy changes between sprints, the
system detects the change at ``activate_sprint()`` time and provides
a ``StrategyMigrationInfo`` result.  A separate ``notify_strategy_migration()``
function sends best-effort notifications via the communication system.
"""

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from synthorg.communication.enums import MessagePriority, MessageType
from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.engine.workflow.ceremony_policy import (
    CeremonyStrategyType,  # noqa: TC001
)
from synthorg.observability import get_logger
from synthorg.observability.events.workflow import (
    SPRINT_CEREMONY_STRATEGY_CHANGED,
)

if TYPE_CHECKING:
    from synthorg.communication.messenger import AgentMessenger

logger = get_logger(__name__)


class StrategyMigrationInfo(BaseModel):
    """Information about a ceremony strategy change between sprints.

    Produced by ``detect_strategy_migration()`` when the active strategy
    type changes.  The caller uses this to dispatch migration
    notifications via ``notify_strategy_migration()``.

    Attributes:
        sprint_id: The sprint being activated.
        previous_strategy: The outgoing strategy type.
        new_strategy: The incoming strategy type.
        velocity_window_reset: Always ``True`` -- the velocity
            rolling-average window resets on strategy change because
            each strategy uses a different velocity calculator with
            different units.
        velocity_history_size: Number of velocity records from the
            old strategy (retained but no longer used for computed
            metrics).
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    sprint_id: NotBlankStr = Field(
        description="The sprint being activated",
    )
    previous_strategy: CeremonyStrategyType = Field(
        description="The outgoing strategy type",
    )
    new_strategy: CeremonyStrategyType = Field(
        description="The incoming strategy type",
    )
    velocity_window_reset: bool = Field(
        description="Whether velocity window resets (always True)",
    )
    velocity_history_size: int = Field(
        ge=0,
        description="Velocity records from old strategy",
    )


def detect_strategy_migration(
    previous_strategy_type: CeremonyStrategyType | None,
    new_strategy_type: CeremonyStrategyType,
    sprint_id: str,
    velocity_history_size: int,
) -> StrategyMigrationInfo | None:
    """Detect a strategy change between sprints.

    Returns ``None`` on first activation (no previous strategy) or
    when the strategy type has not changed.

    Args:
        previous_strategy_type: The outgoing strategy type, or
            ``None`` on first activation.
        new_strategy_type: The incoming strategy type.
        sprint_id: The sprint being activated.
        velocity_history_size: Number of velocity records from the
            old strategy.

    Returns:
        Migration info if the strategy changed, else ``None``.
    """
    if previous_strategy_type is None:
        return None
    if previous_strategy_type == new_strategy_type:
        return None
    return StrategyMigrationInfo(
        sprint_id=sprint_id,
        previous_strategy=previous_strategy_type,
        new_strategy=new_strategy_type,
        velocity_window_reset=True,
        velocity_history_size=velocity_history_size,
    )


def format_migration_warning(info: StrategyMigrationInfo) -> str:
    """Format the migration warning message text.

    Pure function -- no I/O, safe to call from any context.

    Args:
        info: The migration info.

    Returns:
        Human-readable warning text.
    """
    return (
        f"Ceremony scheduling strategy changed from"
        f" '{info.previous_strategy.value}' to"
        f" '{info.new_strategy.value}' for sprint"
        f" {info.sprint_id}. This change takes effect at"
        f" sprint start and may cause initial ceremony"
        f" optimization issues while the system adapts."
        f" The velocity rolling-average window has been"
        f" reset ({info.velocity_history_size} prior sprint"
        f" records from the '{info.previous_strategy.value}'"
        f" strategy will not carry over)."
    )


def format_reorder_prompt(info: StrategyMigrationInfo) -> str:
    """Format the reorder action-item text.

    Pure function -- no I/O, safe to call from any context.

    Args:
        info: The migration info.

    Returns:
        Action-item text for the responsible role.
    """
    return (
        f"ACTION REQUIRED: The ceremony scheduling strategy"
        f" has changed to '{info.new_strategy.value}'."
        f" Please review and reorder the sprint backlog to"
        f" align with the new strategy's optimization"
        f" approach. Previous velocity data"
        f" ({info.velocity_history_size} sprints under"
        f" '{info.previous_strategy.value}') has been reset."
    )


async def notify_strategy_migration(
    info: StrategyMigrationInfo,
    messenger: AgentMessenger,
    *,
    responsible_role: str = "scrum_master",
    channel: str = "#sprint-team",
) -> None:
    """Send migration notifications via the communication system.

    Best-effort: non-fatal errors are logged and swallowed.
    ``MemoryError`` and ``RecursionError`` propagate.

    Sends two messages:

    1. A broadcast ``ANNOUNCEMENT`` with the migration warning.
    2. A channel ``TASK_UPDATE`` with the reorder action item
       directed at the responsible role.

    Args:
        info: The migration info.
        messenger: Per-agent messenger facade.
        responsible_role: Agent role to receive the reorder prompt.
        channel: Channel for the reorder prompt message.
    """
    try:
        await messenger.broadcast(
            content=format_migration_warning(info),
            message_type=MessageType.ANNOUNCEMENT,
            priority=MessagePriority.HIGH,
        )
    except MemoryError, RecursionError:
        raise
    except Exception:
        logger.warning(
            SPRINT_CEREMONY_STRATEGY_CHANGED,
            sprint_id=info.sprint_id,
            note="broadcast notification failed",
        )

    try:
        await messenger.send_message(
            to=responsible_role,
            channel=channel,
            content=format_reorder_prompt(info),
            message_type=MessageType.TASK_UPDATE,
            priority=MessagePriority.HIGH,
        )
    except MemoryError, RecursionError:
        raise
    except Exception:
        logger.warning(
            SPRINT_CEREMONY_STRATEGY_CHANGED,
            sprint_id=info.sprint_id,
            note="reorder prompt notification failed",
        )
