"""OAuth 2.1 device authorization flow (RFC 8628)."""

import asyncio
import json
from datetime import UTC, datetime, timedelta

import httpx

from synthorg.integrations.connections.models import OAuthToken
from synthorg.integrations.errors import (
    DeviceFlowTimeoutError,
    TokenExchangeFailedError,
)
from synthorg.observability import get_logger
from synthorg.observability.events.integrations import (
    OAUTH_DEVICE_FLOW_GRANTED,
    OAUTH_DEVICE_FLOW_POLLING,
    OAUTH_DEVICE_FLOW_STARTED,
    OAUTH_DEVICE_FLOW_TIMEOUT,
    OAUTH_TOKEN_EXCHANGE_FAILED,
)

logger = get_logger(__name__)


class DeviceFlowResult:
    """Result of initiating a device flow.

    Attributes:
        device_code: The device code for polling.
        user_code: The code the user enters at the verification URL.
        verification_uri: URL where the user authorizes.
        verification_uri_complete: Pre-filled URL (if available).
        interval: Polling interval in seconds.
        expires_in: Seconds until the device code expires.
    """

    __slots__ = (
        "device_code",
        "expires_in",
        "interval",
        "user_code",
        "verification_uri",
        "verification_uri_complete",
    )

    def __init__(  # noqa: PLR0913
        self,
        *,
        device_code: str,
        user_code: str,
        verification_uri: str,
        verification_uri_complete: str = "",
        interval: int = 5,
        expires_in: int = 600,
    ) -> None:
        self.device_code = device_code
        self.user_code = user_code
        self.verification_uri = verification_uri
        self.verification_uri_complete = verification_uri_complete
        self.interval = interval
        self.expires_in = expires_in


class DeviceFlow:
    """OAuth 2.1 device authorization flow (RFC 8628).

    Designed for CLI/headless use where the user cannot interact
    with a browser redirect.  The user enters a code at a URL
    displayed by the application.
    """

    @property
    def grant_type(self) -> str:
        """OAuth grant type identifier."""
        return "urn:ietf:params:oauth:grant-type:device_code"

    @property
    def supports_refresh(self) -> bool:
        """Whether this flow produces refresh tokens."""
        return True

    async def request_device_code(
        self,
        *,
        device_authorization_url: str,
        client_id: str,
        scopes: tuple[str, ...] = (),
    ) -> DeviceFlowResult:
        """Request a device code from the authorization server.

        Args:
            device_authorization_url: The device authorization endpoint.
            client_id: OAuth client ID.
            scopes: Requested scopes.

        Returns:
            A ``DeviceFlowResult`` with user code and verification URL.

        Raises:
            TokenExchangeFailedError: If the request fails.
        """
        payload: dict[str, str] = {"client_id": client_id}
        if scopes:
            payload["scope"] = " ".join(scopes)

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    device_authorization_url,
                    data=payload,
                )
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            logger.exception(
                OAUTH_TOKEN_EXCHANGE_FAILED,
                error=str(exc),
            )
            msg = f"Device code request failed: {exc}"
            raise TokenExchangeFailedError(msg) from exc

        # user_code is an active credential -- do not log it at
        # INFO. Only the verification URI is safe to surface.
        logger.info(
            OAUTH_DEVICE_FLOW_STARTED,
            verification_uri=data.get("verification_uri"),
        )
        return DeviceFlowResult(
            device_code=str(data["device_code"]),
            user_code=str(data["user_code"]),
            verification_uri=str(data["verification_uri"]),
            verification_uri_complete=str(
                data.get("verification_uri_complete", ""),
            ),
            interval=int(data.get("interval", 5)),
            expires_in=int(data.get("expires_in", 600)),
        )

    async def poll_for_token(
        self,
        *,
        token_url: str,
        client_id: str,
        device_code: str,
        interval: int = 5,
        max_wait_seconds: int = 600,
    ) -> OAuthToken:
        """Poll the token endpoint until the user authorizes.

        Args:
            token_url: Token endpoint URL.
            client_id: OAuth client ID.
            device_code: Device code from ``request_device_code``.
            interval: Polling interval in seconds.
            max_wait_seconds: Max seconds to wait.

        Returns:
            The granted ``OAuthToken``.

        Raises:
            DeviceFlowTimeoutError: If the user does not authorize
                within the timeout.
            TokenExchangeFailedError: On unexpected errors.
        """
        payload = {
            "grant_type": self.grant_type,
            "client_id": client_id,
            "device_code": device_code,
        }
        deadline = datetime.now(UTC) + timedelta(seconds=max_wait_seconds)
        poll_interval = interval

        while datetime.now(UTC) < deadline:
            logger.debug(OAUTH_DEVICE_FLOW_POLLING, interval=poll_interval)
            await asyncio.sleep(poll_interval)

            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.post(token_url, data=payload)
                    data = resp.json()
            except (httpx.HTTPError, json.JSONDecodeError) as exc:
                logger.exception(
                    OAUTH_TOKEN_EXCHANGE_FAILED,
                    error=str(exc),
                )
                msg = f"Device flow polling failed: {exc}"
                raise TokenExchangeFailedError(msg) from exc

            error = data.get("error")
            if error == "authorization_pending":
                continue
            if error == "slow_down":
                poll_interval += 5
                continue
            if error == "expired_token":
                break
            if error:
                msg = f"Device flow error: {error}"
                raise TokenExchangeFailedError(msg)

            access_token = data.get("access_token", "")
            if access_token:
                logger.info(OAUTH_DEVICE_FLOW_GRANTED)
                expires_in = data.get("expires_in")
                expires_at = None
                if isinstance(expires_in, int) and expires_in > 0:
                    expires_at = datetime.now(UTC) + timedelta(
                        seconds=expires_in,
                    )
                refresh = data.get("refresh_token")
                return OAuthToken(
                    access_token=str(access_token),
                    refresh_token=(str(refresh) if refresh else None),
                    token_type=str(
                        data.get("token_type", "Bearer"),
                    ),
                    expires_at=expires_at,
                    scope_granted=str(data.get("scope", "")),
                )

        logger.warning(
            OAUTH_DEVICE_FLOW_TIMEOUT,
            max_wait_seconds=max_wait_seconds,
        )
        msg = f"Device flow timed out after {max_wait_seconds}s"
        raise DeviceFlowTimeoutError(msg)
