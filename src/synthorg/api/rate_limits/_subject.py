"""Shared subject-identity resolution for rate-limit guards (#1489, #1391).

Both the sliding-window ``per_op_rate_limit`` guard and the inflight
``PerOpConcurrencyMiddleware`` must bucket requests by the same
"real client" identifier -- otherwise a malicious caller could hit
the rate-limiter under user-keying but escape the concurrency cap by
spoofing the request shape, or vice versa.  Factoring the helpers out
of ``guard.py`` makes the contract explicit and keeps the two code
paths in lockstep.
"""

import ipaddress
from typing import Any, Final, Literal

from litestar.connection import ASGIConnection  # noqa: TC002

from synthorg.observability import get_logger
from synthorg.observability.events.api import API_GUARD_DEGRADED_AUTH

logger = get_logger(__name__)

KeyPolicy = Literal["user", "ip", "user_or_ip"]

# AppState keys -- wired in ``api/app.py`` startup.
STATE_KEY_STORE: Final[str] = "per_op_rate_limit_store"
STATE_KEY_CONFIG: Final[str] = "per_op_rate_limit_config"
STATE_KEY_INFLIGHT_STORE: Final[str] = "per_op_inflight_store"
STATE_KEY_INFLIGHT_CONFIG: Final[str] = "per_op_inflight_config"
# Trusted-proxy set (frozenset[str]) used to decide whether to read
# X-Forwarded-For; mirrors the global limiter's behaviour so the per-op
# guards pick the same "real client IP" and cannot be bypassed by
# untrusted callers spoofing the forwarded header.
STATE_KEY_TRUSTED_PROXIES: Final[str] = "per_op_trusted_proxies"
# Trusted-proxy-normalised client IP key -- stashed on the ASGI scope
# by any middleware that has already resolved the forwarded IP.  The
# helpers read this first and only walk X-Forwarded-For themselves when
# the immediate peer is in ``per_op_trusted_proxies``.
SCOPE_KEY_TRUSTED_IP: Final[str] = "trusted_client_ip"


def extract_subject_key(
    connection: ASGIConnection[Any, Any, Any, Any],
    policy: KeyPolicy,
    *,
    guard_name: str,
) -> str:
    """Resolve the subject identifier for a given key policy.

    Args:
        connection: The incoming request's ASGI connection.
        policy: Which identity to bucket on (``user``, ``ip``, or
            ``user_or_ip``).
        guard_name: Name of the caller (``"per_op_rate_limit"`` or
            ``"per_op_concurrency"``) for telemetry attribution when
            the ``user`` policy falls back to IP.

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
                guard=guard_name,
                note="user_key_missing_user_id_falling_back_to_ip",
            )
            return f"ip:{client_ip(connection)}"
        return f"user:{user_id}"
    if policy == "ip":
        return f"ip:{client_ip(connection)}"
    if user_id is not None:
        return f"user:{user_id}"
    return f"ip:{client_ip(connection)}"


def _peer_ip(connection: ASGIConnection[Any, Any, Any, Any]) -> str | None:
    """Return the immediate peer IP from the ASGI scope."""
    client = connection.scope.get("client")
    if isinstance(client, (tuple, list)) and client:
        return str(client[0])
    return None


def client_ip(connection: ASGIConnection[Any, Any, Any, Any]) -> str:
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
