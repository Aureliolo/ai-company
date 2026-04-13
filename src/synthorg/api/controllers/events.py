"""Event stream and interrupt controllers.

Provides SSE event streaming at ``/events/stream`` and a polling
fallback for interrupts at ``/interrupts``.
"""

import asyncio
import json as _json
from collections.abc import AsyncIterator  # noqa: TC003
from datetime import UTC, datetime
from typing import Annotated, Any

from litestar import Controller, Request, get, post
from litestar.datastructures import State  # noqa: TC002
from litestar.params import Parameter
from litestar.response import ServerSentEvent
from pydantic import BaseModel, ConfigDict, Field

from synthorg.api.auth.models import AuthenticatedUser
from synthorg.api.dto import ApiResponse
from synthorg.api.errors import NotFoundError, UnauthorizedError
from synthorg.api.guards import require_approval_roles, require_read_access
from synthorg.api.path_params import QUERY_MAX_LENGTH, PathId
from synthorg.api.state import AppState  # noqa: TC001
from synthorg.communication.event_stream.interrupt import (
    InterruptResolution,
    InterruptStore,
    ResumeDecision,
)
from synthorg.communication.event_stream.stream import EventStreamHub  # noqa: TC001
from synthorg.communication.event_stream.types import StreamEvent  # noqa: TC001
from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.event_stream import (
    EVENT_STREAM_CLIENT_CONNECTED,
    EVENT_STREAM_CLIENT_DISCONNECTED,
    EVENT_STREAM_INTERRUPT_NOT_FOUND,
)

logger = get_logger(__name__)

_SSE_KEEPALIVE_SECONDS = 30.0


# ── DTOs ─────────────────────────────────────────────────────────


class ResumeInterruptRequest(BaseModel):
    """Request body for resuming an interrupt."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    decision: ResumeDecision | None = Field(
        default=None,
        description="Approval decision (TOOL_APPROVAL only)",
    )
    feedback: NotBlankStr | None = Field(
        default=None,
        description="Feedback text (TOOL_APPROVAL only)",
    )
    response: NotBlankStr | None = Field(
        default=None,
        description="Clarification response (INFO_REQUEST only)",
    )


class InterruptResponse(BaseModel):
    """Interrupt item returned by the polling API."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    id: NotBlankStr
    type: str
    session_id: NotBlankStr
    agent_id: NotBlankStr
    created_at: str
    timeout_seconds: float
    tool_name: NotBlankStr | None = None
    evidence_package_id: NotBlankStr | None = None
    question: NotBlankStr | None = None
    context_snippet: NotBlankStr | None = None


# ── Helpers ──────────────────────────────────────────────────────


def _require_hub(app_state: AppState) -> EventStreamHub:
    hub = app_state.event_stream_hub
    if hub is None:
        msg = "Event stream not configured"
        raise NotFoundError(msg)
    return hub


def _require_interrupt_store(app_state: AppState) -> InterruptStore:
    store = app_state.interrupt_store
    if store is None:
        msg = "Interrupt store not configured"
        raise NotFoundError(msg)
    return store


def _require_auth(request: Request[Any, Any, Any]) -> AuthenticatedUser:
    auth_user = request.scope.get("user")
    if not isinstance(auth_user, AuthenticatedUser):
        msg = "Authentication required"
        raise UnauthorizedError(msg)
    return auth_user


# ── SSE stream ───────────────────────────────────────────────────


async def _sse_event_stream(
    hub: EventStreamHub,
    session_id: str,
) -> AsyncIterator[dict[str, str]]:
    """Yield SSE events from the hub for the given session."""
    queue = hub.subscribe(session_id)
    logger.info(
        EVENT_STREAM_CLIENT_CONNECTED,
        session_id=session_id,
    )
    try:
        while True:
            try:
                event: StreamEvent = await asyncio.wait_for(
                    queue.get(),
                    timeout=_SSE_KEEPALIVE_SECONDS,
                )
                yield {
                    "event": event.type.value,
                    "data": _json.dumps(event.model_dump(mode="json")),
                }
            except TimeoutError:
                yield {"event": "keepalive", "data": "{}"}
    finally:
        hub.unsubscribe(session_id, queue)
        logger.info(
            EVENT_STREAM_CLIENT_DISCONNECTED,
            session_id=session_id,
        )


# ── Controllers ──────────────────────────────────────────────────


class EventStreamController(Controller):
    """AG-UI SSE event stream and interrupt resume."""

    path = "/events"
    tags = ("events",)

    @get(
        "/stream",
        media_type="text/event-stream",
        guards=[require_read_access],
    )
    async def stream(
        self,
        state: State,
        session_id: Annotated[
            str,
            Parameter(max_length=QUERY_MAX_LENGTH),
        ],
    ) -> ServerSentEvent:
        """SSE stream of AG-UI events for a session.

        Args:
            state: Application state.
            session_id: Session to subscribe to.

        Returns:
            SSE stream of projected events.
        """
        app_state: AppState = state.app_state
        hub = _require_hub(app_state)
        return ServerSentEvent(content=_sse_event_stream(hub, session_id))

    @post(
        "/resume/{interrupt_id:str}",
        guards=[require_approval_roles],
        status_code=200,
    )
    async def resume_interrupt(
        self,
        state: State,
        interrupt_id: PathId,
        data: ResumeInterruptRequest,
        request: Request[Any, Any, Any],
    ) -> ApiResponse[dict[str, str]]:
        """Resume a pending interrupt.

        Args:
            state: Application state.
            interrupt_id: Interrupt to resume.
            data: Resume payload.
            request: The incoming HTTP request.

        Returns:
            Confirmation envelope.
        """
        app_state: AppState = state.app_state
        store = _require_interrupt_store(app_state)
        auth_user = _require_auth(request)

        interrupt = await store.get(interrupt_id)
        if interrupt is None:
            logger.warning(
                EVENT_STREAM_INTERRUPT_NOT_FOUND,
                interrupt_id=interrupt_id,
            )
            msg = f"Interrupt {interrupt_id!r} not found"
            raise NotFoundError(msg)

        resolution = InterruptResolution(
            interrupt_id=interrupt_id,
            decision=data.decision,
            feedback=data.feedback,
            response=data.response,
            resolved_at=datetime.now(UTC),
            resolved_by=auth_user.username,
        )
        await store.resolve(resolution)

        return ApiResponse(data={"status": "resumed"})


class InterruptController(Controller):
    """Polling fallback for interrupt management."""

    path = "/interrupts"
    tags = ("interrupts",)

    @get(guards=[require_read_access])
    async def list_interrupts(
        self,
        state: State,
        session_id: Annotated[
            str | None,
            Parameter(max_length=QUERY_MAX_LENGTH),
        ] = None,
    ) -> ApiResponse[tuple[InterruptResponse, ...]]:
        """List pending interrupts.

        Args:
            state: Application state.
            session_id: Optional session filter.

        Returns:
            List of pending interrupts.
        """
        app_state: AppState = state.app_state
        store = _require_interrupt_store(app_state)
        pending = await store.list_pending(session_id=session_id)
        items = tuple(
            InterruptResponse(
                id=i.id,
                type=i.type.value,
                session_id=i.session_id,
                agent_id=i.agent_id,
                created_at=i.created_at.isoformat(),
                timeout_seconds=i.timeout_seconds,
                tool_name=i.tool_name,
                evidence_package_id=i.evidence_package_id,
                question=i.question,
                context_snippet=i.context_snippet,
            )
            for i in pending
        )
        return ApiResponse(data=items)

    @post(
        "/{interrupt_id:str}/resume",
        guards=[require_approval_roles],
        status_code=200,
    )
    async def resume(
        self,
        state: State,
        interrupt_id: PathId,
        data: ResumeInterruptRequest,
        request: Request[Any, Any, Any],
    ) -> ApiResponse[dict[str, str]]:
        """Resume a pending interrupt via polling API.

        Args:
            state: Application state.
            interrupt_id: Interrupt to resume.
            data: Resume payload.
            request: The incoming HTTP request.

        Returns:
            Confirmation envelope.
        """
        app_state: AppState = state.app_state
        store = _require_interrupt_store(app_state)
        auth_user = _require_auth(request)

        interrupt = await store.get(interrupt_id)
        if interrupt is None:
            logger.warning(
                EVENT_STREAM_INTERRUPT_NOT_FOUND,
                interrupt_id=interrupt_id,
            )
            msg = f"Interrupt {interrupt_id!r} not found"
            raise NotFoundError(msg)

        resolution = InterruptResolution(
            interrupt_id=interrupt_id,
            decision=data.decision,
            feedback=data.feedback,
            response=data.response,
            resolved_at=datetime.now(UTC),
            resolved_by=auth_user.username,
        )
        await store.resolve(resolution)

        return ApiResponse(data={"status": "resumed"})
