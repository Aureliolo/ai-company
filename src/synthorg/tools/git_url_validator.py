"""Git clone URL validation — SSRF prevention with DNS resolution.

Validates clone URLs against allowed schemes and performs hostname/IP
validation to prevent Server-Side Request Forgery (SSRF) attacks via
``git clone``.  All resolved IPs must be public; private, loopback,
and link-local addresses are blocked by default.  A configurable
hostname allowlist lets legitimate internal Git servers bypass the
private-IP check.
"""

import asyncio
import ipaddress
from typing import Final
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field

from synthorg.observability import get_logger
from synthorg.observability.events.git import (
    GIT_CLONE_DNS_FAILED,
    GIT_CLONE_SSRF_BLOCKED,
)

logger = get_logger(__name__)

# ── Constants ────────────────────────────────────────────────────

_ALLOWED_CLONE_SCHEMES: Final[tuple[str, ...]] = (
    "https://",
    "ssh://",
)

_BLOCKED_NETWORKS: Final[tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]] = (
    ipaddress.IPv4Network("127.0.0.0/8"),
    ipaddress.IPv4Network("10.0.0.0/8"),
    ipaddress.IPv4Network("172.16.0.0/12"),
    ipaddress.IPv4Network("192.168.0.0/16"),
    ipaddress.IPv4Network("169.254.0.0/16"),
    ipaddress.IPv4Network("0.0.0.0/8"),
    ipaddress.IPv6Network("::1/128"),
    ipaddress.IPv6Network("fe80::/10"),
    ipaddress.IPv6Network("fc00::/7"),
    ipaddress.IPv6Network("::/128"),
)


# ── Network policy model ─────────────────────────────────────────


class GitCloneNetworkPolicy(BaseModel):
    """Network policy for git clone SSRF prevention.

    Controls which hosts are allowed as clone targets.  By default,
    all public hosts are permitted while private, loopback, and
    link-local addresses are blocked.  Entries in
    ``hostname_allowlist`` bypass the private-IP check for legitimate
    internal Git servers.

    Attributes:
        hostname_allowlist: Hostnames that bypass the private-IP
            check (case-insensitive matching).
        block_private_ips: Master switch for private IP blocking.
        dns_resolution_timeout: Timeout in seconds for async DNS
            resolution.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    hostname_allowlist: tuple[str, ...] = Field(
        default=(),
        description="Hostnames that bypass the private-IP check",
    )
    block_private_ips: bool = Field(
        default=True,
        description="Master switch for private IP blocking",
    )
    dns_resolution_timeout: float = Field(
        default=5.0,
        gt=0,
        le=30.0,
        description="Timeout in seconds for DNS resolution",
    )


# ── Helpers ──────────────────────────────────────────────────────


def _is_blocked_ip(addr: str) -> bool:
    """Check whether an IP address falls within a blocked network.

    Handles IPv6-mapped IPv4 addresses (e.g. ``::ffff:127.0.0.1``)
    by extracting the mapped IPv4 address for validation.

    Args:
        addr: IP address string to check.

    Returns:
        ``True`` if the address is in a blocked network range.
    """
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return True  # Unparseable → blocked (fail-closed)

    # Unwrap IPv6-mapped IPv4 (::ffff:x.x.x.x)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped

    return any(ip in network for network in _BLOCKED_NETWORKS)


def _extract_hostname(url: str) -> str | None:
    """Extract the hostname from a clone URL.

    Supports:
    - Standard URLs: ``https://host/path``,
      ``ssh://user@host:port/path``
    - SCP-like syntax: ``user@host:path``
    - IPv6 literals: ``https://[::1]/path``

    Args:
        url: Repository URL string.

    Returns:
        The extracted hostname, or ``None`` if unparseable.
    """
    # Standard URL schemes
    if "://" in url:
        parsed = urlparse(url)
        hostname = parsed.hostname  # strips brackets from IPv6
        return hostname or None

    # SCP-like syntax: user@host:path
    if "@" in url and ":" in url:
        at_idx = url.index("@")
        rest = url[at_idx + 1 :]

        # IPv6 literal in brackets: git@[::1]:path
        if rest.startswith("["):
            bracket_end = rest.find("]")
            if bracket_end == -1:
                return None
            hostname = rest[1:bracket_end]
            return hostname or None

        colon_idx = rest.find(":")
        if colon_idx == -1:
            return None
        hostname = rest[:colon_idx]
        return hostname or None

    return None


def _is_allowed_clone_scheme(url: str) -> bool:
    """Check if a clone URL uses an allowed remote scheme.

    Allows standard remote schemes and SCP-like syntax.  Rejects
    ``file://``, ``ext::``, bare local paths, and URLs starting with
    ``-`` (flag injection).

    Args:
        url: Repository URL string to validate.

    Returns:
        ``True`` if the URL scheme is allowed.
    """
    if url.startswith("-"):
        return False
    if any(url.startswith(scheme) for scheme in _ALLOWED_CLONE_SCHEMES):
        return True
    # SCP-like syntax: user@host:path (e.g. git@github.com:user/repo.git).
    # Must have @ and : but NOT :: (rejects ext:: protocol) and NOT ://
    # (rejects URLs that should match a scheme above).
    return "@" in url and ":" in url and "::" not in url and "://" not in url


# ── DNS resolution helper ────────────────────────────────────────


async def _resolve_and_check(
    hostname: str,
    dns_timeout: float,
) -> str | None:
    """Resolve *hostname* via DNS and check all IPs against blocklist.

    Args:
        hostname: Lowercase hostname to resolve.
        dns_timeout: DNS resolution timeout in seconds.

    Returns:
        An error message if any resolved IP is blocked or DNS fails,
        or ``None`` if all IPs are public.
    """
    loop = asyncio.get_running_loop()
    try:
        results = await asyncio.wait_for(
            loop.getaddrinfo(hostname, None),
            timeout=dns_timeout,
        )
    except TimeoutError:
        logger.warning(
            GIT_CLONE_DNS_FAILED,
            hostname=hostname,
            reason="timeout",
        )
        return f"DNS resolution for {hostname!r} timed out"
    except OSError as exc:
        logger.warning(
            GIT_CLONE_DNS_FAILED,
            hostname=hostname,
            reason=str(exc),
        )
        return f"DNS resolution for {hostname!r} failed: {exc}"

    if not results:
        logger.warning(
            GIT_CLONE_DNS_FAILED,
            hostname=hostname,
            reason="no_results",
        )
        return f"DNS resolution for {hostname!r} returned no results"

    # Every resolved IP must be public
    for *_info, sockaddr in results:
        addr = sockaddr[0]
        if _is_blocked_ip(addr):
            logger.warning(
                GIT_CLONE_SSRF_BLOCKED,
                hostname=hostname,
                resolved_ip=addr,
                reason="dns_resolves_to_private_ip",
            )
            return (
                f"Clone URL host {hostname!r} resolves to "
                f"blocked private/reserved IP {addr}"
            )

    return None


# ── Main validator ───────────────────────────────────────────────


async def validate_clone_url_host(
    url: str,
    policy: GitCloneNetworkPolicy,
) -> str | None:
    """Validate that a clone URL host is not private or internal.

    Performs DNS resolution to detect hosts resolving to private IPs
    (DNS rebinding prevention).  **All** resolved addresses must be
    public for the URL to be allowed.  Fails closed on DNS errors.

    Args:
        url: Repository URL string to validate.
        policy: Network policy controlling allowlist and blocking.

    Returns:
        An error message string if the host is blocked, or ``None``
        if the host is allowed.
    """
    hostname = _extract_hostname(url)
    if not hostname:
        return "Could not extract hostname from clone URL"

    normalized = hostname.lower()

    # Allowlist bypass (case-insensitive)
    if any(normalized == h.lower() for h in policy.hostname_allowlist):
        return None

    # Master switch
    if not policy.block_private_ips:
        return None

    # Literal IP — no DNS needed
    try:
        ipaddress.ip_address(normalized)
    except ValueError:
        pass  # Not a literal IP, resolve below
    else:
        if _is_blocked_ip(normalized):
            logger.warning(
                GIT_CLONE_SSRF_BLOCKED,
                hostname=normalized,
                reason="literal_private_ip",
            )
            return f"Clone URL host {normalized!r} is a blocked private/reserved IP"
        return None

    return await _resolve_and_check(normalized, policy.dns_resolution_timeout)
