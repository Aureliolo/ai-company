"""External-trigger ceremony scheduling strategy.

Ceremonies fire on external signals: webhooks, CI/CD events, git
events, MCP tool invocations.  Bridges the synthetic org with
real-world development workflows.

**Config keys** (per-ceremony ``policy_override.strategy_config``):

- ``on_external`` (str): external event name that triggers this
  ceremony.

**Config keys** (sprint-level ``ceremony_policy.strategy_config``):

- ``sources`` (list[dict]): event source definitions (type + config).
- ``transition_event`` (str): external event that triggers sprint
  auto-transition.
"""

from typing import TYPE_CHECKING, Any

from synthorg.engine.workflow.ceremony_policy import (
    CeremonyStrategyType,
)
from synthorg.engine.workflow.sprint_lifecycle import Sprint, SprintStatus
from synthorg.engine.workflow.strategies._helpers import get_ceremony_config
from synthorg.engine.workflow.velocity_types import VelocityCalcType
from synthorg.observability import get_logger
from synthorg.observability.events.workflow import (
    SPRINT_AUTO_TRANSITION,
    SPRINT_CEREMONY_EXTERNAL_EVENT_MATCHED,
    SPRINT_CEREMONY_EXTERNAL_EVENT_RECEIVED,
    SPRINT_CEREMONY_EXTERNAL_SOURCE_CLEARED,
    SPRINT_CEREMONY_EXTERNAL_SOURCE_REGISTERED,
    SPRINT_CEREMONY_SKIPPED,
    SPRINT_CEREMONY_TRIGGERED,
    SPRINT_STRATEGY_CONFIG_INVALID,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from synthorg.engine.workflow.ceremony_context import CeremonyEvalContext
    from synthorg.engine.workflow.sprint_config import (
        SprintCeremonyConfig,
        SprintConfig,
    )

logger = get_logger(__name__)

# -- Config keys ---------------------------------------------------------------

_KEY_ON_EXTERNAL: str = "on_external"
_KEY_TRANSITION_EVENT: str = "transition_event"
_KEY_SOURCES: str = "sources"

_KNOWN_CONFIG_KEYS: frozenset[str] = frozenset(
    {
        _KEY_ON_EXTERNAL,
        _KEY_TRANSITION_EVENT,
        _KEY_SOURCES,
    }
)

# -- Defaults and limits -------------------------------------------------------

_MAX_EVENT_NAME_LEN: int = 128
_MAX_SOURCES: int = 20
_MAX_RECEIVED_EVENTS: int = 256
_VALID_SOURCE_TYPES: frozenset[str] = frozenset({"webhook", "git_event"})


class ExternalTriggerStrategy:
    """Ceremony scheduling strategy driven by external signals.

    Ceremonies fire when a matching external event is received -- via
    ``context.external_events`` or the ``on_external_event`` lifecycle
    hook.  Event source registration is declarative (validated and
    stored, but transport integration is handled externally).

    This is a **stateful strategy** -- lifecycle hooks manage event
    subscriptions and buffered events per sprint.
    """

    __slots__ = (
        "_event_counts",
        "_received_events",
        "_sources",
    )

    def __init__(self) -> None:
        self._received_events: set[str] = set()
        self._event_counts: dict[str, int] = {}
        self._sources: tuple[dict[str, Any], ...] = ()

    # -- Core evaluation -------------------------------------------------------

    def should_fire_ceremony(
        self,
        ceremony: SprintCeremonyConfig,
        sprint: Sprint,  # noqa: ARG002
        context: CeremonyEvalContext,
    ) -> bool:
        """Return True when a matching external event has been received.

        Args:
            ceremony: The ceremony configuration being evaluated.
            sprint: Current sprint state.
            context: Evaluation context.

        Returns:
            ``True`` if the ceremony should fire.
        """
        config = get_ceremony_config(ceremony)
        on_external = config.get(_KEY_ON_EXTERNAL)

        if not self._is_valid_event_name(on_external):
            return False

        event_name = str(on_external).strip()

        if event_name in context.external_events:
            logger.info(
                SPRINT_CEREMONY_EXTERNAL_EVENT_MATCHED,
                ceremony=ceremony.name,
                event_name=event_name,
                source="context",
                strategy="external_trigger",
            )
            logger.info(
                SPRINT_CEREMONY_TRIGGERED,
                ceremony=ceremony.name,
                reason="external_event",
                strategy="external_trigger",
            )
            return True

        if event_name in self._received_events:
            logger.info(
                SPRINT_CEREMONY_EXTERNAL_EVENT_MATCHED,
                ceremony=ceremony.name,
                event_name=event_name,
                source="received_buffer",
                strategy="external_trigger",
            )
            logger.info(
                SPRINT_CEREMONY_TRIGGERED,
                ceremony=ceremony.name,
                reason="external_event",
                strategy="external_trigger",
            )
            return True

        return False

    def should_transition_sprint(
        self,
        sprint: Sprint,
        config: SprintConfig,
        context: CeremonyEvalContext,
    ) -> SprintStatus | None:
        """Return IN_REVIEW when the configured transition event fires.

        Only transitions from ACTIVE status.

        Args:
            sprint: Current sprint state.
            config: Sprint configuration.
            context: Evaluation context.

        Returns:
            ``SprintStatus.IN_REVIEW`` if transition event detected,
            else ``None``.
        """
        if sprint.status is not SprintStatus.ACTIVE:
            return None

        strategy_config = config.ceremony_policy.strategy_config or {}
        raw_transition = strategy_config.get(_KEY_TRANSITION_EVENT)
        if not self._is_valid_event_name(raw_transition):
            return None

        transition_event = str(raw_transition).strip()

        if transition_event in context.external_events:
            logger.info(
                SPRINT_AUTO_TRANSITION,
                transition_event=transition_event,
                source="external_events",
                strategy="external_trigger",
            )
            return SprintStatus.IN_REVIEW

        if transition_event in self._received_events:
            logger.info(
                SPRINT_AUTO_TRANSITION,
                transition_event=transition_event,
                source="received_buffer",
                strategy="external_trigger",
            )
            return SprintStatus.IN_REVIEW

        return None

    # -- Lifecycle hooks -------------------------------------------------------

    async def on_sprint_activated(
        self,
        sprint: Sprint,  # noqa: ARG002
        config: SprintConfig,
    ) -> None:
        """Clear state and register event sources from config.

        Args:
            sprint: The activated sprint.
            config: Sprint configuration.
        """
        self._received_events.clear()
        self._event_counts.clear()

        strategy_config = (
            config.ceremony_policy.strategy_config
            if config.ceremony_policy.strategy_config is not None
            else {}
        )

        raw_sources = strategy_config.get(_KEY_SOURCES)
        if isinstance(raw_sources, list):
            self._sources = tuple(
                dict(entry) for entry in raw_sources if isinstance(entry, dict)
            )
        else:
            self._sources = ()

        if self._sources:
            logger.info(
                SPRINT_CEREMONY_EXTERNAL_SOURCE_REGISTERED,
                source_count=len(self._sources),
                source_types=[s.get("type") for s in self._sources],
                strategy="external_trigger",
            )

    async def on_sprint_deactivated(self) -> None:
        """Clear all internal state."""
        if self._sources:
            logger.info(
                SPRINT_CEREMONY_EXTERNAL_SOURCE_CLEARED,
                source_count=len(self._sources),
                strategy="external_trigger",
            )
        self._received_events.clear()
        self._event_counts.clear()
        self._sources = ()

    async def on_task_completed(
        self,
        sprint: Sprint,
        task_id: str,
        story_points: float,
        context: CeremonyEvalContext,
    ) -> None:
        """No-op."""

    async def on_task_added(
        self,
        sprint: Sprint,
        task_id: str,
    ) -> None:
        """No-op."""

    async def on_task_blocked(
        self,
        sprint: Sprint,
        task_id: str,
    ) -> None:
        """No-op."""

    async def on_budget_updated(
        self,
        sprint: Sprint,
        budget_consumed_fraction: float,
    ) -> None:
        """No-op."""

    async def on_external_event(
        self,
        sprint: Sprint,  # noqa: ARG002
        event_name: str,
        payload: Mapping[str, Any],  # noqa: ARG002
    ) -> None:
        """Buffer an external event for evaluation.

        Args:
            sprint: Current sprint state.
            event_name: Name of the external event.
            payload: Event payload data.
        """
        if not self._is_valid_event_name(event_name):
            logger.warning(
                SPRINT_CEREMONY_SKIPPED,
                reason="invalid_external_event_name",
                value=(
                    event_name
                    if isinstance(event_name, str)
                    else type(event_name).__name__
                ),
                strategy="external_trigger",
            )
            return

        cleaned = event_name.strip()

        if (
            cleaned not in self._received_events
            and len(self._received_events) >= _MAX_RECEIVED_EVENTS
        ):
            logger.warning(
                SPRINT_CEREMONY_SKIPPED,
                reason="too_many_distinct_events",
                event_name=cleaned,
                limit=_MAX_RECEIVED_EVENTS,
                strategy="external_trigger",
            )
            return

        self._received_events.add(cleaned)
        self._event_counts[cleaned] = self._event_counts.get(cleaned, 0) + 1
        logger.debug(
            SPRINT_CEREMONY_EXTERNAL_EVENT_RECEIVED,
            event_name=cleaned,
            count=self._event_counts[cleaned],
            strategy="external_trigger",
        )

    # -- Metadata --------------------------------------------------------------

    @property
    def strategy_type(self) -> CeremonyStrategyType:
        """Return EXTERNAL_TRIGGER."""
        return CeremonyStrategyType.EXTERNAL_TRIGGER

    def get_default_velocity_calculator(self) -> VelocityCalcType:
        """Return POINTS_PER_SPRINT."""
        return VelocityCalcType.POINTS_PER_SPRINT

    def validate_strategy_config(
        self,
        config: Mapping[str, Any],
    ) -> None:
        """Validate external-trigger strategy config.

        Args:
            config: Strategy config to validate.

        Raises:
            ValueError: If the config contains invalid keys or values.
        """
        unknown = set(config) - _KNOWN_CONFIG_KEYS
        if unknown:
            msg = f"Unknown config keys: {sorted(unknown)}"
            logger.warning(
                SPRINT_STRATEGY_CONFIG_INVALID,
                strategy="external_trigger",
                unknown_keys=sorted(unknown),
            )
            raise ValueError(msg)

        self._validate_string_key(config, _KEY_ON_EXTERNAL)
        self._validate_string_key(config, _KEY_TRANSITION_EVENT)
        self._validate_sources(config)

    # -- Private helpers -------------------------------------------------------

    @staticmethod
    def _is_valid_event_name(value: object) -> bool:
        """Check if a value is a valid external event name."""
        return (
            isinstance(value, str)
            and bool(value.strip())
            and len(value) <= _MAX_EVENT_NAME_LEN
        )

    @staticmethod
    def _validate_string_key(
        config: Mapping[str, Any],
        key: str,
    ) -> None:
        """Validate that *key* is a non-empty string if present."""
        value = config.get(key)
        if value is None:
            return
        if (
            not isinstance(value, str)
            or not value.strip()
            or len(value) > _MAX_EVENT_NAME_LEN
        ):
            msg = f"'{key}' must be a non-empty string (<= {_MAX_EVENT_NAME_LEN} chars)"
            logger.warning(
                SPRINT_STRATEGY_CONFIG_INVALID,
                strategy="external_trigger",
                key=key,
                value=value,
            )
            raise ValueError(msg)

    @staticmethod
    def _validate_sources(config: Mapping[str, Any]) -> None:
        """Validate the sources list if present."""
        sources = config.get(_KEY_SOURCES)
        if sources is None:
            return
        if not isinstance(sources, list):
            msg = "'sources' must be a list"
            logger.warning(
                SPRINT_STRATEGY_CONFIG_INVALID,
                strategy="external_trigger",
                key=_KEY_SOURCES,
                value=type(sources).__name__,
            )
            raise TypeError(msg)
        if len(sources) > _MAX_SOURCES:
            msg = f"'sources' must have at most {_MAX_SOURCES} entries"
            logger.warning(
                SPRINT_STRATEGY_CONFIG_INVALID,
                strategy="external_trigger",
                key=_KEY_SOURCES,
                count=len(sources),
                limit=_MAX_SOURCES,
            )
            raise ValueError(msg)
        for i, entry in enumerate(sources):
            if not isinstance(entry, dict):
                msg = f"sources[{i}] must be a dict"
                raise TypeError(msg)
            source_type = entry.get("type")
            if source_type is None:
                msg = f"sources[{i}] must have a 'type' key"
                raise ValueError(msg)
            if source_type not in _VALID_SOURCE_TYPES:
                msg = (
                    f"sources[{i}].type must be one of "
                    f"{sorted(_VALID_SOURCE_TYPES)}, got {source_type!r}"
                )
                raise ValueError(msg)
