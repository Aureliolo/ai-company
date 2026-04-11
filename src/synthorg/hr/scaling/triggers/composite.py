"""Composite scaling trigger -- combines multiple triggers with OR."""

from typing import TYPE_CHECKING

from synthorg.observability import get_logger

if TYPE_CHECKING:
    from synthorg.core.types import NotBlankStr
    from synthorg.hr.scaling.protocols import ScalingTrigger

logger = get_logger(__name__)


class CompositeScalingTrigger:
    """Combines multiple triggers with OR semantics.

    Fires if any child trigger fires.

    Args:
        triggers: Child triggers to combine.
    """

    def __init__(
        self,
        *,
        triggers: tuple[ScalingTrigger, ...],
    ) -> None:
        self._triggers = triggers

    @property
    def name(self) -> NotBlankStr:
        """Trigger name."""
        return "composite"  # type: ignore[return-value]

    async def should_trigger(self) -> bool:
        """Trigger if any child trigger fires."""
        for trigger in self._triggers:
            if await trigger.should_trigger():
                return True
        return False
