"""Outbound A2A client for delegating to external agents.

Sends JSON-RPC 2.0 requests to external A2A-compatible agents,
pulling credentials from the connection catalog and validating
outbound URLs against SSRF rules.
"""

from typing import Any
from uuid import uuid4

import httpx

from synthorg.a2a.models import (
    A2ATask,
    A2ATaskState,
    JsonRpcRequest,
    JsonRpcResponse,
)
from synthorg.observability import get_logger
from synthorg.observability.events.a2a import (
    A2A_OUTBOUND_FAILED,
    A2A_OUTBOUND_SENT,
    A2A_OUTBOUND_SSRF_BLOCKED,
)

logger = get_logger(__name__)


class A2AClientError(Exception):
    """Error raised by the outbound A2A client."""

    def __init__(self, message: str, *, peer_name: str = "") -> None:
        super().__init__(message)
        self.peer_name = peer_name


class A2AClient:
    """Outbound JSON-RPC 2.0 client for A2A federation.

    Sends requests to external A2A agents, pulling credentials
    from the connection catalog and validating URLs against SSRF
    rules.

    Args:
        connection_catalog: Connection catalog for credential
            retrieval.
        network_validator: SSRF validation (optional; when None,
            SSRF checks are skipped -- test-only).
        timeout_seconds: HTTP request timeout in seconds.
    """

    __slots__ = (
        "_catalog",
        "_network_validator",
        "_timeout",
    )

    def __init__(
        self,
        connection_catalog: Any,
        *,
        network_validator: Any | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._catalog = connection_catalog
        self._network_validator = network_validator
        self._timeout = timeout_seconds

    async def send_message(
        self,
        peer_name: str,
        message_params: dict[str, Any],
    ) -> A2ATask:
        """Send a ``message/send`` request to an external peer.

        Args:
            peer_name: Connection name of the target peer.
            message_params: JSON-RPC params for message/send.

        Returns:
            A2A task from the peer's response.

        Raises:
            A2AClientError: On connection, auth, or peer errors.
        """
        return await self._call_method(
            peer_name,
            "message/send",
            message_params,
        )

    async def get_task(
        self,
        peer_name: str,
        task_id: str,
    ) -> A2ATask:
        """Send a ``tasks/get`` request to an external peer.

        Args:
            peer_name: Connection name of the target peer.
            task_id: Remote task identifier.

        Returns:
            A2A task from the peer's response.

        Raises:
            A2AClientError: On connection or peer errors.
        """
        return await self._call_method(
            peer_name,
            "tasks/get",
            {"id": task_id},
        )

    async def cancel_task(
        self,
        peer_name: str,
        task_id: str,
    ) -> A2ATask:
        """Send a ``tasks/cancel`` request to an external peer.

        Args:
            peer_name: Connection name of the target peer.
            task_id: Remote task identifier.

        Returns:
            A2A task from the peer's response.

        Raises:
            A2AClientError: On connection or peer errors.
        """
        return await self._call_method(
            peer_name,
            "tasks/cancel",
            {"id": task_id},
        )

    async def _call_method(
        self,
        peer_name: str,
        method: str,
        params: dict[str, Any],
    ) -> A2ATask:
        """Execute a JSON-RPC call to a peer.

        Args:
            peer_name: Connection name.
            method: JSON-RPC method name.
            params: Method parameters.

        Returns:
            Parsed A2A task from the response.

        Raises:
            A2AClientError: On any failure.
        """
        conn = await self._catalog.get(peer_name)
        if conn is None:
            msg = f"A2A peer connection '{peer_name}' not found"
            raise A2AClientError(msg, peer_name=peer_name)

        base_url = conn.base_url
        if not base_url:
            msg = f"A2A peer '{peer_name}' has no base_url"
            raise A2AClientError(msg, peer_name=peer_name)

        # SSRF validation on outbound URL
        if self._network_validator is not None:
            from synthorg.tools.network_validator import (  # noqa: PLC0415
                extract_hostname,
            )

            hostname = extract_hostname(str(base_url))
            if hostname is None:
                logger.warning(
                    A2A_OUTBOUND_SSRF_BLOCKED,
                    peer_name=peer_name,
                    url=str(base_url),
                    reason="unparseable URL",
                )
                msg = f"SSRF: cannot parse URL for peer '{peer_name}'"
                raise A2AClientError(msg, peer_name=peer_name)

        # Build JSON-RPC request
        rpc_req = JsonRpcRequest(
            id=str(uuid4()),
            method=method,
            params=params,
        )

        # Pull credentials
        credentials = await self._catalog.get_credentials(peer_name)
        headers: dict[str, str] = {
            "Content-Type": "application/json",
        }
        api_key = credentials.get("api_key", "")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        url = f"{str(base_url).rstrip('/')}/api/v1/a2a"

        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
            ) as http:
                response = await http.post(
                    url,
                    json=rpc_req.model_dump(),
                    headers=headers,
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.exception(
                A2A_OUTBOUND_FAILED,
                peer_name=peer_name,
                method=method,
                error=str(exc),
            )
            msg = f"A2A outbound request to '{peer_name}' failed: {exc}"
            raise A2AClientError(msg, peer_name=peer_name) from exc

        logger.info(
            A2A_OUTBOUND_SENT,
            peer_name=peer_name,
            method=method,
        )

        # Parse JSON-RPC response
        try:
            raw = response.json()
            rpc_resp = JsonRpcResponse.model_validate(raw)
        except MemoryError, RecursionError:
            raise
        except Exception as exc:
            msg = f"Failed to parse response from '{peer_name}'"
            raise A2AClientError(msg, peer_name=peer_name) from exc

        if rpc_resp.error is not None:
            msg = (
                f"A2A peer '{peer_name}' returned error: "
                f"{rpc_resp.error.message} (code={rpc_resp.error.code})"
            )
            raise A2AClientError(msg, peer_name=peer_name)

        result = rpc_resp.result or {}
        return A2ATask(
            id=result.get("id", str(uuid4())),
            state=A2ATaskState(
                result.get("state", "submitted"),
            ),
        )
