"""Webhook event bus bridge.

Subscribes to the ``#webhooks`` bus channel and forwards events
into ``ExternalTriggerStrategy.on_external_event()`` on active
sprints.
"""

import asyncio
import contextlib
from typing import Final

from synthorg.communication.bus_protocol import MessageBus  # noqa: TC001
from synthorg.communication.message import DataPart
from synthorg.engine.workflow.ceremony_scheduler import CeremonyScheduler  # noqa: TC001
from synthorg.engine.workflow.strategies.external_trigger import (
    ExternalTriggerStrategy,
)
from synthorg.integrations.webhooks.event_bus_bridge import WEBHOOK_CHANNEL
from synthorg.observability import get_logger
from synthorg.observability.events.integrations import (
    WEBHOOK_BRIDGE_EVENT_FORWARDED,
    WEBHOOK_BRIDGE_POLL_ERROR,
    WEBHOOK_BRIDGE_STARTED,
    WEBHOOK_BRIDGE_STOPPED,
)

logger = get_logger(__name__)

_SUBSCRIBER_ID: Final[str] = "__webhook_bridge__"
_POLL_TIMEOUT: Final[float] = 1.0
_MAX_CONSECUTIVE_ERRORS: Final[int] = 30


class WebhookEventBridge:
    """Bridges webhook bus events to the ceremony scheduler.

    Subscribes to ``#webhooks`` and forwards each verified event
    into the active sprint's ``ExternalTriggerStrategy`` (if any).

    Args:
        bus: The message bus instance.
        ceremony_scheduler: The ceremony scheduler holding the
            active sprint and strategy.
    """

    def __init__(
        self,
        bus: MessageBus,
        ceremony_scheduler: CeremonyScheduler,
    ) -> None:
        self._bus = bus
        self._scheduler = ceremony_scheduler
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Subscribe and start the polling task."""
        if self._task is not None:
            return
        await self._bus.subscribe(
            WEBHOOK_CHANNEL.name,
            _SUBSCRIBER_ID,
        )
        self._task = asyncio.create_task(
            self._poll_loop(),
            name="webhook-event-bridge",
        )
        logger.info(WEBHOOK_BRIDGE_STARTED)

    async def stop(self) -> None:
        """Cancel the polling task and unsubscribe."""
        if self._task is None:
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None
        with contextlib.suppress(Exception):
            await self._bus.unsubscribe(
                WEBHOOK_CHANNEL.name,
                _SUBSCRIBER_ID,
            )
        logger.info(WEBHOOK_BRIDGE_STOPPED)

    async def _poll_loop(self) -> None:
        """Poll ``#webhooks`` and forward events."""
        consecutive_errors = 0
        while True:
            try:
                envelope = await self._bus.receive(
                    WEBHOOK_CHANNEL.name,
                    _SUBSCRIBER_ID,
                    timeout=_POLL_TIMEOUT,
                )
                if envelope is None:
                    continue
                consecutive_errors = 0
                await self._forward(envelope.message)
            except asyncio.CancelledError:
                break
            except Exception:
                consecutive_errors += 1
                if consecutive_errors >= _MAX_CONSECUTIVE_ERRORS:
                    logger.exception(
                        WEBHOOK_BRIDGE_POLL_ERROR,
                        error="too many consecutive errors, stopping",
                    )
                    break
                logger.warning(
                    WEBHOOK_BRIDGE_POLL_ERROR,
                    consecutive_errors=consecutive_errors,
                    exc_info=True,
                )

    async def _forward(self, message: object) -> None:
        """Extract event data and call on_external_event."""
        from synthorg.communication.message import Message  # noqa: PLC0415

        if not isinstance(message, Message):
            return
        strategy, sprint = await self._scheduler.get_active_info()
        if strategy is None or sprint is None:
            return
        if not isinstance(strategy, ExternalTriggerStrategy):
            return

        for part in message.parts:
            if not isinstance(part, DataPart):
                continue
            data = dict(part.data) if part.data is not None else {}
            event_type = data.get("event_type", "")
            if not event_type:
                continue
            await strategy.on_external_event(
                sprint,
                event_type,
                data.get("payload", {}),
            )
            logger.debug(
                WEBHOOK_BRIDGE_EVENT_FORWARDED,
                event_type=event_type,
                connection_name=data.get("connection_name"),
            )
