"""Factory for per-operation inflight-store strategies."""

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
    """
    if config.backend == "memory":
        return InMemoryInflightStore()
    # Defensive: ``config.backend`` is a ``Literal["memory"]`` union
    # today and the settings-enum is restricted to ``("memory",)``,
    # so reaching this branch requires either a bypass of Pydantic
    # validation or a new backend landed without its factory entry.
    # Fail loud so the drift is obvious rather than silently
    # falling through to an in-memory backend under a different name.
    msg = f"Unknown per-op inflight backend: {config.backend!r}"  # type: ignore[unreachable]
    logger.error(API_APP_STARTUP, backend=config.backend, error="unknown_backend")
    raise ValueError(msg)
