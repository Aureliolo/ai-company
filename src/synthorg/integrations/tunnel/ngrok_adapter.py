"""ngrok tunnel adapter for local webhook development.

Wraps the ``pyngrok`` library (or ngrok binary) to expose the
local API server on a public URL for receiving webhooks.
"""

import asyncio
import os

from synthorg.integrations.errors import TunnelError
from synthorg.observability import get_logger
from synthorg.observability.events.integrations import (
    TUNNEL_ERROR,
    TUNNEL_STARTED,
    TUNNEL_STOPPED,
)

logger = get_logger(__name__)


class NgrokAdapter:
    """ngrok tunnel provider.

    Exposes the local API port on a public ngrok URL.
    Requires ``pyngrok`` to be installed (optional dependency).

    All ngrok calls are blocking, so they are offloaded to a
    worker thread via ``asyncio.to_thread`` to keep the event
    loop responsive.

    Args:
        auth_token_env: Environment variable holding the ngrok auth
            token (optional; free tier works without a token for
            limited use).
        port: Local port to tunnel (default 8000).
    """

    def __init__(
        self,
        *,
        auth_token_env: str = "NGROK_AUTHTOKEN",  # noqa: S107
        port: int = 8000,
    ) -> None:
        self._auth_token_env = auth_token_env
        self._port = port
        self._public_url: str | None = None
        self._tunnel: object | None = None

    async def start(self) -> str:
        """Start the ngrok tunnel.

        Returns:
            The public URL.

        Raises:
            TunnelError: If ngrok is not installed or fails to start.
        """
        try:
            from pyngrok import (  # type: ignore[import-not-found]  # noqa: PLC0415
                conf,
                ngrok,
            )
        except ImportError as exc:
            logger.warning(
                TUNNEL_ERROR,
                error="pyngrok not installed",
                exc_info=True,
            )
            msg = (
                "pyngrok is not installed. Install it with "
                "'pip install pyngrok' to use the tunnel feature."
            )
            raise TunnelError(msg) from exc

        auth_token = os.environ.get(self._auth_token_env, "").strip()
        if auth_token:
            conf.get_default().auth_token = auth_token

        try:
            tunnel = await asyncio.to_thread(ngrok.connect, self._port, "http")
            self._tunnel = tunnel
            self._public_url = str(tunnel.public_url)
        except Exception as exc:
            logger.exception(TUNNEL_ERROR, error=str(exc))
            msg = f"Failed to start ngrok tunnel: {exc}"
            raise TunnelError(msg) from exc

        logger.info(
            TUNNEL_STARTED,
            public_url=self._public_url,
            port=self._port,
            note="tunnel exposes localhost publicly",
        )
        return self._public_url

    async def stop(self) -> None:
        """Stop the ngrok tunnel."""
        if self._tunnel is None:
            return
        try:
            from pyngrok import ngrok  # noqa: PLC0415

            await asyncio.to_thread(ngrok.disconnect, self._public_url)
        except Exception as exc:
            logger.exception(
                TUNNEL_ERROR,
                error=f"failed to disconnect: {exc}",
                exc_type=type(exc).__name__,
            )
        self._tunnel = None
        self._public_url = None
        logger.info(TUNNEL_STOPPED)

    async def get_url(self) -> str | None:
        """Return the current public URL, or ``None`` if stopped."""
        return self._public_url
