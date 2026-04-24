"""Message bus → Litestar channels bridge.

Subscribes to internal ``MessageBus`` channels and forwards
events to Litestar's ``ChannelsPlugin`` for WebSocket delivery.
"""

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Final

from litestar.channels import ChannelsPlugin  # noqa: TC002

from synthorg.api.channels import ALL_CHANNELS
from synthorg.api.ws_models import WsEvent, WsEventType
from synthorg.communication.bus_protocol import MessageBus  # noqa: TC001
from synthorg.communication.errors import CommunicationError
from synthorg.communication.message import Message  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.background_tasks import log_task_exceptions
from synthorg.observability.events.api import (
    API_APP_SHUTDOWN,
    API_APP_STARTUP,
    API_BRIDGE_CHANNEL_DEAD,
    API_BUS_BRIDGE_POLL_ERROR,
    API_BUS_BRIDGE_SUBSCRIBE_FAILED,
)
from synthorg.settings.enums import SettingNamespace

if TYPE_CHECKING:
    from synthorg.settings.resolver import ConfigResolver

logger = get_logger(__name__)

_SUBSCRIBER_ID: Final[str] = "__api_bridge__"
_POLL_TIMEOUT: Final[float] = 1.0
"""Fallback poll timeout used when no resolver is wired in."""
_MAX_CONSECUTIVE_ERRORS: Final[int] = 30
"""Fallback error budget used when no resolver is wired in."""
_STOP_DRAIN_TIMEOUT_SECONDS: Final[float] = 10.0
"""Hard deadline for the ``stop()`` drain.

Per CLAUDE.md ``## Code Conventions`` > Lifecycle synchronization:
services whose ``stop()`` drains across ``await`` boundaries must
wrap the drain in ``asyncio.wait_for`` so the lifecycle lock cannot
be held indefinitely if a polling task ignores cancellation.
"""


class MessageBusBridge:
    """Bridge between internal ``MessageBus`` and Litestar channels.

    Subscribes to each internal message bus channel as
    ``__api_bridge__`` and re-publishes messages as ``WsEvent``
    JSON to the corresponding Litestar channel.

    Uses bare ``asyncio.create_task`` instead of ``TaskGroup``
    because the polling tasks must outlive the ``start()`` call
    frame -- they run continuously until ``stop()`` is called.

    Attributes:
        _bus: The internal message bus to poll.
        _plugin: The Litestar channels plugin to publish to.
    """

    def __init__(
        self,
        message_bus: MessageBus,
        channels_plugin: ChannelsPlugin,
        *,
        config_resolver: ConfigResolver | None = None,
    ) -> None:
        self._bus = message_bus
        self._plugin = channels_plugin
        self._config_resolver = config_resolver
        self._tasks: list[asyncio.Task[None]] = []
        self._running: bool = False
        # Set to True when a stop() drain exceeds the hard deadline.
        # Prevents a subsequent start() from creating a second poller
        # set on top of orphaned pollers that ignored cancellation
        # (they would race on the same ``_SUBSCRIBER_ID`` subscription
        # and split or duplicate WebSocket delivery). Recovery
        # requires a fresh ``MessageBusBridge`` instance.
        self._stop_failed: bool = False
        # Serializes start() / stop() so the check-and-set on
        # _running is atomic against concurrent lifecycle calls.
        # Does not gate publish / receive (those use the underlying
        # bus lock) so normal traffic is not serialized here.
        self._lifecycle_lock = asyncio.Lock()
        # Resolver-failure warnings are logged only on the first
        # failure in a run of failures to avoid flooding logs during
        # a prolonged settings outage. The flag is cleared on the
        # first successful resolution so a re-failure still surfaces.
        self._poll_timeout_fallback_logged: bool = False
        self._max_errors_fallback_logged: bool = False

    async def _get_poll_timeout(self) -> float:
        """Resolve the current poll timeout, falling back to the constant.

        A transient settings outage or malformed value must not crash
        the polling loop. Warnings are log-once per run of failures
        (cleared on recovery) so a prolonged outage cannot flood logs.
        """
        if self._config_resolver is None:
            return _POLL_TIMEOUT
        try:
            value = await self._config_resolver.get_float(
                SettingNamespace.COMMUNICATION.value,
                "bus_bridge_poll_timeout_seconds",
            )
        except asyncio.CancelledError:
            raise
        except MemoryError, RecursionError:
            raise
        except Exception:
            if not self._poll_timeout_fallback_logged:
                logger.warning(
                    API_BUS_BRIDGE_POLL_ERROR,
                    error=(
                        "failed to resolve bus_bridge_poll_timeout_seconds;"
                        " using fallback (logging suppressed until recovery)"
                    ),
                    poll_timeout=_POLL_TIMEOUT,
                    exc_info=True,
                )
                self._poll_timeout_fallback_logged = True
            return _POLL_TIMEOUT
        self._poll_timeout_fallback_logged = False
        return value

    async def _get_max_consecutive_errors(self) -> int:
        """Resolve the current error budget, falling back to the constant.

        Same guard and log-once-per-failure-run semantics as
        :meth:`_get_poll_timeout`.
        """
        if self._config_resolver is None:
            return _MAX_CONSECUTIVE_ERRORS
        try:
            value = await self._config_resolver.get_int(
                SettingNamespace.COMMUNICATION.value,
                "bus_bridge_max_consecutive_errors",
            )
        except asyncio.CancelledError:
            raise
        except MemoryError, RecursionError:
            raise
        except Exception:
            if not self._max_errors_fallback_logged:
                logger.warning(
                    API_BUS_BRIDGE_POLL_ERROR,
                    error=(
                        "failed to resolve bus_bridge_max_consecutive_errors;"
                        " using fallback (logging suppressed until recovery)"
                    ),
                    max_errors=_MAX_CONSECUTIVE_ERRORS,
                    exc_info=True,
                )
                self._max_errors_fallback_logged = True
            return _MAX_CONSECUTIVE_ERRORS
        self._max_errors_fallback_logged = False
        return value

    async def start(self) -> None:
        """Start polling tasks for each channel.

        The entire body runs under ``_lifecycle_lock`` so the
        check-and-set on ``_running`` is atomic against concurrent
        ``start()`` / ``stop()`` calls, and the per-channel
        subscribe + task-spawn loop cannot interleave with a racing
        lifecycle transition.

        Raises:
            RuntimeError: If the bridge is already running.
        """
        async with self._lifecycle_lock:
            if self._stop_failed:
                msg = (
                    "MessageBusBridge is unrestartable after a timed-out stop; "
                    "construct a fresh MessageBusBridge instead"
                )
                logger.warning(API_APP_STARTUP, error=msg)
                raise RuntimeError(msg)
            if self._running:
                msg = "MessageBusBridge is already running"
                logger.warning(API_APP_STARTUP, error=msg)
                raise RuntimeError(msg)

            logger.info(API_APP_STARTUP, component="bus_bridge")
            self._running = True

            failed_channels: list[str] = []
            for channel_name in ALL_CHANNELS:
                try:
                    await self._bus.subscribe(channel_name, _SUBSCRIBER_ID)
                # Catch ``CommunicationError`` (base of ``BusStreamError``
                # raised by the NATS pull-consumer creation path) in
                # addition to OS/connection errors so a single broken
                # backend does not abort the whole start() -- the
                # partial-coverage escalation below still surfaces it.
                # ``RuntimeError`` remains in the tuple to preserve the
                # previous catch surface for backend implementations
                # that raise it on transient wiring errors.
                except CommunicationError, OSError, RuntimeError, ConnectionError:
                    # Track per-channel subscribe failures so we can
                    # surface incomplete coverage at ERROR with the full
                    # list -- a single transient failure must not
                    # silently mask a dead channel from operators.
                    failed_channels.append(channel_name)
                    logger.warning(
                        API_BUS_BRIDGE_SUBSCRIBE_FAILED,
                        channel=channel_name,
                        subscriber_id=_SUBSCRIBER_ID,
                        exc_info=True,
                    )
                    continue
                task = asyncio.create_task(
                    self._poll_channel(channel_name),
                    name=f"bridge-{channel_name}",
                )
                task.add_done_callback(
                    log_task_exceptions(
                        logger,
                        API_BRIDGE_CHANNEL_DEAD,
                        channel=channel_name,
                    ),
                )
                self._tasks.append(task)

            if not self._tasks:
                self._running = False
                logger.error(
                    API_APP_STARTUP,
                    error="bus bridge started with zero active channels",
                    failed_channels=tuple(failed_channels),
                )
                msg = "MessageBusBridge failed to subscribe to any channels"
                raise RuntimeError(msg)

            if failed_channels:
                # Started with partial coverage. Keep running (the
                # healthy channels still serve traffic) but emit at
                # ERROR so operators see the gap -- a WARNING per
                # failed channel is not aggregated anywhere and a
                # silent partial bridge is indistinguishable from a
                # healthy one from a supervisor perspective.
                logger.error(
                    API_APP_STARTUP,
                    error="bus bridge started with incomplete channel coverage",
                    active_channels=len(self._tasks),
                    failed_channels=tuple(failed_channels),
                    total_channels=len(ALL_CHANNELS),
                )

    async def stop(self) -> None:
        """Cancel all polling tasks.

        Holds ``_lifecycle_lock`` so ``stop()`` cannot race a
        partially-constructed ``start()`` (e.g. ``_running=True`` but
        some channels still mid-subscribe).
        """
        async with self._lifecycle_lock:
            if not self._running:
                return

            logger.info(API_APP_SHUTDOWN, component="bus_bridge")
            for task in self._tasks:
                task.cancel()
            if self._tasks:
                results: list[BaseException | None]
                try:
                    results = await asyncio.wait_for(
                        asyncio.gather(
                            *self._tasks,
                            return_exceptions=True,
                        ),
                        timeout=_STOP_DRAIN_TIMEOUT_SECONDS,
                    )
                except TimeoutError:
                    # Drain exceeded the hard deadline. Mark the bridge
                    # unrestartable and re-raise: a future start() must
                    # not attach a fresh poller set on the same static
                    # ``_SUBSCRIBER_ID`` subscription alongside orphaned
                    # pollers that ignored cancellation, because that
                    # would split or duplicate WebSocket delivery. Leave
                    # ``_tasks`` + ``_running`` intact so the bridge's
                    # state reflects the incomplete shutdown; the caller
                    # receives the TimeoutError and must reconstruct a
                    # fresh ``MessageBusBridge`` to recover.
                    self._stop_failed = True
                    # TRY400: logger.exception here would append a
                    # TimeoutError traceback with no actionable diagnostic
                    # information beyond the structured fields below.
                    logger.error(  # noqa: TRY400
                        API_APP_SHUTDOWN,
                        component="bus_bridge",
                        error=(
                            "stop exceeded hard deadline; bridge marked unrestartable"
                        ),
                        timeout_seconds=_STOP_DRAIN_TIMEOUT_SECONDS,
                        pending_tasks=sum(1 for t in self._tasks if not t.done()),
                    )
                    raise
                for result in results:
                    if isinstance(result, asyncio.CancelledError):
                        continue
                    if isinstance(result, BaseException):
                        logger.warning(
                            API_APP_SHUTDOWN,
                            component="bus_bridge",
                            error=str(result),
                            exc_info=result,
                        )
            self._tasks.clear()
            self._running = False

    async def _poll_channel(self, channel_name: str) -> None:
        """Poll a single channel and publish to Litestar.

        Stops polling after the configured max-consecutive-errors
        budget is exhausted to avoid infinite log spam on broken
        channels.  Poll timeout and error budget are re-read each
        iteration so operator tuning via settings takes effect
        without a restart.  Each iteration caches both values up
        front so the receive/sleep pair and the error-budget check
        observe the same values even if the operator edits the
        setting mid-iteration.
        """
        consecutive_errors = 0
        while True:
            poll_timeout = await self._get_poll_timeout()
            max_errors = await self._get_max_consecutive_errors()
            try:
                envelope = await self._bus.receive(
                    channel_name,
                    _SUBSCRIBER_ID,
                    timeout=poll_timeout,
                )
                if envelope is None:
                    continue
                ws_event = self._to_ws_event(envelope.message, channel_name)
                self._plugin.publish(
                    ws_event.model_dump_json(),
                    channels=[channel_name],
                )
                consecutive_errors = 0
            except asyncio.CancelledError:
                break
            except OSError, ConnectionError, TimeoutError:
                consecutive_errors += 1
                if consecutive_errors >= max_errors:
                    logger.error(
                        API_BRIDGE_CHANNEL_DEAD,
                        channel=channel_name,
                        consecutive_errors=consecutive_errors,
                        exc_info=True,
                    )
                    break
                logger.warning(
                    API_BUS_BRIDGE_POLL_ERROR,
                    channel=channel_name,
                    consecutive_errors=consecutive_errors,
                    exc_info=True,
                )
                await asyncio.sleep(poll_timeout)
            except Exception:
                logger.error(
                    API_BRIDGE_CHANNEL_DEAD,
                    channel=channel_name,
                    exc_info=True,
                )
                break

    @staticmethod
    def _to_ws_event(message: Message, channel_name: str) -> WsEvent:
        """Convert an internal ``Message`` to a ``WsEvent``."""
        payload: dict[str, Any] = {
            "message_id": str(message.id),
            "sender": message.sender,
            "to": message.to,
            "content": message.text,
            "parts": [p.model_dump(mode="json") for p in message.parts],
        }
        return WsEvent(
            event_type=WsEventType.MESSAGE_SENT,
            channel=channel_name,
            timestamp=datetime.now(UTC),
            payload=payload,
        )
