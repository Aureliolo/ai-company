"""Cancellation token for fine-tuning pipeline stages.

Provides a cooperative cancellation mechanism: the orchestrator
sets the token, and each stage checks it between batches.
"""

import threading

from synthorg.memory.errors import FineTuneCancelledError


class CancellationToken:
    """Cooperative cancellation signal for pipeline stages.

    Thread-safe via ``threading.Event``.  The orchestrator calls
    ``cancel()`` from the event loop; stage functions call ``check()``
    between batches, potentially from worker threads (via
    ``asyncio.to_thread``).
    """

    __slots__ = ("_event",)

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        """Signal cancellation."""
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        """Whether cancellation has been requested."""
        return self._event.is_set()

    def check(self) -> None:
        """Raise ``FineTuneCancelledError`` if cancelled.

        Call this between batches in each pipeline stage.

        Raises:
            FineTuneCancelledError: If cancellation was requested.
        """
        if self._event.is_set():
            msg = "Fine-tuning pipeline run was cancelled"
            raise FineTuneCancelledError(msg)
