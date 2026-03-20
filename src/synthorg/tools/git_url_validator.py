"""Git clone URL validation -- SSRF prevention with DNS resolution.

Validates clone URLs against allowed schemes and performs hostname/IP
validation to prevent Server-Side Request Forgery (SSRF) attacks via
``git clone``.  All resolved IPs must be public; private, loopback,
link-local, and reserved addresses are blocked by default.  A
configurable hostname allowlist lets legitimate internal Git servers
bypass the private-IP check.

TOCTOU DNS rebinding is mitigated by two complementary strategies:

* **HTTPS URLs** -- the validated IPs are returned to the caller so
  it can pin ``git clone`` via ``-c http.curloptResolve`` (requires
  git >= 2.22, which uses libcurl under the hood).
* **SSH / SCP-like URLs** -- a second DNS resolution is performed
  immediately before execution and compared against the first; if new
  IPs appear that were not in the validated set the clone is blocked.

Both mitigations can be disabled via
``GitCloneNetworkPolicy(dns_rebinding_mitigation=False)`` for
environments where DNS results legitimately vary between resolves
(CDN, geo-DNS, etc.).  For defense-in-depth, combine with
network-level egress controls (firewall, HTTP CONNECT proxy).
See the sandbox design page for planned network isolation.
"""

import asyncio
import ipaddress
import re
from typing import Any, Final, Self
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, model_validator

from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.git import (
    GIT_CLONE_DNS_FAILED,
    GIT_CLONE_DNS_REBINDING_DETECTED,
    GIT_CLONE_SSRF_BLOCKED,
    GIT_CLONE_SSRF_DISABLED,
)

logger = get_logger(__name__)

# ── Constants ────────────────────────────────────────────────────

ALLOWED_CLONE_SCHEMES: Final[tuple[str, ...]] = (
    "https://",
    "ssh://",
)

# Matches scheme://userinfo@host patterns in clone URLs.
_CREDENTIAL_RE: Final[re.Pattern[str]] = re.compile(r"(\w+://)[^@/]+@")

_BLOCKED_NETWORKS: Final[tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]] = (
    # IPv4 -- loopback, private, link-local, reserved
    ipaddress.IPv4Network("0.0.0.0/8"),
    ipaddress.IPv4Network("10.0.0.0/8"),
    ipaddress.IPv4Network("100.64.0.0/10"),  # CGNAT (RFC 6598)
    ipaddress.IPv4Network("127.0.0.0/8"),
    ipaddress.IPv4Network("169.254.0.0/16"),
    ipaddress.IPv4Network("172.16.0.0/12"),
    ipaddress.IPv4Network("192.0.0.0/24"),  # IETF Protocol Assignments
    ipaddress.IPv4Network("192.0.2.0/24"),  # TEST-NET-1 (RFC 5737)
    ipaddress.IPv4Network("192.168.0.0/16"),
    ipaddress.IPv4Network("198.18.0.0/15"),  # Benchmarking (RFC 2544)
    ipaddress.IPv4Network("198.51.100.0/24"),  # TEST-NET-2 (RFC 5737)
    ipaddress.IPv4Network("203.0.113.0/24"),  # TEST-NET-3 (RFC 5737)
    ipaddress.IPv4Network("224.0.0.0/4"),  # Multicast (RFC 5771)
    ipaddress.IPv4Network("240.0.0.0/4"),  # Reserved (RFC 1112)
    ipaddress.IPv4Network("255.255.255.255/32"),  # Broadcast
    # IPv6 -- loopback, link-local, ULA, tunneling, multicast, reserved
    ipaddress.IPv6Network("::/128"),
    ipaddress.IPv6Network("::1/128"),
    ipaddress.IPv6Network("64:ff9b::/96"),  # NAT64 (RFC 6052)
    ipaddress.IPv6Network("100::/64"),  # Discard (RFC 6666)
    ipaddress.IPv6Network("2001::/32"),  # Teredo (RFC 4380)
    ipaddress.IPv6Network("2001:db8::/32"),  # Documentation (RFC 3849)
    ipaddress.IPv6Network("2002::/16"),  # 6to4 (RFC 3056) -- encodes IPv4
    ipaddress.IPv6Network("fc00::/7"),
    ipaddress.IPv6Network("fe80::/10"),
    ipaddress.IPv6Network("ff00::/8"),  # Multicast (RFC 4291)
)


# ── Network policy model ─────────────────────────────────────────


class GitCloneNetworkPolicy(BaseModel):
    """Network policy for git clone SSRF prevention.

    Controls which hosts are allowed as clone targets.  By default,
    all public hosts are permitted while private, loopback, and
    link-local addresses are blocked.  Entries in
    ``hostname_allowlist`` bypass the private-IP check for legitimate
    internal Git servers.

    Allowlist entries are normalized to lowercase and deduplicated
    at construction time.

    Attributes:
        hostname_allowlist: Hostnames that bypass the private-IP
            check.  Stored lowercase after construction.
        block_private_ips: Master switch for private IP blocking.
            When ``False``, **all** hosts are allowed regardless
            of IP -- use only in development.
        dns_resolution_timeout: Timeout in seconds for async DNS
            resolution.
        dns_rebinding_mitigation: Enable TOCTOU DNS rebinding
            mitigation.  When ``True`` (default), HTTPS clones use
            ``http.curloptResolve`` to pin git to validated IPs,
            and SSH/SCP clones double-resolve to detect IP changes.
            Disable for hosts behind CDNs or geo-DNS where resolved
            IPs legitimately vary between queries.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    hostname_allowlist: tuple[NotBlankStr, ...] = Field(
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
    dns_rebinding_mitigation: bool = Field(
        default=True,
        description=(
            "Enable TOCTOU DNS rebinding mitigation "
            "(curloptResolve for HTTPS, double-resolve for SSH/SCP)"
        ),
    )

    @model_validator(mode="after")
    def _normalize_allowlist(self) -> Self:
        """Lowercase and deduplicate allowlist entries."""
        normalized = tuple(dict.fromkeys(h.lower() for h in self.hostname_allowlist))
        if normalized != self.hostname_allowlist:
            object.__setattr__(self, "hostname_allowlist", normalized)
        return self


# ── Validation result model ──────────────────────────────────────


class DnsValidationOk(BaseModel):
    """Successful DNS validation result with resolved addresses.

    Carries validated IP addresses so the caller can pin DNS
    resolution and close the TOCTOU gap between validation and
    ``git clone`` execution.

    Attributes:
        hostname: The normalized (lowercase) hostname that was
            resolved.
        port: Explicit port from the URL, or scheme default (443
            for HTTPS).  ``None`` for non-HTTPS URLs (SSH/SCP).
        resolved_ips: Deduplicated resolved IP addresses.  Empty
            for literal IPs, allowlisted hosts, disabled blocking,
            or when ``dns_rebinding_mitigation`` is off.
        is_https: Whether the URL uses HTTPS transport (eligible
            for ``http.curloptResolve`` pinning).
    """

    model_config = ConfigDict(frozen=True)

    hostname: NotBlankStr
    port: int | None = Field(default=None, gt=0, le=65535)
    resolved_ips: tuple[str, ...] = ()
    is_https: bool = False


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
        logger.warning(
            GIT_CLONE_SSRF_BLOCKED,
            addr=addr,
            reason="unparseable_ip_blocked",
        )
        return True  # Unparseable -> blocked (fail-closed)

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


def is_allowed_clone_scheme(url: str) -> bool:
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
    if any(url.startswith(scheme) for scheme in ALLOWED_CLONE_SCHEMES):
        return True
    # SCP-like syntax: user@host:path (e.g. git@github.com:user/repo.git).
    # Must have @ and : but NOT :// (rejects URLs that should match a
    # scheme above).  Bracketed IPv6 literals (git@[::1]:path) are
    # allowed; unbracketed :: is rejected (catches ext:: protocol).
    if "://" in url or "@" not in url or ":" not in url:
        return False
    _, rest = url.split("@", 1)
    if rest.startswith("["):
        bracket_end = rest.find("]")
        return bracket_end > 0 and rest[bracket_end + 1 : bracket_end + 2] == ":"
    host, _sep, _path = rest.partition(":")
    return bool(host) and "::" not in host


def build_curl_resolve_value(
    hostname: str,
    port: int,
    ips: tuple[str, ...],
) -> str:
    """Build a ``http.curloptResolve`` config value.

    Format: ``host:port:addr1,addr2,...``

    IPv6 addresses do NOT need brackets in the resolve value --
    libcurl handles position-based parsing.

    Args:
        hostname: Hostname to pin.
        port: Port number (e.g. 443 for default HTTPS).
        ips: Non-empty tuple of validated IP addresses to pin to.

    Returns:
        The curloptResolve config string.

    Raises:
        ValueError: If *ips* is empty.
    """
    if not ips:
        msg = "ips must not be empty"
        raise ValueError(msg)
    return f"{hostname}:{port}:{','.join(ips)}"


# ── DNS resolution helpers ───────────────────────────────────────


def _dns_failure(hostname: str, reason: str, message: str) -> str:
    """Log a DNS resolution failure and return the error message."""
    logger.warning(
        GIT_CLONE_DNS_FAILED,
        hostname=hostname,
        reason=reason,
    )
    return message


async def _resolve_dns(
    hostname: str,
    dns_timeout: float,
) -> list[tuple[Any, ...]] | str:
    """Resolve *hostname* via async DNS.

    Args:
        hostname: Lowercase hostname to resolve.
        dns_timeout: DNS resolution timeout in seconds.

    Returns:
        The raw ``getaddrinfo`` result list on success, or an error
        message string on failure.
    """
    loop = asyncio.get_running_loop()
    try:
        results = await asyncio.wait_for(
            loop.getaddrinfo(hostname, None),
            timeout=dns_timeout,
        )
    except TimeoutError:
        return _dns_failure(
            hostname,
            "timeout",
            f"DNS resolution for {hostname!r} timed out",
        )
    except OSError as exc:
        return _dns_failure(
            hostname,
            str(exc),
            f"DNS resolution for {hostname!r} failed: {exc}",
        )
    except Exception as exc:
        logger.error(
            GIT_CLONE_DNS_FAILED,
            hostname=hostname,
            reason=f"unexpected: {type(exc).__name__}: {exc}",
            exc_info=True,
        )
        return f"DNS resolution for {hostname!r} failed: {exc}"

    if not results:
        return _dns_failure(
            hostname,
            "no_results",
            f"DNS resolution for {hostname!r} returned no results",
        )

    return results


def _check_resolved_ips(
    hostname: str,
    results: list[tuple[Any, ...]],
) -> str | tuple[str, ...]:
    """Validate resolved IPs and return deduplicated public addresses.

    Args:
        hostname: Hostname that was resolved (for error messages).
        results: Raw ``getaddrinfo`` result tuples.

    Returns:
        A deduplicated tuple of validated public IP strings on
        success, or an error message string if any IP is blocked.
    """
    seen: dict[str, None] = {}
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
        seen[addr] = None

    return tuple(seen)


async def _resolve_and_check(
    hostname: str,
    dns_timeout: float,
) -> str | tuple[str, ...]:
    """Resolve *hostname* via DNS and check all IPs against blocklist.

    Args:
        hostname: Lowercase hostname to resolve.
        dns_timeout: DNS resolution timeout in seconds.

    Returns:
        A deduplicated tuple of validated public IP strings on
        success, or an error message string if any resolved IP is
        blocked or DNS fails.
    """
    results = await _resolve_dns(hostname, dns_timeout)
    if isinstance(results, str):
        return results
    return _check_resolved_ips(hostname, results)


# ── Double-resolve consistency check ─────────────────────────────


async def verify_dns_consistency(
    hostname: str,
    expected_ips: frozenset[str],
    dns_timeout: float,
) -> str | None:
    """Re-resolve *hostname* and verify consistency with prior result.

    Performs a second DNS resolution immediately before execution and
    checks two conditions:

    1. All re-resolved IPs must be public (primary SSRF defense).
    2. The re-resolved IP set must be a subset of *expected_ips*
       (detects DNS rebinding where IPs change between resolves).

    Args:
        hostname: Lowercase hostname to re-resolve.
        expected_ips: IP addresses from the initial validation.
        dns_timeout: DNS resolution timeout in seconds.

    Returns:
        An error message if rebinding is detected or any IP is
        blocked, or ``None`` if the resolution is consistent.
    """
    result = await _resolve_and_check(hostname, dns_timeout)
    if isinstance(result, str):
        return result

    new_ips = frozenset(result)
    unexpected = new_ips - expected_ips
    if unexpected:
        logger.warning(
            GIT_CLONE_DNS_REBINDING_DETECTED,
            hostname=hostname,
            expected_ips=sorted(expected_ips),
            new_ips=sorted(new_ips),
            unexpected_ips=sorted(unexpected),
        )
        return (
            f"DNS rebinding detected for {hostname!r}: "
            f"re-resolved IPs {sorted(new_ips)} differ from "
            f"validated IPs {sorted(expected_ips)}"
        )

    return None


# ── Main validator ───────────────────────────────────────────────


def _ok(
    hostname: str,
    port: int | None,
    *,
    is_https: bool,
    resolved_ips: tuple[str, ...] = (),
) -> DnsValidationOk:
    """Construct a successful validation result."""
    return DnsValidationOk(
        hostname=hostname,
        port=port,
        resolved_ips=resolved_ips,
        is_https=is_https,
    )


async def validate_clone_url_host(  # noqa: PLR0911
    url: str,
    policy: GitCloneNetworkPolicy,
) -> str | DnsValidationOk:
    """Validate that a clone URL host is not private or internal.

    Performs DNS resolution to detect hosts resolving to private IPs
    (DNS rebinding prevention).  **All** resolved addresses must be
    public for the URL to be allowed.  Fails closed on DNS errors.

    On success, returns a ``DnsValidationOk`` carrying the resolved
    IPs so the caller can apply TOCTOU mitigation (curloptResolve
    pinning for HTTPS, double-resolve for SSH/SCP).

    Args:
        url: Repository URL string to validate.
        policy: Network policy controlling allowlist and blocking.

    Returns:
        An error message string if the host is blocked, or a
        ``DnsValidationOk`` on success.
    """
    hostname = _extract_hostname(url)
    if not hostname:
        redacted = _CREDENTIAL_RE.sub(r"\1***@", url)
        logger.warning(
            GIT_CLONE_SSRF_BLOCKED,
            url=redacted,
            reason="hostname_extraction_failed",
        )
        return f"Could not extract hostname from clone URL: {redacted!r}"

    normalized = hostname.lower()
    is_https = url.startswith("https://")
    port: int | None = None
    if is_https:
        port = urlparse(url).port or 443

    # Allowlist bypass (pre-normalized to lowercase at construction)
    if normalized in policy.hostname_allowlist:
        return _ok(normalized, port, is_https=is_https)

    # Master switch
    if not policy.block_private_ips:
        logger.warning(
            GIT_CLONE_SSRF_DISABLED,
            hostname=normalized,
            reason="block_private_ips_disabled",
        )
        return _ok(normalized, port, is_https=is_https)

    # Literal IP -- no DNS needed, no TOCTOU gap
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
        return _ok(normalized, port, is_https=is_https)

    # DNS resolution + IP check
    result = await _resolve_and_check(normalized, policy.dns_resolution_timeout)
    if isinstance(result, str):
        return result

    resolved_ips = result if policy.dns_rebinding_mitigation else ()
    return _ok(normalized, port, is_https=is_https, resolved_ips=resolved_ips)
