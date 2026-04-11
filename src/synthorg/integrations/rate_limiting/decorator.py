"""Tool-side rate limiting decorator.

Applies per-connection rate limits to tool implementations using
the existing ``RateLimiter`` from the provider resilience layer.
"""

import functools
from collections.abc import Callable, Coroutine  # noqa: TC003
from typing import Any, TypeVar

from synthorg.core.resilience_config import RateLimiterConfig
from synthorg.integrations.errors import ConnectionRateLimitError
from synthorg.observability import get_logger
from synthorg.observability.events.integrations import (
    TOOL_RATE_LIMIT_ACQUIRED,
    TOOL_RATE_LIMIT_HIT,
)
from synthorg.providers.resilience.rate_limiter import RateLimiter

logger = get_logger(__name__)

T = TypeVar("T")

_limiters: dict[str, RateLimiter] = {}


def _get_or_create_limiter(
    connection_name: str,
    config: RateLimiterConfig,
) -> RateLimiter:
    """Get or create a rate limiter for a connection."""
    if connection_name not in _limiters:
        _limiters[connection_name] = RateLimiter(
            config,
            provider_name=f"connection:{connection_name}",
        )
    return _limiters[connection_name]


def with_connection_rate_limit(
    connection_name: str,
    *,
    config: RateLimiterConfig | None = None,
) -> Callable[
    [Callable[..., Coroutine[Any, Any, T]]],
    Callable[..., Coroutine[Any, Any, T]],
]:
    """Decorator that applies connection-level rate limiting to a tool.

    Wraps an async tool method with ``RateLimiter.acquire()`` /
    ``release()`` calls using the connection's configured rate limit.

    Args:
        connection_name: Connection name to rate-limit by.
        config: Rate limiter config override.  If ``None``, uses a
            default of 60 RPM / 0 concurrency.

    Returns:
        A decorator that wraps the async function.

    Example::

        @with_connection_rate_limit("github")
        async def fetch_github_pr(self, repo: str) -> str: ...
    """
    effective_config = config or RateLimiterConfig(
        max_requests_per_minute=60,
    )

    def decorator(
        fn: Callable[..., Coroutine[Any, Any, T]],
    ) -> Callable[..., Coroutine[Any, Any, T]]:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            limiter = _get_or_create_limiter(
                connection_name,
                effective_config,
            )
            if not limiter.is_enabled:
                return await fn(*args, **kwargs)

            acquired = await limiter.acquire()
            if not acquired:
                logger.warning(
                    TOOL_RATE_LIMIT_HIT,
                    connection_name=connection_name,
                )
                msg = f"Rate limit exceeded for connection '{connection_name}'"
                raise ConnectionRateLimitError(msg)

            logger.debug(
                TOOL_RATE_LIMIT_ACQUIRED,
                connection_name=connection_name,
            )
            try:
                return await fn(*args, **kwargs)
            finally:
                limiter.release()

        return wrapper

    return decorator
