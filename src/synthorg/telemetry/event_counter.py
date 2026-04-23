"""In-memory telemetry event counter.

Process-local rolling buffer of :class:`TelemetryEvent` timestamps +
types.  Implements the
:class:`~synthorg.telemetry.event_counter_protocol.TelemetryEventCounter`
protocol (read surface) and the
:class:`~synthorg.telemetry.event_counter_protocol.TelemetrySubscriber`
protocol (write surface) so it can be registered directly with the
:class:`TelemetryCollector` via ``subscribe()``.

The counter is the single owner of event-count roll-up logic; the
telemetry signal aggregator calls :meth:`summarize` rather than
reimplementing windowed counts and top-type ranking.
"""

import threading
from collections import deque
from typing import TYPE_CHECKING

from synthorg.meta.signal_models import OrgTelemetrySummary
from synthorg.observability import get_logger
from synthorg.observability.events.telemetry import TELEMETRY_COUNTER_EVICTED

if TYPE_CHECKING:
    from datetime import datetime

    from synthorg.telemetry.protocol import TelemetryEvent

logger = get_logger(__name__)

_DEFAULT_MAX_EVENTS = 10_000
"""Default ring-buffer capacity for telemetry events.

Telemetry events fire on deployment lifecycle boundaries + heartbeat;
this covers many weeks of normal traffic.  Durable backends behind
the protocol are the right path for multi-month retention.
"""

_ERROR_EVENT_NAME_HINTS: tuple[str, ...] = (
    ".failed",
    ".error",
    ".denied",
    ".rejected",
)
"""Substring hints used to classify an event type as error-bearing.

Telemetry events carry their severity via the event type name
(``deployment.startup`` vs. ``deployment.report.failed``).  The hint
list lets the counter surface ``error_event_count`` without a
separate enum.  New hints are additive: appending one does not
invalidate existing counts because the whole event buffer is
re-scanned at summarise time.
"""


class InMemoryTelemetryEventCounter:
    """Process-local rolling telemetry-event counter.

    Args:
        max_events: Ring-buffer capacity.  Oldest entries are evicted
            when the buffer is full.
    """

    def __init__(self, *, max_events: int = _DEFAULT_MAX_EVENTS) -> None:
        if max_events < 1:
            msg = f"max_events must be >= 1, got {max_events}"
            raise ValueError(msg)
        self._max_events = max_events
        # Store (timestamp, event_type) tuples to minimise memory.
        self._events: deque[tuple[datetime, str]] = deque(maxlen=max_events)
        # Threading lock because ``on_event`` is synchronous and may
        # be called from any thread the reporter dispatches from.
        self._lock = threading.Lock()

    def on_event(self, event: TelemetryEvent) -> None:
        """Record one telemetry event.

        Synchronous, best-effort; swallows all exceptions except
        ``MemoryError`` / ``RecursionError``.
        """
        try:
            with self._lock:
                evicted = len(self._events) == self._max_events
                self._events.append((event.timestamp, event.event_type))
            if evicted:
                logger.info(
                    TELEMETRY_COUNTER_EVICTED,
                    max_events=self._max_events,
                )
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.exception(
                "telemetry.counter.record_failed",
                event_type=getattr(event, "event_type", "<unknown>"),
            )

    async def summarize(
        self,
        *,
        since: datetime,
        until: datetime,
        max_top: int = 10,
    ) -> OrgTelemetrySummary:
        """Roll recorded events into an :class:`OrgTelemetrySummary`."""
        _validate_window(since, until)
        if max_top < 1:
            msg = f"max_top must be >= 1, got {max_top}"
            raise ValueError(msg)
        with self._lock:
            snapshot = tuple(self._events)
        in_window = [(ts, et) for ts, et in snapshot if since <= ts < until]
        if not in_window:
            return OrgTelemetrySummary()
        type_counts: dict[str, int] = {}
        error_count = 0
        for _ts, event_type in in_window:
            type_counts[event_type] = type_counts.get(event_type, 0) + 1
            if _is_error_event(event_type):
                error_count += 1
        top_types = _rank_top_types(type_counts, max_top=max_top)
        return OrgTelemetrySummary(
            event_count=len(in_window),
            top_event_types=top_types,
            error_event_count=error_count,
        )

    async def count(self) -> int:
        """Return current buffer size (not capacity)."""
        with self._lock:
            return len(self._events)

    async def clear(self) -> None:
        """Drop all stored events."""
        with self._lock:
            self._events.clear()


def _validate_window(since: datetime, until: datetime) -> None:
    """Reject inverted or naive windows before any scan."""
    if since.tzinfo is None or until.tzinfo is None:
        msg = "since/until must be timezone-aware"
        raise ValueError(msg)
    if since >= until:
        msg = (
            f"since ({since.isoformat()}) must be earlier than until "
            f"({until.isoformat()})"
        )
        raise ValueError(msg)


def _is_error_event(event_type: str) -> bool:
    """Return ``True`` when the type name matches an error hint.

    Hints are compared case-insensitively; the event type namespace
    is mixed case in the wild (``TELEMETRY_REPORT_FAILED`` emits
    ``telemetry.report.failed``) and we want the match to be stable.
    """
    lower = event_type.lower()
    return any(hint in lower for hint in _ERROR_EVENT_NAME_HINTS)


def _rank_top_types(
    type_counts: dict[str, int],
    *,
    max_top: int,
) -> tuple[str, ...]:
    """Return the top event-type names by count, alphabetical tie-break."""
    ranked = sorted(type_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return tuple(name for name, _ in ranked[:max_top])


__all__ = [
    "InMemoryTelemetryEventCounter",
]
