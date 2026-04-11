"""Webhook replay protection.

Prevents replay attacks by tracking nonces and validating
timestamps within a configurable window.
"""

from collections import OrderedDict
from collections.abc import Callable  # noqa: TC003

from synthorg.observability import get_logger
from synthorg.observability.events.integrations import WEBHOOK_REPLAY_DETECTED

logger = get_logger(__name__)

_DEFAULT_WINDOW_SECONDS = 300
_DEFAULT_MAX_ENTRIES = 10_000


def _default_clock() -> float:
    """Wall-clock seconds since the Unix epoch.

    Kept out of the ``time`` import so tests can inject a clock
    without patching a module-wide name.
    """
    import time  # noqa: PLC0415

    return time.time()


class ReplayProtector:
    """In-memory nonce + timestamp replay protection.

    Rejects requests with:
    - A timestamp outside the configured window.
    - A previously-seen nonce within the window.

    Nonces are evicted when they expire beyond the window. The
    store is also bounded: once ``max_entries`` is reached, the
    oldest nonces are dropped in insertion order to prevent an
    attacker from exhausting memory with unique nonces.

    Args:
        window_seconds: Maximum clock skew / replay window.
        max_entries: Maximum nonces retained at once.
        clock: Wall-clock source (injectable for deterministic tests).
    """

    def __init__(
        self,
        window_seconds: int = _DEFAULT_WINDOW_SECONDS,
        *,
        max_entries: int = _DEFAULT_MAX_ENTRIES,
        clock: Callable[[], float] = _default_clock,
    ) -> None:
        self._window = window_seconds
        self._max_entries = max_entries
        self._seen: OrderedDict[str, float] = OrderedDict()
        self._clock = clock

    def check(
        self,
        *,
        nonce: str | None,
        timestamp: float | None,
    ) -> bool:
        """Check whether a request is a replay.

        Args:
            nonce: Request nonce (optional).
            timestamp: Request timestamp as Unix epoch seconds.

        Returns:
            ``True`` if the request is safe (not a replay).
            ``False`` if the request should be rejected.
        """
        now = self._clock()

        # Fail closed: when neither a nonce nor a timestamp is supplied
        # the protector has nothing to check against, so accepting the
        # request would silently downgrade replay protection to a
        # no-op. Reject instead -- misconfigured verifiers or missing
        # headers should surface as rejected deliveries.
        if nonce is None and timestamp is None:
            logger.warning(
                WEBHOOK_REPLAY_DETECTED,
                reason="no freshness signal (nonce and timestamp both missing)",
            )
            return False

        if timestamp is not None and abs(now - timestamp) > self._window:
            logger.warning(
                WEBHOOK_REPLAY_DETECTED,
                reason="timestamp outside window",
                skew=abs(now - timestamp),
            )
            return False

        self._evict(now)

        if nonce is not None:
            if nonce in self._seen:
                logger.warning(
                    WEBHOOK_REPLAY_DETECTED,
                    reason="duplicate nonce",
                    nonce=nonce[:16],
                )
                return False
            self._seen[nonce] = now
            # Bound the store: evict oldest insertion(s) if over limit.
            while len(self._seen) > self._max_entries:
                self._seen.popitem(last=False)

        return True

    def _evict(self, now: float) -> None:
        """Remove nonces older than the window."""
        cutoff = now - self._window
        # OrderedDict preserves insertion order; stop at the first
        # non-expired entry since later insertions are always newer.
        while self._seen:
            nonce, ts = next(iter(self._seen.items()))
            if ts >= cutoff:
                break
            del self._seen[nonce]
