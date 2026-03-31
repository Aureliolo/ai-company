"""User management controller -- CEO-only CRUD for human users."""

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

from litestar import Controller, Request, delete, get, patch, post
from litestar.datastructures import State  # noqa: TC002
from litestar.status_codes import HTTP_204_NO_CONTENT
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from synthorg.api.auth.config import AuthConfig
from synthorg.api.auth.models import AuthenticatedUser, User
from synthorg.api.dto import ApiResponse
from synthorg.api.errors import ApiValidationError, ConflictError, NotFoundError
from synthorg.api.guards import HumanRole, require_ceo
from synthorg.api.path_params import PathId  # noqa: TC001
from synthorg.api.state import AppState  # noqa: TC001
from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.api import (
    API_RESOURCE_CONFLICT,
    API_RESOURCE_NOT_FOUND,
    API_USER_CREATED,
    API_USER_DELETED,
    API_USER_LISTED,
    API_USER_UPDATED,
    API_VALIDATION_FAILED,
)
from synthorg.persistence.errors import QueryError

logger = get_logger(__name__)

# Derive from AuthConfig default to prevent silent divergence.
_MIN_PASSWORD_LENGTH: int = AuthConfig.model_fields["min_password_length"].default

# Roles that cannot be assigned via the user management API.
_FORBIDDEN_ROLES: frozenset[HumanRole] = frozenset({HumanRole.SYSTEM})

# Serializes CEO uniqueness check-then-act sequences.
_CEO_LOCK = asyncio.Lock()


# -- Request / Response DTOs -------------------------------------------


class CreateUserRequest(BaseModel):
    """Request body for creating a new user."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    username: NotBlankStr = Field(max_length=128)
    password: NotBlankStr = Field(max_length=128)
    role: HumanRole


class UpdateUserRoleRequest(BaseModel):
    """Request body for updating a user's role."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    role: HumanRole


class UserResponse(BaseModel):
    """Public user representation (no password hash)."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    id: NotBlankStr
    username: NotBlankStr
    role: HumanRole
    must_change_password: bool
    created_at: AwareDatetime
    updated_at: AwareDatetime


def _to_response(user: User) -> UserResponse:
    """Map a ``User`` domain model to the public ``UserResponse`` DTO."""
    return UserResponse(
        id=user.id,
        username=user.username,
        role=user.role,
        must_change_password=user.must_change_password,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


# -- Validation helpers ------------------------------------------------


def _validate_assignable_role(role: HumanRole) -> None:
    """Reject roles that cannot be assigned via the API."""
    if role in _FORBIDDEN_ROLES:
        msg = f"Cannot assign role: {role.value}"
        logger.warning(API_VALIDATION_FAILED, reason=msg)
        raise ApiValidationError(msg)


async def _get_user_or_404(
    app_state: AppState,
    user_id: str,
) -> User:
    """Fetch a user by ID, raising NotFoundError if missing."""
    user = await app_state.persistence.users.get(user_id)
    if user is None:
        msg = f"User not found: {user_id}"
        logger.warning(API_RESOURCE_NOT_FOUND, reason=msg)
        raise NotFoundError(msg)
    return user


async def _validate_ceo_create(app_state: AppState) -> None:
    """Reject creation of a second CEO."""
    ceo_count = await app_state.persistence.users.count_by_role(
        HumanRole.CEO,
    )
    if ceo_count > 0:
        msg = "A CEO user already exists"
        logger.warning(API_RESOURCE_CONFLICT, reason=msg)
        raise ConflictError(msg)


async def _validate_username_unique(
    app_state: AppState,
    username: str,
) -> None:
    """Reject duplicate usernames."""
    existing = await app_state.persistence.users.get_by_username(username)
    if existing is not None:
        msg = f"Username already taken: {username}"
        logger.warning(API_RESOURCE_CONFLICT, reason=msg)
        raise ConflictError(msg)


async def _validate_role_change(
    app_state: AppState,
    user: User,
    new_role: HumanRole,
) -> None:
    """Validate CEO-related constraints on role changes."""
    # Prevent removing the only CEO
    if user.role == HumanRole.CEO and new_role != HumanRole.CEO:
        ceo_count = await app_state.persistence.users.count_by_role(
            HumanRole.CEO,
        )
        if ceo_count <= 1:
            msg = "Cannot change the only CEO's role"
            logger.warning(API_RESOURCE_CONFLICT, reason=msg)
            raise ConflictError(msg)

    # Prevent creating a second CEO
    if new_role == HumanRole.CEO and user.role != HumanRole.CEO:
        ceo_count = await app_state.persistence.users.count_by_role(
            HumanRole.CEO,
        )
        if ceo_count > 0:
            msg = "A CEO user already exists"
            logger.warning(API_RESOURCE_CONFLICT, reason=msg)
            raise ConflictError(msg)


# -- Controller --------------------------------------------------------


class UserController(Controller):
    """CEO-only endpoints for managing human user accounts.

    All endpoints require the CEO role.
    """

    path = "/users"
    tags = ("users",)
    guards = [require_ceo]  # noqa: RUF012

    @post(status_code=201)
    async def create_user(
        self,
        state: State,
        data: CreateUserRequest,
    ) -> ApiResponse[UserResponse]:
        """Create a new user account.

        Args:
            state: Application state.
            data: User creation payload.

        Returns:
            Created user response.

        Raises:
            ApiValidationError: If the role is SYSTEM or password
                is too short.
            ConflictError: If username is taken or a second CEO is
                requested.
        """
        app_state: AppState = state.app_state

        _validate_assignable_role(data.role)

        if len(data.password) < _MIN_PASSWORD_LENGTH:
            msg = f"Password must be at least {_MIN_PASSWORD_LENGTH} characters"
            logger.warning(API_VALIDATION_FAILED, reason=msg)
            raise ApiValidationError(msg)

        async with _CEO_LOCK:
            if data.role == HumanRole.CEO:
                await _validate_ceo_create(app_state)

            await _validate_username_unique(app_state, data.username)

            now = datetime.now(UTC)
            password_hash = await app_state.auth_service.hash_password_async(
                data.password,
            )
            user = User(
                id=str(uuid.uuid4()),
                username=data.username,
                password_hash=password_hash,
                role=data.role,
                must_change_password=True,
                created_at=now,
                updated_at=now,
            )
            try:
                await app_state.persistence.users.save(user)
            except QueryError as exc:
                cause = str(exc.__cause__) if exc.__cause__ else ""
                if "users.username" in cause:
                    msg = f"Username already taken: {data.username}"
                else:
                    msg = "A CEO user already exists"
                logger.warning(API_RESOURCE_CONFLICT, reason=msg)
                raise ConflictError(msg) from exc

        logger.info(
            API_USER_CREATED,
            user_id=user.id,
            role=user.role.value,
        )
        return ApiResponse(data=_to_response(user))

    @get()
    async def list_users(
        self,
        state: State,
    ) -> ApiResponse[tuple[UserResponse, ...]]:
        """List all human users (excludes system user).

        Args:
            state: Application state.

        Returns:
            Tuple of user responses.
        """
        app_state: AppState = state.app_state
        users = await app_state.persistence.users.list_users()
        logger.debug(API_USER_LISTED, count=len(users))
        return ApiResponse(
            data=tuple(_to_response(u) for u in users),
        )

    @get("/{user_id:str}")
    async def get_user(
        self,
        state: State,
        user_id: PathId,
    ) -> ApiResponse[UserResponse]:
        """Get a user by ID.

        Args:
            state: Application state.
            user_id: User identifier.

        Returns:
            User response.

        Raises:
            NotFoundError: If the user is not found.
        """
        app_state: AppState = state.app_state
        user = await _get_user_or_404(app_state, user_id)
        return ApiResponse(data=_to_response(user))

    @patch("/{user_id:str}")
    async def update_user_role(
        self,
        state: State,
        user_id: PathId,
        data: UpdateUserRoleRequest,
    ) -> ApiResponse[UserResponse]:
        """Update a user's role.

        Args:
            state: Application state.
            user_id: User identifier.
            data: Role update payload.

        Returns:
            Updated user response.

        Raises:
            NotFoundError: If the user is not found.
            ApiValidationError: If the target role is SYSTEM.
            ConflictError: If the target user is the system user,
                changing the only CEO's role, or assigning a
                second CEO.
        """
        app_state: AppState = state.app_state

        _validate_assignable_role(data.role)
        user = await _get_user_or_404(app_state, user_id)

        if user.role == HumanRole.SYSTEM:
            msg = "Cannot modify the system user"
            logger.warning(API_RESOURCE_CONFLICT, reason=msg)
            raise ConflictError(msg)

        async with _CEO_LOCK:
            await _validate_role_change(app_state, user, data.role)

            now = datetime.now(UTC)
            updated = user.model_copy(
                update={"role": data.role, "updated_at": now},
            )
            try:
                await app_state.persistence.users.save(updated)
            except QueryError as exc:
                msg = "A CEO user already exists"
                logger.warning(API_RESOURCE_CONFLICT, reason=msg)
                raise ConflictError(msg) from exc

        logger.info(
            API_USER_UPDATED,
            user_id=user.id,
            old_role=user.role.value,
            new_role=data.role.value,
        )
        return ApiResponse(data=_to_response(updated))

    @delete("/{user_id:str}", status_code=HTTP_204_NO_CONTENT)
    async def delete_user(
        self,
        state: State,
        user_id: PathId,
        request: Request[Any, Any, Any],
    ) -> None:
        """Delete a user account.

        Args:
            state: Application state.
            user_id: User identifier.
            request: The incoming HTTP request.

        Raises:
            NotFoundError: If the user is not found.
            ConflictError: If attempting to delete your own account,
                the system user, or the CEO.
        """
        app_state: AppState = state.app_state
        auth_user: AuthenticatedUser = request.scope["user"]

        user = await _get_user_or_404(app_state, user_id)

        if user.id == auth_user.user_id:
            msg = "Cannot delete your own account"
            logger.warning(API_RESOURCE_CONFLICT, reason=msg)
            raise ConflictError(msg)

        if user.role == HumanRole.SYSTEM:
            msg = "Cannot delete the system user"
            logger.warning(API_RESOURCE_CONFLICT, reason=msg)
            raise ConflictError(msg)

        if user.role == HumanRole.CEO:
            msg = "Cannot delete the CEO user"
            logger.warning(API_RESOURCE_CONFLICT, reason=msg)
            raise ConflictError(msg)

        deleted = await app_state.persistence.users.delete(user_id)
        if not deleted:
            msg = f"User not found: {user_id}"
            logger.warning(API_RESOURCE_NOT_FOUND, reason=msg)
            raise NotFoundError(msg)

        logger.info(
            API_USER_DELETED,
            user_id=user.id,
            deleted_by_user_id=auth_user.user_id,
        )
