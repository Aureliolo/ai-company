"""Per-operation rate limiting (#1391).

Layered on top of the global two-tier limiter (``api/config.py``
``RateLimitConfig``), per-op guards throttle individual expensive
endpoints.  Composition, not replacement: the global tier still fires
first for unauthenticated and authenticated keys; per-op guards add a
narrower bucket keyed by ``(operation, user_or_ip)``.

Pluggable via Protocol + strategy + factory + config discriminator per
CLAUDE.md.  Ships with an ``InMemorySlidingWindowStore`` default;
additional strategies can be added behind the factory when needed.
"""

from synthorg.api.rate_limits.config import PerOpRateLimitConfig
from synthorg.api.rate_limits.factory import build_sliding_window_store
from synthorg.api.rate_limits.guard import per_op_rate_limit
from synthorg.api.rate_limits.in_memory import InMemorySlidingWindowStore
from synthorg.api.rate_limits.protocol import (
    RateLimitOutcome,
    SlidingWindowStore,
)

__all__ = [
    "InMemorySlidingWindowStore",
    "PerOpRateLimitConfig",
    "RateLimitOutcome",
    "SlidingWindowStore",
    "build_sliding_window_store",
    "per_op_rate_limit",
]
