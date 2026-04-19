"""Middleware factory helpers for the Litestar application.

Builds the rate-limit + auth + CSRF middleware stack and the client
identifier extractors the rate-limit tiers use.
"""

from collections.abc import Callable  # noqa: TC003
from typing import TYPE_CHECKING, Any

from litestar import Request  # noqa: TC002
from litestar.middleware.rate_limit import (
    RateLimitConfig as LitestarRateLimitConfig,
)
from litestar.middleware.rate_limit import (
    get_remote_address,
)

from synthorg.api.auth.csrf import create_csrf_middleware_class
from synthorg.api.auth.middleware import create_auth_middleware_class
from synthorg.api.middleware import RequestLoggingMiddleware
from synthorg.observability import get_logger
from synthorg.observability.events.api import API_NETWORK_EXPOSURE_WARNING

if TYPE_CHECKING:
    from litestar.types import Middleware

    from synthorg.api.auth.config import AuthConfig
    from synthorg.api.config import ApiConfig

logger = get_logger(__name__)


def _build_unauth_identifier(
    trusted: frozenset[str],
) -> Callable[[Request[Any, Any, Any]], str]:
    """Build a proxy-aware client IP extractor for the unauth tier.

    When ``trusted_proxies`` is configured, extracts the real client
    IP from the ``X-Forwarded-For`` header (rightmost untrusted hop).
    Without trusted proxies, falls back to ``request.client.host``.

    Args:
        trusted: Frozen set of trusted proxy IPs/CIDRs.

    Returns:
        Callable that extracts a rate-limit key from a request.
    """
    if not trusted:
        return get_remote_address

    def _extract_forwarded_ip(
        request: Request[Any, Any, Any],
    ) -> str:
        # Only trust X-Forwarded-For when the immediate peer is a
        # known proxy. Otherwise any client can spoof the header.
        peer_ip = get_remote_address(request)
        if peer_ip not in trusted:
            return peer_ip
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            # X-Forwarded-For: client, proxy1, proxy2
            # Walk from the right, skip trusted proxies.
            hops = [h.strip() for h in forwarded.split(",")]
            for hop in reversed(hops):
                if hop not in trusted:
                    return hop
        return peer_ip

    return _extract_forwarded_ip


def _auth_identifier_for_request(
    request: Request[Any, Any, Any],
) -> str:
    """Return the authenticated user's ID as the rate limit key.

    Falls back to client IP when the user is not set in scope
    (e.g. auth-excluded paths that are not excluded from the
    auth rate limiter).

    Args:
        request: The incoming request.

    Returns:
        User ID string or client IP as fallback.
    """
    user = request.scope.get("user")
    if user is not None and hasattr(user, "user_id"):
        return str(user.user_id)
    return get_remote_address(request)


def _throttle_when_anonymous(
    request: Request[Any, Any, Any],
) -> bool:
    """Throttle-gate for the anonymous tier.

    The auth middleware runs before the rate-limit middleware (see
    middleware order at the bottom of :func:`build_middleware`), so
    ``scope["user"]`` is authoritatively populated -- either the real
    ``AuthenticatedUser`` after JWT/API-key verification, or ``None``
    for auth-excluded paths (``/auth/login``, ``/auth/setup`` etc.)
    which the auth middleware skips.  A forged session cookie cannot
    bypass this check: if the JWT didn't verify, auth either raised
    401 before we got here or left ``user`` unset.

    Returns ``True`` when the request should count against the
    anonymous bucket, ``False`` when the per-user (auth) tier should
    handle it instead.
    """
    return request.scope.get("user") is None


def _throttle_when_authenticated(
    request: Request[Any, Any, Any],
) -> bool:
    """Throttle-gate for the authenticated tier (per user).

    Mirror of :func:`_throttle_when_anonymous`.  Ensures anonymous
    traffic on auth-excluded paths is counted by the anonymous tier
    only, not double-counted under its fallback IP identifier.
    """
    return request.scope.get("user") is not None


def _build_auth_exclude_paths(
    auth: AuthConfig,
    prefix: str,
    ws_path: str,
    *,
    a2a_enabled: bool = False,
) -> tuple[str, ...]:
    """Compute auth middleware exclude paths with fail-safe defaults."""
    setup_status_path = f"^{prefix}/setup/status$"
    metrics_path = f"^{prefix}/metrics$"
    # Logout must always bypass auth so clients can recover from
    # stale cookie state (an app-version upgrade invalidates the
    # session without giving the client a way to clear it).  Kept
    # as a fail-safe even when operators override
    # ``auth.exclude_paths`` with a custom list.
    logout_path = f"^{prefix}/auth/logout$"
    # The OAuth provider redirects the user's browser here without a
    # session cookie, so the global auth middleware has to let it
    # through. CSRF protection is handled by the state token the
    # callback validates against the oauth_states repo.
    oauth_callback_path = f"^{prefix}/oauth/callback$"
    exclude_paths = (
        auth.exclude_paths
        if auth.exclude_paths is not None
        else (
            f"^{prefix}/health$",
            metrics_path,
            "^/docs",
            "^/api$",
            f"^{prefix}/auth/setup$",
            f"^{prefix}/auth/login$",
            logout_path,
            setup_status_path,
            oauth_callback_path,
        )
    )
    if metrics_path not in exclude_paths:
        exclude_paths = (*exclude_paths, metrics_path)
    if setup_status_path not in exclude_paths:
        exclude_paths = (*exclude_paths, setup_status_path)
    if logout_path not in exclude_paths:
        exclude_paths = (*exclude_paths, logout_path)
    if ws_path not in exclude_paths:
        exclude_paths = (*exclude_paths, ws_path)
    if oauth_callback_path not in exclude_paths:
        exclude_paths = (*exclude_paths, oauth_callback_path)
    if a2a_enabled:
        a2a_gateway_path = f"^{prefix}/a2a"
        well_known_path = r"^/\.well-known"
        if a2a_gateway_path not in exclude_paths:
            exclude_paths = (*exclude_paths, a2a_gateway_path)
        if well_known_path not in exclude_paths:
            exclude_paths = (*exclude_paths, well_known_path)
    return exclude_paths


def _build_middleware(
    api_config: ApiConfig,
    *,
    a2a_enabled: bool = False,
) -> list[Middleware]:
    """Build the middleware stack from configuration.

    Three rate-limit tiers surround the auth middleware:

    1. **IP floor** (outermost) -- keyed by client IP, high budget,
       un-gated.  Counts every request that reaches the app, including
       ones the auth middleware will reject with 401.  Protects
       against floods of forged-token traffic on protected endpoints.
    2. Auth middleware -- populates ``scope["user"]``.
    3. CSRF middleware -- double-submit validation for cookie
       sessions (exempt login/setup/logout/health).
    4. **Unauth tier** -- keyed by client IP, low budget, fires only
       when ``scope["user"]`` is ``None`` (aggressive cap on
       brute-force against login/setup).
    5. Request logging.
    6. **Auth tier** (innermost) -- keyed by user ID, high budget,
       fires only when ``scope["user"]`` is set.  Prevents a single
       authenticated user from abusing the API.

    Auth runs before both user-gated tiers so ``scope["user"]`` is
    authoritatively populated for the ``check_throttle_handler``
    branch: the unauth tier never double-counts authenticated
    parallel flows (the original 429-storm on the setup wizard) and
    the auth tier never mis-counts anonymous traffic.  The IP floor
    runs before auth so invalid-auth floods still hit a rate cap.

    When ``trusted_proxies`` is configured, IP-based tiers read
    ``X-Forwarded-For`` to extract the real client IP. Without it,
    all clients behind a proxy share one IP-based rate limit bucket.
    """
    rl = api_config.rate_limit
    prefix = api_config.api_prefix
    ws_path = f"^{prefix}/ws$"
    trusted = frozenset(api_config.server.trusted_proxies)

    if not trusted and api_config.server.host not in ("127.0.0.1", "localhost", "::1"):
        logger.warning(
            API_NETWORK_EXPOSURE_WARNING,
            note=(
                "No trusted_proxies configured. If this server is behind "
                "a reverse proxy or load balancer, all proxied clients "
                "will share a single unauth rate-limit bucket. Set "
                "api.server.trusted_proxies to the proxy IPs."
            ),
        )

    rl_exclude = list(rl.exclude_paths)
    if ws_path not in rl_exclude:
        rl_exclude.append(ws_path)

    unauth_identifier = _build_unauth_identifier(trusted)
    # Un-gated per-IP floor.  Runs outermost so every request is
    # counted, including ones the auth middleware will reject with
    # 401 -- otherwise an attacker could flood protected routes with
    # forged tokens and burn auth-verification cycles without ever
    # tripping a rate cap (the user-gated unauth tier below never
    # sees auth-rejected traffic because auth runs after the floor
    # but before the user-gated tiers).
    ip_floor_rate_limit = LitestarRateLimitConfig(
        rate_limit=(rl.time_unit, rl.floor_max_requests),  # type: ignore[arg-type]
        exclude=rl_exclude,
        identifier_for_request=unauth_identifier,
        store="rate_limit_floor",
    )
    unauth_rate_limit = LitestarRateLimitConfig(
        rate_limit=(rl.time_unit, rl.unauth_max_requests),  # type: ignore[arg-type]
        exclude=rl_exclude,
        identifier_for_request=unauth_identifier,
        # Only throttle requests without an authenticated user.  The
        # auth middleware is ordered before this tier (see the return
        # at the end of this function), so ``scope["user"]`` is
        # either a verified ``AuthenticatedUser`` or ``None`` for
        # auth-excluded paths -- a forged session cookie cannot bypass
        # this check.  Without the gate, every authenticated request
        # would count against the 20/min/IP cap and parallel dashboard
        # flows (e.g. setup wizard probing N presets) would hit spurious
        # 429s.
        check_throttle_handler=_throttle_when_anonymous,
        store="rate_limit_unauth",
    )
    auth_rate_limit = LitestarRateLimitConfig(
        rate_limit=(rl.time_unit, rl.auth_max_requests),  # type: ignore[arg-type]
        exclude=rl_exclude,
        identifier_for_request=_auth_identifier_for_request,
        check_throttle_handler=_throttle_when_authenticated,
        store="rate_limit_auth",
    )

    exclude_paths = _build_auth_exclude_paths(
        api_config.auth,
        prefix,
        ws_path,
        a2a_enabled=a2a_enabled,
    )
    auth = api_config.auth.model_copy(
        update={"exclude_paths": exclude_paths},
    )
    auth_middleware = create_auth_middleware_class(auth)

    # CSRF middleware: exempt login/setup (they set the cookie, client
    # cannot carry a CSRF token on the first request), logout (clients
    # may need to clear a stale session whose CSRF cookie was lost --
    # e.g. on app version upgrade; CSRF-protecting logout is low value
    # since forcing a logout is a nuisance, not a compromise), and
    # health.
    csrf_exempt = frozenset(
        {
            f"{prefix}/auth/login",
            f"{prefix}/auth/setup",
            f"{prefix}/auth/logout",
            f"{prefix}/health",
        }
    )
    csrf_middleware = create_csrf_middleware_class(
        auth,
        exempt_paths=csrf_exempt,
    )

    # Middleware order (outside-in, i.e. request flow):
    #   1. ip_floor_rate_limit -- un-gated IP cap; counts every request,
    #                             including ones auth rejects with 401
    #   2. auth_middleware     -- resolves identity, populates scope["user"]
    #   3. csrf_middleware     -- validates double-submit for cookie sessions
    #   4. unauth_rate_limit   -- 20/min/IP for requests where user is None
    #   5. RequestLoggingMiddleware
    #   6. auth_rate_limit     -- per-user cap for authenticated requests
    # The IP floor runs before auth so invalid-auth floods on
    # protected routes still hit a rate cap.  Auth runs before both
    # user-gated tiers so they can branch on scope["user"]
    # deterministically via check_throttle_handler.
    return [
        ip_floor_rate_limit.middleware,
        auth_middleware,
        csrf_middleware,
        unauth_rate_limit.middleware,
        RequestLoggingMiddleware,
        auth_rate_limit.middleware,
    ]
