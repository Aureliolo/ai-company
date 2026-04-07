"""Sandbox auth proxy -- route LLM traffic through SynthOrg's provider layer.

Provides a local HTTP proxy that intercepts outbound LLM requests
from sandbox containers, injects authentication headers from
SynthOrg's encrypted credential store, and forwards to the real
provider endpoint.  Credentials never enter the container.

.. note::

    This module defines the proxy interface and lifecycle management.
    The HTTP proxy server uses ``aiohttp`` when available.
"""

from synthorg.observability import get_logger

logger = get_logger(__name__)


class SandboxAuthProxy:
    """Local HTTP proxy for authenticated LLM traffic from sandboxes.

    Listens on a localhost port, intercepts outbound LLM requests,
    adds authentication headers, and forwards to the real provider.

    Attributes:
        port: Port the proxy is listening on (0 = not started).
        url: Full URL of the proxy (empty string when not started).
    """

    def __init__(self) -> None:
        self._port: int = 0
        self._url: str = ""

    @property
    def port(self) -> int:
        """Port the proxy is listening on (0 when not started)."""
        return self._port

    @property
    def url(self) -> str:
        """Full URL of the proxy (empty when not started)."""
        return self._url

    async def start(self, *, port: int = 0) -> str:
        """Start the auth proxy.

        Args:
            port: Port to listen on (0 = ephemeral port).

        Returns:
            The URL of the running proxy.

        Raises:
            NotImplementedError: Proxy server not yet implemented.
        """
        msg = (
            "SandboxAuthProxy.start() is not yet implemented. "
            "This will be available when the auth proxy server "
            "is built on top of aiohttp."
        )
        logger.warning(
            "sandbox.auth_proxy.not_implemented",
            port=port,
        )
        raise NotImplementedError(msg)

    async def stop(self) -> None:
        """Stop the auth proxy and release the port.

        Safe to call when not started.
        """
        self._port = 0
        self._url = ""
