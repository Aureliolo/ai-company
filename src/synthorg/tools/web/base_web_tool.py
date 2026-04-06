"""Base class for web tools.

Provides the common ``ToolCategory.WEB`` category, a
``NetworkPolicy`` instance for SSRF prevention, and a
shared URL validation helper.
"""

from abc import ABC
from typing import Any

from synthorg.core.enums import ToolCategory
from synthorg.tools.base import BaseTool
from synthorg.tools.network_validator import (
    DnsValidationOk,
    NetworkPolicy,
    is_allowed_http_scheme,
    validate_url_host,
)


class BaseWebTool(BaseTool, ABC):
    """Abstract base for all web tools.

    Sets ``category=ToolCategory.WEB`` and holds a shared
    ``NetworkPolicy`` for SSRF prevention and a configurable
    request timeout.
    """

    def __init__(  # noqa: PLR0913
        self,
        *,
        name: str,
        description: str = "",
        parameters_schema: dict[str, Any] | None = None,
        action_type: str | None = None,
        network_policy: NetworkPolicy | None = None,
        request_timeout: float = 30.0,
    ) -> None:
        """Initialize a web tool with network policy.

        Args:
            name: Tool name.
            description: Human-readable description.
            parameters_schema: JSON Schema for tool parameters.
            action_type: Security action type override.
            network_policy: Network policy for SSRF prevention.
                ``None`` uses the default (block all private IPs).
            request_timeout: Default request timeout in seconds.
        """
        super().__init__(
            name=name,
            description=description,
            category=ToolCategory.WEB,
            parameters_schema=parameters_schema,
            action_type=action_type,
        )
        self._network_policy = network_policy or NetworkPolicy()
        self._request_timeout = request_timeout

    @property
    def network_policy(self) -> NetworkPolicy:
        """The network policy for SSRF prevention."""
        return self._network_policy

    async def _validate_url(self, url: str) -> str | DnsValidationOk:
        """Validate a URL against the network policy.

        Checks scheme and host/IP against SSRF blocklist.

        Args:
            url: URL to validate.

        Returns:
            An error message string if blocked, or a
            ``DnsValidationOk`` on success.
        """
        if not is_allowed_http_scheme(url):
            return (
                f"URL scheme not allowed: {url!r}. "
                "Only http:// and https:// are permitted."
            )
        return await validate_url_host(url, self._network_policy)
