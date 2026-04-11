"""Webhook replay protection.

Prevents replay attacks by tracking nonces and validating
timestamps within a configurable window.
"""

import time

from synthorg.observability import get_logger
from synthorg.observability.events.integrations import WEBHOOK_REPLAY_DETECTED

logger = get_logger(__name__)


class ReplayProtector:
    """In-memory nonce + timestamp replay protection.

    Rejects requests with:
    - A timestamp outside the configured window.
    - A previously-seen nonce within the window.

    Nonces are evicted when they expire beyond the window.

    Args:
        window_seconds: Maximum clock skew / replay window.
    """

    def __init__(self, window_seconds: int = 300) -> None:
        self._window = window_seconds
        self._seen: dict[str, float] = {}

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
        now = time.time()

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

        return True

    def _evict(self, now: float) -> None:
        """Remove expired nonces."""
        cutoff = now - self._window
        expired = [k for k, ts in self._seen.items() if ts < cutoff]
        for key in expired:
            del self._seen[key]
