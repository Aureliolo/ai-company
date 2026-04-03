"""Uvicorn server runner.

Provides a convenience function to start the API server
with settings from ``RootConfig``.
"""

from typing import TYPE_CHECKING, Any

import uvicorn

from synthorg.api.app import create_app
from synthorg.observability import get_logger
from synthorg.observability.events.api import (
    API_APP_STARTUP,
    API_TLS_CONFIGURED,
)

if TYPE_CHECKING:
    from synthorg.config.schema import RootConfig

logger = get_logger(__name__)


def run_server(config: RootConfig) -> None:
    """Create and run the Litestar app via uvicorn.

    Backend services are auto-wired by ``create_app()`` from
    configuration and environment variables (e.g. ``SYNTHORG_DB_PATH``).
    Explicit service injection is only needed for testing.

    Args:
        config: Root company configuration containing server
            settings.
    """
    api_config = config.api
    server = api_config.server

    logger.info(
        API_APP_STARTUP,
        host=server.host,
        port=server.port,
        workers=server.workers,
    )

    ws_ping: float | None = (
        server.ws_ping_interval if server.ws_ping_interval > 0 else None
    )
    ws_timeout: float | None = (
        server.ws_ping_timeout if server.ws_ping_timeout > 0 else None
    )

    ssl_kwargs: dict[str, Any] = {}
    if server.ssl_certfile:
        ssl_kwargs["ssl_certfile"] = server.ssl_certfile
        ssl_kwargs["ssl_keyfile"] = server.ssl_keyfile
        if server.ssl_ca_certs:
            ssl_kwargs["ssl_ca_certs"] = server.ssl_ca_certs
        logger.info(
            API_TLS_CONFIGURED,
            certfile=server.ssl_certfile,
        )

    proxy_kwargs: dict[str, Any] = {}
    if server.trusted_proxies:
        proxy_kwargs["forwarded_allow_ips"] = ",".join(
            server.trusted_proxies,
        )
        proxy_kwargs["proxy_headers"] = True

    app = create_app(config=config)
    uvicorn.run(
        app,
        host=server.host,
        port=server.port,
        workers=server.workers,
        reload=server.reload,
        ws_ping_interval=ws_ping,
        ws_ping_timeout=ws_timeout,
        access_log=False,
        log_config=None,
        **ssl_kwargs,
        **proxy_kwargs,
    )
