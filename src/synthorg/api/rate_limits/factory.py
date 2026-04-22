"""Factory for sliding-window store strategies."""

from synthorg.api.rate_limits.config import PerOpRateLimitConfig  # noqa: TC001
from synthorg.api.rate_limits.in_memory import InMemorySlidingWindowStore
from synthorg.api.rate_limits.protocol import SlidingWindowStore  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.api import API_APP_STARTUP

logger = get_logger(__name__)


def build_sliding_window_store(
    config: PerOpRateLimitConfig,
) -> SlidingWindowStore:
    """Construct the configured :class:`SlidingWindowStore`.

    Args:
        config: Per-op rate limit configuration.

    Returns:
        A concrete :class:`SlidingWindowStore` implementation.
    """
    if config.backend == "memory":
        return InMemorySlidingWindowStore()
    # Defensive: the Literal union is exhaustive today, but any future
    # backend value must be explicitly handled here before landing.
    msg = f"Unknown per-op rate limit backend: {config.backend!r}"  # type: ignore[unreachable]
    logger.error(API_APP_STARTUP, backend=config.backend, error="unknown_backend")
    raise ValueError(msg)
