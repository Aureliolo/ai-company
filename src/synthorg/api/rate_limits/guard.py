"""Per-operation rate limit guard factory (#1391).

``per_op_rate_limit`` returns a Litestar ``Guard`` that throttles an
endpoint based on a sliding-window bucket.  The guard reads the live
:class:`SlidingWindowStore` and :class:`PerOpRateLimitConfig` from the
Litestar app state (``connection.app.state``), so operator config
overrides take effect without a restart.
"""

from collections.abc import Awaitable, Callable  # noqa: TC003
from typing import Any, Final, Literal

from litestar.connection import ASGIConnection  # noqa: TC002
from litestar.handlers.base import BaseRouteHandler  # noqa: TC002

from synthorg.api.errors import PerOperationRateLimitError
from synthorg.api.rate_limits.config import PerOpRateLimitConfig  # noqa: TC001
from synthorg.api.rate_limits.protocol import SlidingWindowStore  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.api import API_GUARD_DENIED

logger = get_logger(__name__)

KeyPolicy = Literal["user", "ip", "user_or_ip"]

# AppState keys -- wired in ``api/app.py`` startup.
STATE_KEY_STORE: Final[str] = "per_op_rate_limit_store"
STATE_KEY_CONFIG: Final[str] = "per_op_rate_limit_config"


def _extract_subject_key(
    connection: ASGIConnection[Any, Any, Any, Any],
    policy: KeyPolicy,
) -> str:
    """Resolve the subject identifier for a given key policy.

    Args:
        connection: The incoming request's ASGI connection.
        policy: Which identity to bucket on (``user``, ``ip``, or
            ``user_or_ip``).

    Returns:
        A stable string identifier prefixed with ``"user:"`` or
        ``"ip:"`` so the two namespaces never collide.
    """
    user = connection.scope.get("user")
    user_id = getattr(user, "user_id", None) if user is not None else None
    if policy == "user":
        if user_id is None:
            # Fall back to IP so anonymous calls still get throttled
            # rather than bypassing the limiter entirely.
            return f"ip:{_client_ip(connection)}"
        return f"user:{user_id}"
    if policy == "ip":
        return f"ip:{_client_ip(connection)}"
    if user_id is not None:
        return f"user:{user_id}"
    return f"ip:{_client_ip(connection)}"


def _client_ip(connection: ASGIConnection[Any, Any, Any, Any]) -> str:
    """Extract a best-effort client IP from the connection.

    Uses the ``X-Forwarded-For`` header when present (populated by the
    global rate limiter's proxy-aware extractor at the ASGI scope level)
    and falls back to the raw client host.  Returning ``"unknown"``
    keeps the guard from blowing up when the connection has no client
    metadata (rare, typically test fixtures).
    """
    forwarded = connection.headers.get("x-forwarded-for", "")
    if forwarded:
        first = forwarded.split(",", 1)[0].strip()
        if first:
            return first
    client = connection.scope.get("client")
    if isinstance(client, (tuple, list)) and client:
        return str(client[0])
    return "unknown"


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
        raise ValueError(msg)
    if window_seconds <= 0:
        msg = "window_seconds must be positive"
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
        if store is None or config is None or not config.enabled:
            return
        limit_max, limit_window = config.overrides.get(
            operation,
            (default_max, default_window),
        )
        if limit_max <= 0 or limit_window <= 0:
            # Operator disabled this operation via override.
            return
        subject = _extract_subject_key(connection, key)
        bucket_key = f"{operation}:{subject}"
        outcome = await store.acquire(
            bucket_key,
            max_requests=limit_max,
            window_seconds=limit_window,
        )
        if outcome.allowed:
            return
        retry_after_s = (
            int(outcome.retry_after_seconds)
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
