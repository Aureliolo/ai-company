"""Per-operation rate limit guard factory (#1391).

``per_op_rate_limit`` returns a Litestar ``Guard`` that throttles an
endpoint based on a sliding-window bucket.  The guard reads the live
:class:`SlidingWindowStore` and :class:`PerOpRateLimitConfig` from the
Litestar app state (``connection.app.state``), so operator config
overrides take effect without a restart.
"""

import ipaddress
import math
from collections.abc import Awaitable, Callable  # noqa: TC003
from typing import Any, Final, Literal

from litestar.connection import ASGIConnection  # noqa: TC002
from litestar.handlers.base import BaseRouteHandler  # noqa: TC002

from synthorg.api.errors import PerOperationRateLimitError, ServiceUnavailableError
from synthorg.api.rate_limits.config import PerOpRateLimitConfig  # noqa: TC001
from synthorg.api.rate_limits.protocol import SlidingWindowStore  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.api import (
    API_APP_STARTUP,
    API_GUARD_DEGRADED_AUTH,
    API_GUARD_DENIED,
)

logger = get_logger(__name__)

KeyPolicy = Literal["user", "ip", "user_or_ip"]

# AppState keys -- wired in ``api/app.py`` startup.
STATE_KEY_STORE: Final[str] = "per_op_rate_limit_store"
STATE_KEY_CONFIG: Final[str] = "per_op_rate_limit_config"
# Trusted-proxy set (frozenset[str]) used to decide whether to read
# X-Forwarded-For; mirrors the global limiter's behaviour so the per-op
# guard picks the same "real client IP" and cannot be bypassed by
# untrusted callers spoofing the forwarded header.
STATE_KEY_TRUSTED_PROXIES: Final[str] = "per_op_trusted_proxies"
# Trusted-proxy-normalised client IP key -- stashed on the ASGI scope
# by any middleware that has already resolved the forwarded IP.  The
# guard reads this first and only walks X-Forwarded-For itself when
# the immediate peer is in ``per_op_trusted_proxies``.
SCOPE_KEY_TRUSTED_IP: Final[str] = "trusted_client_ip"


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
            # Authenticated request expected but no user populated.
            # Fall back to IP so anonymous calls still get throttled
            # rather than bypassing the limiter entirely, but log so
            # operators notice when auth middleware silently strips
            # the user claim.
            logger.warning(
                API_GUARD_DEGRADED_AUTH,
                guard="per_op_rate_limit",
                note="user_key_missing_user_id_falling_back_to_ip",
            )
            return f"ip:{_client_ip(connection)}"
        return f"user:{user_id}"
    if policy == "ip":
        return f"ip:{_client_ip(connection)}"
    if user_id is not None:
        return f"user:{user_id}"
    return f"ip:{_client_ip(connection)}"


def _peer_ip(connection: ASGIConnection[Any, Any, Any, Any]) -> str | None:
    """Return the immediate peer IP from the ASGI scope."""
    client = connection.scope.get("client")
    if isinstance(client, (tuple, list)) and client:
        return str(client[0])
    return None


def _client_ip(connection: ASGIConnection[Any, Any, Any, Any]) -> str:
    """Extract a proxy-aware best-effort client IP from the connection.

    Resolution order:

    1. ``scope["trusted_client_ip"]`` if a middleware already resolved it.
    2. If the immediate peer is in ``per_op_trusted_proxies`` (state),
       walk ``X-Forwarded-For`` right-to-left and return the first hop
       outside the trusted set.  This matches the global limiter's
       ``_build_unauth_identifier`` semantics so both tiers pick the
       same "real" client identifier.
    3. Otherwise return the immediate peer IP -- the raw
       ``X-Forwarded-For`` header is **never** trusted from untrusted
       peers (would let any caller spoof identities to bypass
       ip/user_or_ip throttles).

    ``"unknown"`` is returned when the connection has no client
    metadata at all (rare, typically test fixtures).
    """
    trusted = connection.scope.get(SCOPE_KEY_TRUSTED_IP)
    if isinstance(trusted, str) and trusted:
        return trusted
    peer = _peer_ip(connection)
    trusted_networks = _trusted_networks(connection)
    if peer is not None and _ip_in_networks(peer, trusted_networks):
        forwarded = connection.headers.get("x-forwarded-for", "")
        if forwarded:
            hops = [h.strip() for h in forwarded.split(",") if h.strip()]
            for hop in reversed(hops):
                if not _ip_in_networks(hop, trusted_networks):
                    return hop
    return peer or "unknown"


def _trusted_networks(
    connection: ASGIConnection[Any, Any, Any, Any],
) -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
    """Read and parse the trusted-proxy state into IP networks.

    ``per_op_trusted_proxies`` is seeded as a ``frozenset[str]`` at app
    startup (raw strings from the config).  Parse each entry into an
    ``ip_network`` object so both bare IPs (``"10.0.0.1"``) and CIDR
    ranges (``"10.0.0.0/8"``) match correctly; malformed entries are
    skipped (logged by config validation at ingest time, not here).
    """
    raw: frozenset[str] = getattr(
        connection.app.state,
        STATE_KEY_TRUSTED_PROXIES,
        frozenset(),
    )
    parsed: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for entry in raw:
        try:
            parsed.append(ipaddress.ip_network(entry, strict=False))
        except ValueError:
            continue
    return tuple(parsed)


def _ip_in_networks(
    ip_str: str,
    networks: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...],
) -> bool:
    """Return True when ``ip_str`` is inside any of ``networks``."""
    if not networks:
        return False
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return any(addr in net for net in networks)


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
        subject = _extract_subject_key(connection, key)
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
