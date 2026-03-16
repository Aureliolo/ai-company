"""Tests for git clone URL validation and SSRF prevention."""

import asyncio
import ipaddress
from unittest.mock import AsyncMock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from synthorg.tools.git_url_validator import (
    GitCloneNetworkPolicy,
    _extract_hostname,
    _is_allowed_clone_scheme,
    _is_blocked_ip,
    validate_clone_url_host,
)

pytestmark = pytest.mark.timeout(30)


# ── _extract_hostname ─────────────────────────────────────────────


@pytest.mark.unit
class TestExtractHostname:
    """Hostname extraction from various URL formats."""

    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            ("https://github.com/user/repo.git", "github.com"),
            ("https://HOST.EXAMPLE.COM/repo", "host.example.com"),
            ("https://host:8443/repo.git", "host"),
            ("https://user@host/repo.git", "host"),
            ("ssh://git@host.example/repo", "host.example"),
            ("ssh://git@host:22/repo.git", "host"),
            ("https://[::1]/repo.git", "::1"),
            ("https://[2001:db8::1]:443/repo", "2001:db8::1"),
        ],
        ids=[
            "https-basic",
            "https-uppercase",
            "https-port",
            "https-userinfo",
            "ssh-basic",
            "ssh-port",
            "https-ipv6-literal",
            "https-ipv6-port",
        ],
    )
    def test_standard_urls(self, url: str, expected: str) -> None:
        assert _extract_hostname(url) == expected

    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            ("git@github.com:user/repo.git", "github.com"),
            ("deploy@host.example:path/repo", "host.example"),
            ("git@[::1]:repo.git", "::1"),
        ],
        ids=["scp-basic", "scp-custom-user", "scp-ipv6"],
    )
    def test_scp_like(self, url: str, expected: str) -> None:
        assert _extract_hostname(url) == expected

    @pytest.mark.parametrize(
        "url",
        [
            "",
            "not-a-url",
            "/local/path",
            "https://",
            "https:///path",
        ],
        ids=[
            "empty",
            "bare-string",
            "local-path",
            "scheme-only",
            "empty-host",
        ],
    )
    def test_unparseable_returns_none(self, url: str) -> None:
        assert _extract_hostname(url) is None


# ── _is_blocked_ip ────────────────────────────────────────────────


@pytest.mark.unit
class TestIsBlockedIp:
    """Private/reserved IP detection including IPv6-mapped IPv4."""

    @pytest.mark.parametrize(
        "addr",
        [
            "127.0.0.1",
            "127.255.255.255",
            "10.0.0.1",
            "10.255.255.255",
            "172.16.0.1",
            "172.31.255.255",
            "192.168.0.1",
            "192.168.255.255",
            "169.254.1.1",
            "0.0.0.0",  # noqa: S104
            "::1",
            "fe80::1",
            "fc00::1",
            "fd00::1",
            "::",
        ],
        ids=[
            "loopback-start",
            "loopback-end",
            "private-10-start",
            "private-10-end",
            "private-172-start",
            "private-172-end",
            "private-192-start",
            "private-192-end",
            "link-local",
            "unspecified-v4",
            "loopback-v6",
            "link-local-v6",
            "ula-v6-fc",
            "ula-v6-fd",
            "unspecified-v6",
        ],
    )
    def test_blocked_addresses(self, addr: str) -> None:
        assert _is_blocked_ip(addr) is True

    @pytest.mark.parametrize(
        "addr",
        [
            "8.8.8.8",
            "1.1.1.1",
            "93.184.216.34",
            "203.0.113.1",
            "2001:db8::1",
            "2607:f8b0:4004:800::200e",
        ],
        ids=[
            "google-dns",
            "cloudflare-dns",
            "example-com",
            "documentation",
            "doc-v6",
            "google-v6",
        ],
    )
    def test_public_addresses(self, addr: str) -> None:
        assert _is_blocked_ip(addr) is False

    @pytest.mark.parametrize(
        ("mapped", "expected"),
        [
            ("::ffff:127.0.0.1", True),
            ("::ffff:10.0.0.1", True),
            ("::ffff:192.168.1.1", True),
            ("::ffff:8.8.8.8", False),
            ("::ffff:93.184.216.34", False),
        ],
        ids=[
            "mapped-loopback",
            "mapped-private-10",
            "mapped-private-192",
            "mapped-google-dns",
            "mapped-example-com",
        ],
    )
    def test_ipv6_mapped_ipv4(self, mapped: str, expected: bool) -> None:
        assert _is_blocked_ip(mapped) is expected

    def test_unparseable_is_blocked(self) -> None:
        """Unparseable addresses are blocked (fail-closed)."""
        assert _is_blocked_ip("not-an-ip") is True


# ── _is_allowed_clone_scheme ──────────────────────────────────────


@pytest.mark.unit
class TestIsAllowedCloneScheme:
    """Scheme validation for clone URLs (moved from test_git_tools)."""

    @pytest.mark.parametrize(
        "url",
        [
            "https://github.com/user/repo.git",
            "https://host:8443/repo.git",
            "ssh://git@host/repo.git",
            "ssh://host:22/repo.git",
            "git@github.com:user/repo.git",
            "deploy@host.example:path/repo",
        ],
        ids=[
            "https",
            "https-port",
            "ssh",
            "ssh-port",
            "scp-git",
            "scp-deploy",
        ],
    )
    def test_allowed_schemes(self, url: str) -> None:
        assert _is_allowed_clone_scheme(url) is True

    @pytest.mark.parametrize(
        "url",
        [
            "/etc/passwd",
            "file:///etc",
            "ext::sh -c 'evil'",
            "../outside-repo",
            "-cfoo=bar@host:path",
            "http://insecure.example.com/repo",
            "not-a-real-url-at-all",
        ],
        ids=[
            "local-path",
            "file-scheme",
            "ext-protocol",
            "relative-path",
            "flag-injection",
            "http-insecure",
            "garbage",
        ],
    )
    def test_blocked_schemes(self, url: str) -> None:
        assert _is_allowed_clone_scheme(url) is False


# ── GitCloneNetworkPolicy ────────────────────────────────────────


@pytest.mark.unit
class TestGitCloneNetworkPolicy:
    """Pydantic model defaults, bounds, and immutability."""

    def test_defaults(self) -> None:
        policy = GitCloneNetworkPolicy()
        assert policy.hostname_allowlist == ()
        assert policy.block_private_ips is True
        assert policy.dns_resolution_timeout == 5.0

    def test_custom_values(self) -> None:
        policy = GitCloneNetworkPolicy(
            hostname_allowlist=("git.internal",),
            block_private_ips=False,
            dns_resolution_timeout=10.0,
        )
        assert policy.hostname_allowlist == ("git.internal",)
        assert policy.block_private_ips is False
        assert policy.dns_resolution_timeout == 10.0

    def test_frozen(self) -> None:
        policy = GitCloneNetworkPolicy()
        with pytest.raises(ValidationError):
            policy.block_private_ips = False  # type: ignore[misc]

    def test_timeout_bounds(self) -> None:
        with pytest.raises(ValidationError):
            GitCloneNetworkPolicy(dns_resolution_timeout=0)
        with pytest.raises(ValidationError):
            GitCloneNetworkPolicy(dns_resolution_timeout=31)


# ── validate_clone_url_host ───────────────────────────────────────


def _dns_result(
    *addrs: str,
) -> list[tuple[int, int, int, str, tuple[str, int]]]:
    """Build a fake getaddrinfo result list."""
    return [(2, 1, 6, "", (addr, 0)) for addr in addrs]


@pytest.mark.unit
class TestValidateCloneUrlHost:
    """Async SSRF validation with mocked DNS."""

    async def test_public_host_allowed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Public host resolving to public IP is allowed."""
        loop = asyncio.get_running_loop()
        monkeypatch.setattr(
            loop,
            "getaddrinfo",
            AsyncMock(return_value=_dns_result("93.184.216.34")),
        )
        policy = GitCloneNetworkPolicy()
        result = await validate_clone_url_host("https://example.com/repo.git", policy)
        assert result is None

    async def test_dns_rebinding_blocked(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Host resolving to private IP is blocked."""
        loop = asyncio.get_running_loop()
        monkeypatch.setattr(
            loop,
            "getaddrinfo",
            AsyncMock(return_value=_dns_result("127.0.0.1")),
        )
        policy = GitCloneNetworkPolicy()
        result = await validate_clone_url_host(
            "https://evil.example.com/repo.git", policy
        )
        assert result is not None
        assert "blocked" in result.lower()

    async def test_literal_private_ip_blocked(self) -> None:
        """Literal private IP in URL is blocked (no DNS needed)."""
        policy = GitCloneNetworkPolicy()
        result = await validate_clone_url_host(
            "https://169.254.169.254/latest/meta-data", policy
        )
        assert result is not None
        assert "blocked" in result.lower()

    async def test_literal_public_ip_allowed(self) -> None:
        """Literal public IP in URL is allowed (no DNS needed)."""
        policy = GitCloneNetworkPolicy()
        result = await validate_clone_url_host("https://93.184.216.34/repo.git", policy)
        assert result is None

    async def test_allowlisted_host_bypasses_check(self) -> None:
        """Allowlisted host bypasses private IP check entirely."""
        policy = GitCloneNetworkPolicy(
            hostname_allowlist=("git.internal.corp",),
        )
        # No DNS mock needed — allowlist check returns early
        result = await validate_clone_url_host(
            "https://git.internal.corp/repo.git", policy
        )
        assert result is None

    async def test_allowlist_case_insensitive(self) -> None:
        """Allowlist matching is case-insensitive."""
        policy = GitCloneNetworkPolicy(
            hostname_allowlist=("Git.Internal.Corp",),
        )
        result = await validate_clone_url_host(
            "https://git.internal.corp/repo.git", policy
        )
        assert result is None

    async def test_dns_timeout_blocked(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """DNS timeout rejects the URL (fail-closed)."""
        loop = asyncio.get_running_loop()
        monkeypatch.setattr(
            loop,
            "getaddrinfo",
            AsyncMock(side_effect=TimeoutError("DNS timeout")),
        )
        policy = GitCloneNetworkPolicy()
        result = await validate_clone_url_host(
            "https://slow.example.com/repo.git", policy
        )
        assert result is not None
        assert "timed out" in result.lower()

    async def test_dns_nxdomain_blocked(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """DNS NXDOMAIN rejects the URL (fail-closed)."""
        loop = asyncio.get_running_loop()
        monkeypatch.setattr(
            loop,
            "getaddrinfo",
            AsyncMock(side_effect=OSError("Name or service not known")),
        )
        policy = GitCloneNetworkPolicy()
        result = await validate_clone_url_host(
            "https://nxdomain.invalid/repo.git", policy
        )
        assert result is not None
        assert "failed" in result.lower()

    async def test_dns_empty_results_blocked(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Empty DNS results reject the URL (fail-closed)."""
        loop = asyncio.get_running_loop()
        monkeypatch.setattr(
            loop,
            "getaddrinfo",
            AsyncMock(return_value=[]),
        )
        policy = GitCloneNetworkPolicy()
        result = await validate_clone_url_host(
            "https://empty-dns.example.com/repo.git", policy
        )
        assert result is not None
        assert "no results" in result.lower()

    async def test_block_private_ips_disabled(self) -> None:
        """Disabling block_private_ips allows everything."""
        policy = GitCloneNetworkPolicy(block_private_ips=False)
        result = await validate_clone_url_host("https://127.0.0.1/repo.git", policy)
        assert result is None

    async def test_mixed_dns_results_one_private_blocked(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """One public + one private result → blocked."""
        loop = asyncio.get_running_loop()
        monkeypatch.setattr(
            loop,
            "getaddrinfo",
            AsyncMock(return_value=_dns_result("93.184.216.34", "127.0.0.1")),
        )
        policy = GitCloneNetworkPolicy()
        result = await validate_clone_url_host(
            "https://multi.example.com/repo.git", policy
        )
        assert result is not None
        assert "blocked" in result.lower()

    async def test_scp_like_private_host_blocked(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SCP-like URL to private host is blocked."""
        loop = asyncio.get_running_loop()
        monkeypatch.setattr(
            loop,
            "getaddrinfo",
            AsyncMock(return_value=_dns_result("10.0.0.5")),
        )
        policy = GitCloneNetworkPolicy()
        result = await validate_clone_url_host("git@internal-host:repo.git", policy)
        assert result is not None
        assert "blocked" in result.lower()

    async def test_unparseable_url_blocked(self) -> None:
        """URL with no extractable hostname is blocked."""
        policy = GitCloneNetworkPolicy()
        result = await validate_clone_url_host("not-a-url", policy)
        assert result is not None
        assert "could not extract" in result.lower()


# ── Property-based tests ──────────────────────────────────────────


@pytest.mark.unit
class TestValidateCloneUrlHostProperties:
    """Hypothesis property-based tests for IP blocking."""

    @given(
        ip=st.one_of(
            st.ip_addresses(v=4, network="127.0.0.0/8"),
            st.ip_addresses(v=4, network="10.0.0.0/8"),
            st.ip_addresses(v=4, network="172.16.0.0/12"),
            st.ip_addresses(v=4, network="192.168.0.0/16"),
            st.ip_addresses(v=4, network="169.254.0.0/16"),
            st.ip_addresses(v=4, network="0.0.0.0/8"),
        ),
    )
    @settings(max_examples=200)
    def test_blocked_ipv4_always_detected(self, ip: ipaddress.IPv4Address) -> None:
        """Every IPv4 in a blocked range is detected."""
        assert _is_blocked_ip(str(ip)) is True

    @given(
        ip=st.one_of(
            st.ip_addresses(v=6, network="::1/128"),
            st.ip_addresses(v=6, network="fe80::/10"),
            st.ip_addresses(v=6, network="fc00::/7"),
        ),
    )
    @settings(max_examples=200)
    def test_blocked_ipv6_always_detected(self, ip: ipaddress.IPv6Address) -> None:
        """Every IPv6 in a blocked range is detected."""
        assert _is_blocked_ip(str(ip)) is True

    @given(
        ip=st.ip_addresses(v=4).filter(
            lambda ip: (
                not any(
                    ip in net
                    for net in (
                        ipaddress.IPv4Network("0.0.0.0/8"),
                        ipaddress.IPv4Network("10.0.0.0/8"),
                        ipaddress.IPv4Network("127.0.0.0/8"),
                        ipaddress.IPv4Network("169.254.0.0/16"),
                        ipaddress.IPv4Network("172.16.0.0/12"),
                        ipaddress.IPv4Network("192.168.0.0/16"),
                    )
                )
            )
        ),
    )
    @settings(max_examples=200)
    def test_non_blocked_ipv4_never_flagged(self, ip: ipaddress.IPv4Address) -> None:
        """IPv4 outside blocked ranges is never flagged."""
        assert _is_blocked_ip(str(ip)) is False
