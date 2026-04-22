"""Client request lifecycle endpoints at /requests."""

from typing import Any

from litestar import Controller, Request, get, post
from litestar.datastructures import State  # noqa: TC002
from pydantic import BaseModel, ConfigDict, Field

from synthorg.api.channels import CHANNEL_REQUESTS, publish_ws_event
from synthorg.api.dto import ApiResponse, PaginatedResponse
from synthorg.api.errors import ConflictError, NotFoundError
from synthorg.api.guards import require_read_access, require_write_access
from synthorg.api.pagination import PaginationLimit, PaginationOffset, paginate
from synthorg.api.rate_limits import per_op_rate_limit
from synthorg.api.state import AppState  # noqa: TC001
from synthorg.api.ws_models import WsEventType
from synthorg.client.models import (
    ClientRequest,
    RequestStatus,
    TaskRequirement,
)
from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.observability import get_logger

logger = get_logger(__name__)


class CreateRequestPayload(BaseModel):
    """Request payload for submitting a new client request."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    client_id: NotBlankStr = Field(description="Requesting client id")
    requirement: TaskRequirement = Field(description="Task requirement")


class RejectionPayload(BaseModel):
    """Payload carrying a rejection reason."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    reason: NotBlankStr = Field(description="Reason for rejection")


class ScopingPayload(BaseModel):
    """Payload carrying scoping notes and an optional refined requirement."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    notes: NotBlankStr = Field(description="Scoping notes from the reviewer")
    refined_title: NotBlankStr | None = Field(default=None)
    refined_description: NotBlankStr | None = Field(default=None)
    refined_acceptance_criteria: tuple[NotBlankStr, ...] | None = Field(
        default=None,
    )


def _publish(
    request: Request[Any, Any, Any],
    event_type: WsEventType,
    client_request: ClientRequest,
) -> None:
    """Best-effort publish a request lifecycle event."""
    publish_ws_event(
        request,
        event_type,
        CHANNEL_REQUESTS,
        {
            "request_id": client_request.request_id,
            "client_id": client_request.client_id,
            "status": client_request.status.value,
        },
    )


class RequestController(Controller):
    """Client request lifecycle endpoints."""

    path = "/requests"
    tags = ("requests",)
    guards = [require_read_access]  # noqa: RUF012

    @get()
    async def list_requests(
        self,
        state: State,
        status: RequestStatus | None = None,
        offset: PaginationOffset = 0,
        limit: PaginationLimit = 50,
    ) -> PaginatedResponse[ClientRequest]:
        """List stored client requests, optionally filtered by status."""
        app_state: AppState = state.app_state
        sim_state = app_state.client_simulation_state
        all_requests = await sim_state.request_store.list_all()
        if status is not None:
            all_requests = tuple(r for r in all_requests if r.status == status)
        page, meta = paginate(all_requests, offset=offset, limit=limit)
        return PaginatedResponse(data=page, pagination=meta)

    @get("/{request_id:str}")
    async def get_request(
        self,
        state: State,
        request_id: str,
    ) -> ApiResponse[ClientRequest]:
        """Return a single request by id."""
        app_state: AppState = state.app_state
        sim_state = app_state.client_simulation_state
        try:
            stored = await sim_state.request_store.get(request_id)
        except KeyError as exc:
            msg = f"Request {request_id!r} not found"
            raise NotFoundError(msg) from exc
        return ApiResponse(data=stored)

    @post(
        "/",
        guards=[
            require_write_access,
            per_op_rate_limit(
                "requests.create",
                max_requests=30,
                window_seconds=60,
                key="user",
            ),
        ],
        status_code=201,
    )
    async def submit_request(
        self,
        request: Request[Any, Any, Any],
        state: State,
        data: CreateRequestPayload,
    ) -> ApiResponse[ClientRequest]:
        """Persist a new ``ClientRequest`` in SUBMITTED status."""
        app_state: AppState = state.app_state
        sim_state = app_state.client_simulation_state
        try:
            await sim_state.pool.get_profile(data.client_id)
        except KeyError as exc:
            msg = f"Unknown client {data.client_id!r}"
            raise NotFoundError(msg) from exc
        client_request = ClientRequest(
            client_id=data.client_id,
            requirement=data.requirement,
        )
        await sim_state.request_store.save(client_request)
        _publish(request, WsEventType.REQUEST_SUBMITTED, client_request)
        return ApiResponse(data=client_request)

    @post(
        "/{request_id:str}/scope",
        guards=[
            require_write_access,
            per_op_rate_limit(
                "requests.update_scope",
                max_requests=50,
                window_seconds=60,
                key="user",
            ),
        ],
    )
    async def scope_request(
        self,
        request: Request[Any, Any, Any],
        state: State,
        request_id: str,
        data: ScopingPayload,
    ) -> ApiResponse[ClientRequest]:
        """Walk a request into SCOPING status with scoping notes.

        Accepts requests in ``SUBMITTED`` (walked through
        ``TRIAGING``) or ``TRIAGING`` state. Rejects any other
        source status with a 409.

        Raises:
            NotFoundError: If the request is not known.
            ConflictError: If the request is not in a scopable state.
        """
        app_state: AppState = state.app_state
        sim_state = app_state.client_simulation_state
        try:
            stored = await sim_state.request_store.get(request_id)
        except KeyError as exc:
            msg = f"Request {request_id!r} not found"
            raise NotFoundError(msg) from exc
        if stored.status not in {RequestStatus.SUBMITTED, RequestStatus.TRIAGING}:
            msg = (
                f"Request {request_id!r} cannot be scoped from "
                f"status {stored.status.value!r}"
            )
            raise ConflictError(msg)
        metadata = dict(stored.metadata)
        metadata["scoping_notes"] = data.notes
        requirement = stored.requirement
        overrides: dict[str, Any] = {}
        if (
            data.refined_title is not None
            or data.refined_description is not None
            or data.refined_acceptance_criteria is not None
        ):
            overrides["requirement"] = requirement.model_copy(
                update={
                    k: v
                    for k, v in {
                        "title": data.refined_title,
                        "description": data.refined_description,
                        "acceptance_criteria": data.refined_acceptance_criteria,
                    }.items()
                    if v is not None
                },
            )
        walked = stored
        if walked.status == RequestStatus.SUBMITTED:
            walked = walked.with_status(
                RequestStatus.TRIAGING,
                metadata=metadata,
            )
        scoped = walked.with_status(
            RequestStatus.SCOPING,
            metadata=metadata,
            **overrides,
        )
        await sim_state.request_store.save(scoped)
        _publish(request, WsEventType.REQUEST_SCOPED, scoped)
        return ApiResponse(data=scoped)

    @post(
        "/{request_id:str}/approve",
        guards=[
            require_write_access,
            per_op_rate_limit(
                "requests.approve",
                max_requests=100,
                window_seconds=60,
                key="user",
            ),
        ],
    )
    async def approve_request(
        self,
        request: Request[Any, Any, Any],
        state: State,
        request_id: str,
    ) -> ApiResponse[ClientRequest]:
        """Walk a request into the ``TASK_CREATED`` terminal state.

        Accepts requests in ``SUBMITTED`` (runs the full intake
        engine) or ``SCOPING`` (finalizes after a prior manual
        scope call). Any other status produces a 409.

        Raises:
            NotFoundError: If the request is not known.
            ConflictError: If the request cannot be approved from
                its current state or no intake engine is configured.
        """
        app_state: AppState = state.app_state
        sim_state = app_state.client_simulation_state
        try:
            stored = await sim_state.request_store.get(request_id)
        except KeyError as exc:
            msg = f"Request {request_id!r} not found"
            raise NotFoundError(msg) from exc
        if stored.status not in {RequestStatus.SUBMITTED, RequestStatus.SCOPING}:
            msg = (
                f"Request {request_id!r} cannot be approved from "
                f"status {stored.status.value!r}"
            )
            raise ConflictError(msg)
        if sim_state.intake_engine is None:
            msg = "Intake engine not configured"
            raise ConflictError(msg)
        if stored.status is RequestStatus.SUBMITTED:
            final, _ = await sim_state.intake_engine.process(stored)
        else:
            final, _ = await sim_state.intake_engine.finalize_scoped(stored)
        await sim_state.request_store.save(final)
        _publish(request, WsEventType.REQUEST_APPROVED, final)
        return ApiResponse(data=final)

    @post(
        "/{request_id:str}/reject",
        guards=[
            require_write_access,
            per_op_rate_limit(
                "requests.reject",
                max_requests=100,
                window_seconds=60,
                key="user",
            ),
        ],
    )
    async def reject_request(
        self,
        request: Request[Any, Any, Any],
        state: State,
        request_id: str,
        data: RejectionPayload,
    ) -> ApiResponse[ClientRequest]:
        """Cancel a request, recording the rejection reason."""
        app_state: AppState = state.app_state
        sim_state = app_state.client_simulation_state
        try:
            stored = await sim_state.request_store.get(request_id)
        except KeyError as exc:
            msg = f"Request {request_id!r} not found"
            raise NotFoundError(msg) from exc
        if stored.status in {RequestStatus.TASK_CREATED, RequestStatus.CANCELLED}:
            msg = (
                f"Request {request_id!r} cannot be rejected from "
                f"status {stored.status.value!r}"
            )
            raise ConflictError(msg)
        metadata = dict(stored.metadata)
        metadata["rejection_reason"] = data.reason
        cancelled = stored.with_status(
            RequestStatus.CANCELLED,
            metadata=metadata,
        )
        await sim_state.request_store.save(cancelled)
        _publish(request, WsEventType.REQUEST_REJECTED, cancelled)
        return ApiResponse(data=cancelled)
