"""Factory for per-operation inflight-store strategies (#1489, SEC-2)."""

from synthorg.api.rate_limits.in_memory_inflight import InMemoryInflightStore
from synthorg.api.rate_limits.inflight_config import (
    PerOpConcurrencyConfig,  # noqa: TC001
)
from synthorg.api.rate_limits.inflight_protocol import InflightStore  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.api import API_APP_STARTUP

logger = get_logger(__name__)


def build_inflight_store(config: PerOpConcurrencyConfig) -> InflightStore:
    """Construct the configured :class:`InflightStore`.

    Args:
        config: Per-op concurrency configuration.

    Returns:
        A concrete :class:`InflightStore` implementation.

    Raises:
        NotImplementedError: ``config.backend`` selects a backend that
            has not been implemented yet (currently ``redis``).
    """
    if config.backend == "memory":
        return InMemoryInflightStore()
    if config.backend == "redis":
        msg = (
            "Redis-backed per-op inflight limiter is not implemented. "
            "Use backend='memory' or contribute a Redis adapter."
        )
        logger.warning(
            API_APP_STARTUP,
            backend=config.backend,
            error="redis_inflight_backend_not_implemented",
        )
        raise NotImplementedError(msg)
    # Defensive: the Literal union is exhaustive today, but any future
    # backend value must be explicitly handled here before landing.
    msg = f"Unknown per-op inflight backend: {config.backend!r}"  # type: ignore[unreachable]
    logger.error(API_APP_STARTUP, backend=config.backend, error="unknown_backend")
    raise ValueError(msg)
