"""Client simulation CRUD endpoints at /clients."""

from typing import Any

from litestar import Controller, Request, delete, get, patch, post
from litestar.datastructures import State  # noqa: TC002
from pydantic import BaseModel, ConfigDict, Field

from synthorg.api.channels import CHANNEL_CLIENTS, publish_ws_event
from synthorg.api.dto import ApiResponse, PaginatedResponse
from synthorg.api.errors import ConflictError, NotFoundError
from synthorg.api.guards import require_read_access, require_write_access
from synthorg.api.pagination import PaginationLimit, PaginationOffset, paginate
from synthorg.api.state import AppState  # noqa: TC001
from synthorg.api.ws_models import WsEventType
from synthorg.client.ai_client import AIClient
from synthorg.client.feedback.scored import ScoredFeedback
from synthorg.client.generators.procedural import ProceduralGenerator
from synthorg.client.models import ClientProfile
from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.observability import get_logger

logger = get_logger(__name__)


class CreateClientRequest(BaseModel):
    """Request payload for creating a client."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    client_id: NotBlankStr = Field(description="Unique client identifier")
    name: NotBlankStr = Field(description="Human-readable name")
    persona: NotBlankStr = Field(description="Persona description")
    expertise_domains: tuple[NotBlankStr, ...] = Field(default=())
    strictness_level: float = Field(default=0.5, ge=0.0, le=1.0)


class UpdateClientRequest(BaseModel):
    """Request payload for updating a client."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    name: NotBlankStr | None = Field(default=None)
    persona: NotBlankStr | None = Field(default=None)
    expertise_domains: tuple[NotBlankStr, ...] | None = Field(default=None)
    strictness_level: float | None = Field(default=None, ge=0.0, le=1.0)


def _build_default_client(profile: ClientProfile) -> AIClient:
    """Construct a default AI client backing for a profile."""
    return AIClient(
        profile=profile,
        generator=ProceduralGenerator(seed=abs(hash(profile.client_id)) & 0xFFFF),
        feedback=ScoredFeedback(
            client_id=profile.client_id,
            passing_score=0.5,
            strictness_multiplier=max(0.1, profile.strictness_level * 2),
        ),
    )


def _publish_client_event(
    request: Request[Any, Any, Any],
    event_type: WsEventType,
    profile: ClientProfile,
) -> None:
    """Best-effort publish a client lifecycle event."""
    publish_ws_event(
        request,
        event_type,
        CHANNEL_CLIENTS,
        {
            "client_id": profile.client_id,
            "name": profile.name,
            "strictness_level": profile.strictness_level,
        },
    )


class ClientController(Controller):
    """Client simulation CRUD endpoints."""

    path = "/clients"
    tags = ("clients",)
    guards = [require_read_access]  # noqa: RUF012

    @get()
    async def list_clients(
        self,
        state: State,
        offset: PaginationOffset = 0,
        limit: PaginationLimit = 50,
    ) -> PaginatedResponse[ClientProfile]:
        """List all configured clients (paginated)."""
        app_state: AppState = state.app_state
        sim_state = app_state.client_simulation_state
        profiles = await sim_state.pool.list_profiles()
        page, meta = paginate(profiles, offset=offset, limit=limit)
        return PaginatedResponse(data=page, pagination=meta)

    @get("/{client_id:str}")
    async def get_client(
        self,
        state: State,
        client_id: str,
    ) -> ApiResponse[ClientProfile]:
        """Return a single client profile by id.

        Raises:
            NotFoundError: If the client is not known.
        """
        app_state: AppState = state.app_state
        sim_state = app_state.client_simulation_state
        try:
            profile = await sim_state.pool.get_profile(client_id)
        except KeyError as exc:
            logger.warning("client.not_found", client_id=client_id)
            msg = f"Client {client_id!r} not found"
            raise NotFoundError(msg) from exc
        return ApiResponse(data=profile)

    @post("/", guards=[require_write_access], status_code=201)
    async def create_client(
        self,
        request: Request[Any, Any, Any],
        state: State,
        data: CreateClientRequest,
    ) -> ApiResponse[ClientProfile]:
        """Create a new client with a default AI backing.

        Raises:
            ConflictError: If the client id already exists.
        """
        app_state: AppState = state.app_state
        sim_state = app_state.client_simulation_state
        existing_profiles = await sim_state.pool.list_profiles()
        if any(p.client_id == data.client_id for p in existing_profiles):
            msg = f"Client {data.client_id!r} already exists"
            raise ConflictError(msg)
        profile = ClientProfile(
            client_id=data.client_id,
            name=data.name,
            persona=data.persona,
            expertise_domains=data.expertise_domains,
            strictness_level=data.strictness_level,
        )
        client = _build_default_client(profile)
        await sim_state.pool.add(profile=profile, client=client)
        _publish_client_event(request, WsEventType.CLIENT_CREATED, profile)
        return ApiResponse(data=profile)

    @patch("/{client_id:str}", guards=[require_write_access])
    async def update_client(
        self,
        request: Request[Any, Any, Any],
        state: State,
        client_id: str,
        data: UpdateClientRequest,
    ) -> ApiResponse[ClientProfile]:
        """Update fields on an existing client profile.

        Raises:
            NotFoundError: If the client is not known.
        """
        app_state: AppState = state.app_state
        sim_state = app_state.client_simulation_state
        try:
            current = await sim_state.pool.get_profile(client_id)
        except KeyError as exc:
            msg = f"Client {client_id!r} not found"
            raise NotFoundError(msg) from exc

        updates: dict[str, object] = {}
        if data.name is not None:
            updates["name"] = data.name
        if data.persona is not None:
            updates["persona"] = data.persona
        if data.expertise_domains is not None:
            updates["expertise_domains"] = data.expertise_domains
        if data.strictness_level is not None:
            updates["strictness_level"] = data.strictness_level
        updated = current.model_copy(update=updates)
        new_client = _build_default_client(updated)
        await sim_state.pool.add(profile=updated, client=new_client)
        _publish_client_event(request, WsEventType.CLIENT_UPDATED, updated)
        return ApiResponse(data=updated)

    @delete("/{client_id:str}", guards=[require_write_access])
    async def delete_client(
        self,
        request: Request[Any, Any, Any],
        state: State,
        client_id: str,
    ) -> None:
        """Remove a client from the pool.

        Raises:
            NotFoundError: If the client is not known.
        """
        app_state: AppState = state.app_state
        sim_state = app_state.client_simulation_state
        try:
            profile = await sim_state.pool.remove(client_id)
        except KeyError as exc:
            msg = f"Client {client_id!r} not found"
            raise NotFoundError(msg) from exc
        _publish_client_event(request, WsEventType.CLIENT_DELETED, profile)
