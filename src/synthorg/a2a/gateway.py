"""A2A JSON-RPC 2.0 gateway controller.

Handles inbound A2A requests dispatched by method name:
``message/send``, ``message/stream``, ``tasks/get``,
``tasks/cancel``.  All inbound requests are validated against
the peer allowlist and connection catalog credentials.
"""

import json
from typing import Any

from litestar import Controller, Request, post
from litestar.datastructures import State  # noqa: TC002
from litestar.response import Response

from synthorg.a2a.models import (
    A2A_PAYLOAD_TOO_LARGE,
    A2A_PEER_NOT_ALLOWED,
    A2A_TASK_NOT_CANCELABLE,
    A2A_TASK_NOT_FOUND,
    JSONRPC_INTERNAL_ERROR,
    JSONRPC_INVALID_PARAMS,
    JSONRPC_METHOD_NOT_FOUND,
    JSONRPC_PARSE_ERROR,
    JsonRpcErrorData,
    JsonRpcRequest,
    JsonRpcResponse,
)
from synthorg.a2a.security import validate_payload_size, validate_peer
from synthorg.a2a.task_mapper import to_a2a
from synthorg.observability import get_logger
from synthorg.observability.events.a2a import (
    A2A_INBOUND_DISPATCHED,
    A2A_INBOUND_RECEIVED,
    A2A_INBOUND_REJECTED,
    A2A_JSONRPC_METHOD_NOT_FOUND,
    A2A_JSONRPC_PARSE_ERROR,
    A2A_TASK_CANCELLED,
    A2A_TASK_CREATED,
)

logger = get_logger(__name__)

_SUPPORTED_METHODS = frozenset(
    {
        "message/send",
        "message/stream",
        "tasks/get",
        "tasks/cancel",
    }
)


def _error_response(
    request_id: str | int | None,
    code: int,
    message: str,
    *,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a JSON-RPC error response dict.

    Args:
        request_id: Echoed request ID.
        code: JSON-RPC error code.
        message: Human-readable error description.
        data: Additional error data.

    Returns:
        Serialized JSON-RPC error response.
    """
    resp = JsonRpcResponse(
        id=request_id,
        error=JsonRpcErrorData(
            code=code,
            message=message,
            data=data,
        ),
    )
    return resp.model_dump()


def _success_response(
    request_id: str | int | None,
    result: dict[str, Any],
) -> dict[str, Any]:
    """Build a JSON-RPC success response dict.

    Args:
        request_id: Echoed request ID.
        result: Success payload.

    Returns:
        Serialized JSON-RPC success response.
    """
    resp = JsonRpcResponse(id=request_id, result=result)
    return resp.model_dump()


class A2AGatewayController(Controller):
    """A2A JSON-RPC 2.0 gateway endpoint."""

    path = "/api/v1/a2a"
    tags = ["A2A"]  # noqa: RUF012

    @post(
        "/",
        summary="A2A JSON-RPC 2.0 endpoint",
        description=(
            "Receives JSON-RPC 2.0 requests and dispatches "
            "to the appropriate A2A method handler."
        ),
        status_code=200,
    )
    async def handle_jsonrpc(
        self,
        state: State,
        request: Request[Any, Any, Any],
    ) -> Response[dict[str, Any]]:
        """Dispatch an inbound JSON-RPC 2.0 request."""
        app_state = state["app_state"]
        a2a_config = app_state.config.a2a

        # Read and validate body size
        body = await request.body()
        if not validate_payload_size(
            body,
            a2a_config.max_request_body_bytes,
        ):
            return Response(
                content=_error_response(
                    None,
                    A2A_PAYLOAD_TOO_LARGE,
                    "Request body exceeds maximum size",
                ),
                media_type="application/json",
                status_code=413,
            )

        # Parse JSON-RPC envelope
        rpc_request = _parse_jsonrpc(body)
        if rpc_request is None:
            return Response(
                content=_error_response(
                    None,
                    JSONRPC_PARSE_ERROR,
                    "Invalid JSON-RPC request",
                ),
                media_type="application/json",
            )

        request_id = rpc_request.id

        logger.info(
            A2A_INBOUND_RECEIVED,
            method=rpc_request.method,
            request_id=request_id,
        )

        # Validate peer from auth header
        peer_name = _extract_peer_name(request)
        if peer_name and not validate_peer(
            peer_name,
            tuple(str(p) for p in a2a_config.allowed_peers),
        ):
            return Response(
                content=_error_response(
                    request_id,
                    A2A_PEER_NOT_ALLOWED,
                    "Peer not on allowlist",
                ),
                media_type="application/json",
                status_code=403,
            )

        return await _dispatch_method(
            app_state,
            rpc_request,
        )


def _parse_jsonrpc(body: bytes) -> JsonRpcRequest | None:
    """Parse a JSON-RPC 2.0 request from raw bytes.

    Args:
        body: Raw request body.

    Returns:
        Parsed request, or ``None`` on parse failure.
    """
    try:
        raw = json.loads(body)
        return JsonRpcRequest.model_validate(raw)
    except json.JSONDecodeError, UnicodeDecodeError:
        logger.warning(A2A_JSONRPC_PARSE_ERROR)
        return None
    except MemoryError, RecursionError:
        raise
    except Exception:
        logger.warning(A2A_JSONRPC_PARSE_ERROR, exc_info=True)
        return None


async def _dispatch_method(
    app_state: Any,
    rpc_request: JsonRpcRequest,
) -> Response[dict[str, Any]]:
    """Dispatch a validated JSON-RPC request to its handler.

    Args:
        app_state: Application state container.
        rpc_request: Validated JSON-RPC request.

    Returns:
        JSON-RPC response wrapped in an HTTP response.
    """
    request_id = rpc_request.id
    method = str(rpc_request.method)

    if method not in _SUPPORTED_METHODS:
        logger.warning(A2A_JSONRPC_METHOD_NOT_FOUND, method=method)
        return Response(
            content=_error_response(
                request_id,
                JSONRPC_METHOD_NOT_FOUND,
                f"Method not found: {method}",
            ),
            media_type="application/json",
        )

    logger.info(
        A2A_INBOUND_DISPATCHED,
        method=method,
        request_id=request_id,
    )

    handler = _METHOD_HANDLERS.get(method)
    if handler is None:
        return Response(
            content=_error_response(
                request_id,
                JSONRPC_INTERNAL_ERROR,
                "Internal error",
            ),
            media_type="application/json",
            status_code=500,
        )

    try:
        result = await handler(app_state, rpc_request)
        return Response(
            content=_success_response(request_id, result),
            media_type="application/json",
        )
    except _A2AMethodError as exc:
        return Response(
            content=_error_response(
                request_id,
                exc.code,
                exc.message,
            ),
            media_type="application/json",
            status_code=exc.http_status,
        )
    except MemoryError, RecursionError:
        raise
    except Exception:
        logger.exception(
            A2A_INBOUND_REJECTED,
            method=method,
            reason="unhandled exception",
        )
        return Response(
            content=_error_response(
                request_id,
                JSONRPC_INTERNAL_ERROR,
                "Internal error",
            ),
            media_type="application/json",
            status_code=500,
        )


def _extract_peer_name(
    request: Request[Any, Any, Any],
) -> str | None:
    """Extract the peer name from request headers.

    Looks for ``X-A2A-Peer-Name`` header first, then falls back
    to the ``Authorization`` header's bearer token prefix.

    Args:
        request: The inbound HTTP request.

    Returns:
        Peer name string, or ``None`` if not identifiable.
    """
    peer = request.headers.get("x-a2a-peer-name")
    if peer:
        return peer.strip()
    return None


class _A2AMethodError(Exception):
    """Error raised by method handlers for JSON-RPC error responses."""

    def __init__(
        self,
        code: int,
        message: str,
        *,
        http_status: int = 400,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status


async def _handle_message_send(
    app_state: Any,
    rpc_request: JsonRpcRequest,
) -> dict[str, Any]:
    """Handle ``message/send`` -- create a task from an inbound message.

    Args:
        app_state: Application state container.
        rpc_request: Parsed JSON-RPC request.

    Returns:
        Task state dict.
    """
    params = rpc_request.params
    message_data = params.get("message")
    if not message_data or not isinstance(message_data, dict):
        raise _A2AMethodError(
            JSONRPC_INVALID_PARAMS,
            "Missing or invalid 'message' parameter",
        )

    # Extract text from message parts for task description
    parts = message_data.get("parts", [])
    text_parts = [
        p.get("text", "")
        for p in parts
        if isinstance(p, dict) and p.get("type") == "text"
    ]
    description = "\n".join(text_parts) or "A2A inbound task"

    task_engine = app_state.task_engine
    if task_engine is None:
        raise _A2AMethodError(
            JSONRPC_INTERNAL_ERROR,
            "Task engine unavailable",
            http_status=503,
        )

    from uuid import uuid4 as _uuid4  # noqa: PLC0415

    from synthorg.core.enums import Priority, TaskType  # noqa: PLC0415
    from synthorg.core.task import Task  # noqa: PLC0415

    task = Task(
        id=f"a2a-{_uuid4().hex[:12]}",
        title=f"A2A: {description[:80]}",
        description=description,
        type=TaskType.ADMIN,
        priority=Priority.MEDIUM,
        project="a2a-inbound",
        created_by="a2a-gateway",
    )

    created = await task_engine.submit(task)

    logger.info(
        A2A_TASK_CREATED,
        task_id=created.id,
    )

    return {
        "id": created.id,
        "state": to_a2a(created.status).value,
    }


async def _handle_tasks_get(
    app_state: Any,
    rpc_request: JsonRpcRequest,
) -> dict[str, Any]:
    """Handle ``tasks/get`` -- retrieve task state.

    Args:
        app_state: Application state container.
        rpc_request: Parsed JSON-RPC request.

    Returns:
        Task state dict.
    """
    task_id = rpc_request.params.get("id")
    if not task_id or not isinstance(task_id, str):
        raise _A2AMethodError(
            JSONRPC_INVALID_PARAMS,
            "Missing or invalid 'id' parameter",
        )

    task_engine = app_state.task_engine
    if task_engine is None:
        raise _A2AMethodError(
            JSONRPC_INTERNAL_ERROR,
            "Task engine unavailable",
            http_status=503,
        )

    task = await task_engine.get(task_id)
    if task is None:
        raise _A2AMethodError(
            A2A_TASK_NOT_FOUND,
            f"Task '{task_id}' not found",
            http_status=404,
        )

    return {
        "id": task.id,
        "state": to_a2a(task.status).value,
    }


async def _handle_tasks_cancel(
    app_state: Any,
    rpc_request: JsonRpcRequest,
) -> dict[str, Any]:
    """Handle ``tasks/cancel`` -- cancel a running task.

    Args:
        app_state: Application state container.
        rpc_request: Parsed JSON-RPC request.

    Returns:
        Updated task state dict.
    """
    task_id = rpc_request.params.get("id")
    if not task_id or not isinstance(task_id, str):
        raise _A2AMethodError(
            JSONRPC_INVALID_PARAMS,
            "Missing or invalid 'id' parameter",
        )

    task_engine = app_state.task_engine
    if task_engine is None:
        raise _A2AMethodError(
            JSONRPC_INTERNAL_ERROR,
            "Task engine unavailable",
            http_status=503,
        )

    task = await task_engine.get(task_id)
    if task is None:
        raise _A2AMethodError(
            A2A_TASK_NOT_FOUND,
            f"Task '{task_id}' not found",
            http_status=404,
        )

    from synthorg.core.enums import TaskStatus  # noqa: PLC0415

    terminal = {
        TaskStatus.COMPLETED,
        TaskStatus.CANCELLED,
        TaskStatus.REJECTED,
    }
    if task.status in terminal:
        raise _A2AMethodError(
            A2A_TASK_NOT_CANCELABLE,
            f"Task '{task_id}' is in terminal state '{task.status.value}'",
        )

    cancelled = await task_engine.cancel(task_id)

    logger.info(A2A_TASK_CANCELLED, task_id=task_id)

    return {
        "id": cancelled.id,
        "state": to_a2a(cancelled.status).value,
    }


async def _handle_message_stream(
    app_state: Any,
    rpc_request: JsonRpcRequest,
) -> dict[str, Any]:
    """Handle ``message/stream`` -- SSE streaming placeholder.

    Full SSE streaming requires a streaming response which is
    handled separately.  This handler acknowledges the stream
    subscription request.

    Args:
        app_state: Application state container.
        rpc_request: Parsed JSON-RPC request.

    Returns:
        Stream acknowledgement dict.
    """
    task_id = rpc_request.params.get("id")
    if not task_id or not isinstance(task_id, str):
        raise _A2AMethodError(
            JSONRPC_INVALID_PARAMS,
            "Missing or invalid 'id' parameter",
        )

    task_engine = app_state.task_engine
    if task_engine is not None:
        task = await task_engine.get(task_id)
        if task is None:
            raise _A2AMethodError(
                A2A_TASK_NOT_FOUND,
                f"Task '{task_id}' not found",
                http_status=404,
            )

    return {
        "id": task_id,
        "state": "streaming",
        "stream_url": f"/api/v1/a2a/stream/{task_id}",
    }


_METHOD_HANDLERS: dict[
    str,
    Any,
] = {
    "message/send": _handle_message_send,
    "message/stream": _handle_message_stream,
    "tasks/get": _handle_tasks_get,
    "tasks/cancel": _handle_tasks_cancel,
}
