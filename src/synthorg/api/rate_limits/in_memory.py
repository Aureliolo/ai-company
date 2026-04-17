"""In-memory sliding-window rate limiter (#1391).

Each bucket holds a deque of monotonic timestamps.  On each ``acquire``
call, timestamps older than ``window_seconds`` are evicted; if the
remaining count is below ``max_requests``, the new timestamp is appended
and the request is allowed.  Otherwise the oldest remaining timestamp
gives the exact number of seconds the caller must wait.

The store is async-safe via a per-key ``asyncio.Lock``.  Buckets with
no activity for ``max(window_seconds * 2, 60)`` seconds are evicted by
a lightweight sweep on every N-th acquire to bound memory growth.
"""

import asyncio
import time
from collections import deque
from typing import Final

from synthorg.api.rate_limits.protocol import RateLimitOutcome, SlidingWindowStore
from synthorg.observability import get_logger
from synthorg.observability.events.api import API_REQUEST_ERROR

logger = get_logger(__name__)

_GC_EVERY_N_ACQUIRES: Final[int] = 1024


class InMemorySlidingWindowStore(SlidingWindowStore):
    """Process-local sliding-window limiter.

    Not shared across processes -- with multiple Litestar workers, each
    worker maintains an independent bucket.  That is acceptable for
    per-operation throttling where global coordination is not required;
    the global two-tier limiter in ``api/app.py`` handles cross-worker
    coordination separately.

    Wire up a Redis-backed adapter via :func:`build_sliding_window_store`
    when cross-worker fairness becomes a requirement.
    """

    def __init__(self) -> None:
        """Initialise an empty bucket store."""
        self._buckets: dict[str, deque[float]] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._meta_lock: asyncio.Lock = asyncio.Lock()
        self._acquires_since_gc: int = 0

    async def acquire(
        self,
        key: str,
        *,
        max_requests: int,
        window_seconds: int,
    ) -> RateLimitOutcome:
        """Record one hit on ``key`` against the ``max_requests`` budget."""
        if max_requests <= 0:
            msg = "max_requests must be positive"
            raise ValueError(msg)
        if window_seconds <= 0:
            msg = "window_seconds must be positive"
            raise ValueError(msg)

        lock = await self._get_lock(key)
        async with lock:
            now = time.monotonic()
            bucket = self._buckets.setdefault(key, deque())
            cutoff = now - float(window_seconds)
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= max_requests:
                oldest = bucket[0]
                retry_after = max(oldest + float(window_seconds) - now, 0.001)
                return RateLimitOutcome(
                    allowed=False,
                    retry_after_seconds=retry_after,
                    remaining=0,
                )
            bucket.append(now)
            remaining = max(max_requests - len(bucket), 0)
            self._acquires_since_gc += 1

        if self._acquires_since_gc >= _GC_EVERY_N_ACQUIRES:
            await self._gc_cold_buckets(window_seconds=window_seconds)

        return RateLimitOutcome(
            allowed=True,
            retry_after_seconds=None,
            remaining=remaining,
        )

    async def close(self) -> None:
        """Clear all buckets and locks."""
        async with self._meta_lock:
            self._buckets.clear()
            self._locks.clear()
            self._acquires_since_gc = 0

    async def _get_lock(self, key: str) -> asyncio.Lock:
        """Return the per-key lock, creating it under the meta-lock."""
        lock = self._locks.get(key)
        if lock is not None:
            return lock
        async with self._meta_lock:
            lock = self._locks.get(key)
            if lock is None:
                lock = asyncio.Lock()
                self._locks[key] = lock
            return lock

    async def _gc_cold_buckets(self, *, window_seconds: int) -> None:
        """Drop buckets (and locks) that have been empty for twice the window."""
        horizon = max(window_seconds * 2, 60)
        async with self._meta_lock:
            try:
                cutoff = time.monotonic() - float(horizon)
                dead = [
                    k for k, dq in self._buckets.items() if not dq or dq[-1] <= cutoff
                ]
                for key in dead:
                    self._buckets.pop(key, None)
                    # Only drop the lock if no task is holding it -- a
                    # locked entry means an in-flight acquire that must
                    # observe the same lock object.
                    lock = self._locks.get(key)
                    if lock is not None and not lock.locked():
                        self._locks.pop(key, None)
                self._acquires_since_gc = 0
            except Exception as exc:
                # GC is best-effort -- never block acquire progress.
                logger.warning(
                    API_REQUEST_ERROR,
                    error_type="rate_limit_gc_failed",
                    error=str(exc),
                )
