"""User admin service layer.

Thin wrapper over :class:`UserRepository` so the ``/users`` controller
does not reach into ``app_state.persistence.users`` directly. CEO /
SYSTEM / constraint-violation policy stays in the controller (those are
HTTP / audit-log concerns) but CRUD mechanics live here with uniform
``API_USER_*`` logging.
"""

from typing import TYPE_CHECKING

from synthorg.api.auth.models import User  # noqa: TC001
from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.api import (
    API_USER_CREATED,
    API_USER_DELETED,
    API_USER_LISTED,
    API_USER_UPDATED,
)

if TYPE_CHECKING:
    from synthorg.persistence.repositories import UserRepository

logger = get_logger(__name__)


class UserService:
    """Wraps :class:`UserRepository` with uniform audit logging.

    Raises from the underlying repository (``ConstraintViolationError``,
    ``QueryError``) propagate unchanged so the controller can map them
    to the appropriate HTTP response.
    """

    __slots__ = ("_repo",)

    def __init__(self, *, repo: UserRepository) -> None:
        self._repo = repo

    async def get(self, user_id: NotBlankStr) -> User | None:
        """Fetch a user by id, or ``None`` when no row matches."""
        return await self._repo.get(user_id)

    async def list_users(self) -> tuple[User, ...]:
        """List all users (sans system user)."""
        users = await self._repo.list_users()
        logger.debug(API_USER_LISTED, count=len(users))
        return users

    async def create(self, user: User) -> User:
        """Persist a freshly-constructed user."""
        await self._repo.save(user)
        logger.info(
            API_USER_CREATED,
            user_id=user.id,
            role=user.role.value,
        )
        return user

    async def save_update(
        self,
        user: User,
        *,
        intent: str,
        **audit_fields: object,
    ) -> User:
        """Upsert an existing user with structured audit metadata.

        ``intent`` distinguishes updates in the audit log (role change,
        org-role grant, org-role revoke); extra ``audit_fields`` are
        forwarded into the ``API_USER_UPDATED`` event verbatim.
        """
        await self._repo.save(user)
        logger.info(
            API_USER_UPDATED,
            user_id=user.id,
            intent=intent,
            **audit_fields,
        )
        return user

    async def delete(
        self,
        user_id: NotBlankStr,
        *,
        deleted_by_user_id: NotBlankStr,
    ) -> bool:
        """Delete a user; returns ``True`` when a row was removed."""
        deleted = await self._repo.delete(user_id)
        if deleted:
            logger.info(
                API_USER_DELETED,
                user_id=user_id,
                deleted_by_user_id=deleted_by_user_id,
            )
        return deleted
