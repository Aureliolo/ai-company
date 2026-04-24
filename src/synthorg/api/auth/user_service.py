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
from synthorg.observability import get_logger, safe_error_description
from synthorg.observability.events.api import (
    API_USER_CREATED,
    API_USER_DELETED,
    API_USER_LISTED,
    API_USER_UPDATED,
)

if TYPE_CHECKING:
    from synthorg.persistence.auth_protocol import RefreshTokenRepository
    from synthorg.persistence.repositories import UserRepository

logger = get_logger(__name__)


class UserService:
    """Wraps :class:`UserRepository` with uniform audit logging.

    Raises from the underlying repository (``ConstraintViolationError``,
    ``QueryError``) propagate unchanged so the controller can map them
    to the appropriate HTTP response.

    Args:
        repo: User repository implementation.
        refresh_tokens: Optional refresh-token repository. When
            provided, ``delete()`` performs ``revoke_by_user()`` as
            an explicit refresh-token revocation step before the DB
            delete (CFG-1 audit / GDPR defense-in-depth). Refresh
            tokens are persisted and also removed by the schema's
            ``ON DELETE CASCADE`` on ``refresh_tokens.user_id``, as
            with sessions and api_keys; the explicit revocation runs
            first so outstanding tokens stop minting access tokens
            even if the DB delete is delayed or retried.
    """

    __slots__ = ("_refresh_tokens", "_repo")

    def __init__(
        self,
        *,
        repo: UserRepository,
        refresh_tokens: RefreshTokenRepository | None = None,
    ) -> None:
        self._repo = repo
        self._refresh_tokens = refresh_tokens

    async def get(self, user_id: NotBlankStr) -> User | None:
        """Fetch a user by id, or ``None`` when no row matches."""
        return await self._repo.get(user_id)

    async def list_users(self) -> tuple[User, ...]:
        """List all users (sans system user)."""
        users = await self._repo.list_users()
        logger.debug(API_USER_LISTED, count=len(users))
        return users

    async def list_users_page(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[tuple[User, ...], int]:
        """Return a single page of users plus the authoritative total.

        The repository pushes ``LIMIT`` / ``OFFSET`` into the SQL so
        large operator rosters do not pay an O(n) scan per request.
        ``count()`` issues the dedicated ``COUNT(*)`` round-trip the
        controller needs to populate ``PaginationMeta.total``.

        Args:
            limit: Page size.
            offset: Number of rows to skip (decoded from the cursor).

        Returns:
            ``(page, total)`` where ``page`` is the requested slice in
            ``id`` order and ``total`` is the full row count for the
            human-user table.
        """
        page = await self._repo.list_users_paginated(limit=limit, offset=offset)
        total = await self._repo.count()
        logger.debug(API_USER_LISTED, count=len(page), offset=offset, total=total)
        return page, total

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
        """Delete a user and cascade to dependent rows.

        Explicitly revokes outstanding refresh tokens before the DB
        delete as defense-in-depth (CFG-1 audit / GDPR). Refresh
        tokens are persisted in ``refresh_tokens`` and also removed
        by schema-level ``ON DELETE CASCADE`` on ``user_id``; running
        ``revoke_by_user`` first prevents a window where tokens could
        still mint access tokens if the delete is retried or delayed.
        Schema FK cascade additionally removes sessions + api_keys
        when the user row goes away. Audit entries are preserved by
        design -- ``audit_entries.agent_id`` carries the agent
        identifier, not the user id, and the security design keeps
        the audit trail intact even after user removal.

        Fails closed: if refresh-token revocation raises, the user
        delete is aborted so tokens are never left live alongside a
        deleted user (SEC-1).

        Returns ``True`` when a user row was removed.
        """
        revoked_refresh_tokens = 0
        if self._refresh_tokens is not None:
            try:
                revoked_refresh_tokens = await self._refresh_tokens.revoke_by_user(
                    user_id
                )
            except MemoryError, RecursionError:
                raise
            except Exception as exc:
                logger.warning(
                    API_USER_DELETED,
                    user_id=user_id,
                    note="refresh-token cascade failed; aborting user delete",
                    error_type=type(exc).__name__,
                    error=safe_error_description(exc),
                )
                raise
        deleted = await self._repo.delete(user_id)
        if deleted:
            logger.info(
                API_USER_DELETED,
                user_id=user_id,
                deleted_by_user_id=deleted_by_user_id,
                cascade_refresh_tokens=revoked_refresh_tokens,
            )
        return deleted
