"""POSIX signal handlers for orderly shutdown.

Uvicorn installs its own ``SIGTERM``/``SIGINT`` handlers that flip the
ASGI lifespan into shutdown -- which is what ultimately drives our
``on_shutdown`` callbacks. This module layers an explicit asyncio
signal handler on top so:

* Operators get an ``api.shutdown.signal.received`` log the moment the
  signal arrives (uvicorn's own log is delayed until it starts
  cancelling in-flight requests).
* ``AppState`` carries a ``shutdown_requested`` event other subsystems
  can observe (e.g. a long-running reconcile loop can exit early
  instead of waiting for cancellation).

Windows has no POSIX signals; the asyncio proactor event loop raises
``NotImplementedError`` on :meth:`add_signal_handler`. The helper logs
a DEBUG event and returns instead, so the app still boots and uvicorn's
own CTRL+C handling remains in effect.
"""

import asyncio
import signal
import sys
from collections.abc import Callable  # noqa: TC003
from typing import TYPE_CHECKING

from synthorg.observability import get_logger
from synthorg.observability.events.api import (
    API_SHUTDOWN_HANDLER_SKIPPED,
    API_SHUTDOWN_SIGNAL_RECEIVED,
)

if TYPE_CHECKING:
    from synthorg.api.state import AppState

logger = get_logger(__name__)


_POSIX_SIGNALS: tuple[signal.Signals, ...] = (signal.SIGTERM, signal.SIGINT)


def install_shutdown_handlers(app_state: AppState) -> None:
    """Register POSIX ``SIGTERM``/``SIGINT`` handlers on the running loop.

    Idempotent: the shared-app test fixture reuses a single ``AppState``
    across lifespan re-enters. Repeated calls overwrite the handler
    with a fresh closure that captures the same ``app_state``.

    On non-POSIX (Windows dev), logs DEBUG and returns. Uvicorn's
    Windows handler (``KeyboardInterrupt`` catch + CTRL_BREAK_EVENT on
    Win32) is sufficient for dev/test; production deployments are
    Linux containers.
    """
    # ``sys.platform`` narrows to a literal on the current host, so
    # mypy would flag the POSIX branch as unreachable on a Windows
    # development machine (and vice versa).  Read it through a local
    # variable so the runtime check survives type checking on either
    # platform.
    current_platform: str = sys.platform
    if current_platform == "win32":
        logger.debug(
            API_SHUTDOWN_HANDLER_SKIPPED,
            reason="non-posix-platform",
            platform=current_platform,
        )
        return

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop (called from sync context); uvicorn owns
        # signals in that case.  Log so operators see the skip.
        logger.debug(
            API_SHUTDOWN_HANDLER_SKIPPED,
            reason="no-running-loop",
        )
        return

    for sig in _POSIX_SIGNALS:
        try:
            loop.add_signal_handler(
                sig,
                _make_handler(sig, app_state),
            )
        except NotImplementedError:
            # Proactor event loops (ProactorEventLoop on Win pre-3.8
            # subinterpreters, embedded runtimes) raise
            # NotImplementedError.  Keep uvicorn's handler as the
            # safety net.
            logger.debug(
                API_SHUTDOWN_HANDLER_SKIPPED,
                reason="loop-lacks-signal-handler",
                signal=sig.name,
            )
            return


def _make_handler(
    sig: signal.Signals,
    app_state: AppState,
) -> Callable[[], None]:
    """Bind ``sig`` + ``app_state`` into a zero-arg handler closure."""

    def handler() -> None:
        _on_signal(sig, app_state)

    return handler


def _on_signal(sig: signal.Signals, app_state: AppState) -> None:
    """Flag the app for shutdown and log the signal.

    Does NOT call ``loop.stop()`` -- uvicorn's own handler triggers the
    ASGI lifespan shutdown, which runs our ``on_shutdown`` hooks in
    order. Our job here is to make the signal observable to subsystems
    that want to stop early.
    """
    logger.info(
        API_SHUTDOWN_SIGNAL_RECEIVED,
        signal=sig.name,
    )
    event = app_state.shutdown_requested
    if not event.is_set():
        event.set()
