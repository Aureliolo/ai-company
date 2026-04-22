"""Per-operation rate limit guard factory (#1391).

``per_op_rate_limit`` returns a Litestar ``Guard`` that throttles an
endpoint based on a sliding-window bucket.  The guard reads the live
:class:`SlidingWindowStore` and :class:`PerOpRateLimitConfig` from the
Litestar app state (``connection.app.state``), so operator config
overrides take effect without a restart.
"""

import math
from collections.abc import Awaitable, Callable  # noqa: TC003
from typing import Any

from litestar.connection import ASGIConnection  # noqa: TC002
from litestar.handlers.base import BaseRouteHandler  # noqa: TC002

from synthorg.api.errors import PerOperationRateLimitError, ServiceUnavailableError
from synthorg.api.rate_limits._subject import (
    STATE_KEY_CONFIG,
    STATE_KEY_STORE,
    KeyPolicy,
    extract_subject_key,
)
from synthorg.api.rate_limits.config import PerOpRateLimitConfig  # noqa: TC001
from synthorg.api.rate_limits.protocol import SlidingWindowStore  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.api import API_APP_STARTUP, API_GUARD_DENIED

logger = get_logger(__name__)


def per_op_rate_limit(
    operation: str,
    *,
    max_requests: int,
    window_seconds: int,
    key: KeyPolicy = "user_or_ip",
) -> Callable[
    [ASGIConnection[Any, Any, Any, Any], BaseRouteHandler],
    Awaitable[None],
]:
    """Build a Litestar guard that throttles ``operation``.

    Args:
        operation: Stable, human-readable operation name (e.g.
            ``"artifacts.upload"``).  Used as the bucket-key prefix and
            as the override lookup key in
            :class:`PerOpRateLimitConfig.overrides`.
        max_requests: Default maximum hits per window.  Overridden per
            deployment by config.
        window_seconds: Default window length in seconds.
        key: Subject keying policy.  ``user`` requires an authenticated
            subject and falls back to IP.  ``ip`` always uses the IP.
            ``user_or_ip`` uses the user ID when authenticated, otherwise
            the IP -- the right default for most endpoints.

    Returns:
        A Litestar-compatible async guard.

    Raises:
        PerOperationRateLimitError: When the request exceeds the bucket.
    """
    if max_requests <= 0:
        msg = "max_requests must be positive"
        logger.warning(
            API_APP_STARTUP,
            guard="per_op_rate_limit",
            operation=operation,
            max_requests=max_requests,
            window_seconds=window_seconds,
            error=msg,
        )
        raise ValueError(msg)
    if window_seconds <= 0:
        msg = "window_seconds must be positive"
        logger.warning(
            API_APP_STARTUP,
            guard="per_op_rate_limit",
            operation=operation,
            max_requests=max_requests,
            window_seconds=window_seconds,
            error=msg,
        )
        raise ValueError(msg)
    default_max = max_requests
    default_window = window_seconds

    async def _guard(
        connection: ASGIConnection[Any, Any, Any, Any],
        _handler: BaseRouteHandler,
    ) -> None:
        state = connection.app.state
        store: SlidingWindowStore | None = getattr(state, STATE_KEY_STORE, None)
        config: PerOpRateLimitConfig | None = getattr(
            state,
            STATE_KEY_CONFIG,
            None,
        )
        # Master switch: when the operator has explicitly disabled
        # per-op rate limiting the guard is a no-op.
        if config is not None and not config.enabled:
            return
        # Missing store or missing config is a wiring error, NOT an
        # "off" signal.  Fail loud and closed with a 503 so misconfigured
        # deployments do not ship without protection.  A 429 would be
        # semantically wrong here: the request is not rate-limited,
        # the operator forgot to wire the limiter.  503 + no
        # ``Retry-After`` tells clients this is a server-side issue.
        if store is None or config is None:
            logger.error(
                API_APP_STARTUP,
                guard="per_op_rate_limit",
                operation=operation,
                missing_store=store is None,
                missing_config=config is None,
                error=(
                    "per-op rate limiter not wired; refusing request to avoid "
                    "silently unthrottled endpoints"
                ),
            )
            msg = (
                f"Rate limit guard for operation {operation!r} is not wired. "
                "This is a deployment error; see logs for context."
            )
            raise ServiceUnavailableError(msg)
        limit_max, limit_window = config.overrides.get(
            operation,
            (default_max, default_window),
        )
        if limit_max <= 0 or limit_window <= 0:
            # Operator disabled this operation via override.
            return
        subject = extract_subject_key(
            connection,
            key,
            guard_name="per_op_rate_limit",
        )
        bucket_key = f"{operation}:{subject}"
        outcome = await store.acquire(
            bucket_key,
            max_requests=limit_max,
            window_seconds=limit_window,
        )
        if outcome.allowed:
            return
        # Round up so a fractional 0.5s delay surfaces as at least 1s
        # and clients never retry before the bucket actually reopens.
        retry_after_s = (
            math.ceil(outcome.retry_after_seconds)
            if outcome.retry_after_seconds is not None
            else 1
        )
        # Always surface at least 1 second so clients don't hot-loop.
        retry_after_s = max(retry_after_s, 1)
        logger.warning(
            API_GUARD_DENIED,
            guard="per_op_rate_limit",
            operation=operation,
            subject=subject,
            max_requests=limit_max,
            window_seconds=limit_window,
            retry_after=retry_after_s,
        )
        msg = (
            f"Rate limit exceeded for operation {operation!r}. "
            f"Retry after {retry_after_s}s."
        )
        raise PerOperationRateLimitError(msg, retry_after=retry_after_s)

    _guard.__name__ = f"per_op_rate_limit[{operation}]"
    _guard.__qualname__ = _guard.__name__
    return _guard
