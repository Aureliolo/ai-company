"""Connection catalog service.

Central registry for external service connections.  Provides CRUD,
lookup, credential resolution, and health status management.
"""

import asyncio
import copy
import json
from datetime import UTC, datetime
from uuid import uuid4

from synthorg.core.types import NotBlankStr
from synthorg.integrations.connections.models import (
    AuthMethod,
    Connection,
    ConnectionStatus,
    ConnectionType,
    SecretRef,
)
from synthorg.integrations.connections.secret_backends.protocol import (
    SecretBackend,  # noqa: TC001
)
from synthorg.integrations.connections.types import get_authenticator
from synthorg.integrations.errors import (
    ConnectionNotFoundError,
    DuplicateConnectionError,
    InvalidConnectionAuthError,
)
from synthorg.observability import get_logger
from synthorg.observability.events.integrations import (
    CONNECTION_CREATED,
    CONNECTION_DELETED,
    CONNECTION_DUPLICATE,
    CONNECTION_NOT_FOUND,
    CONNECTION_UPDATED,
    CONNECTION_VALIDATION_FAILED,
)
from synthorg.persistence.repositories_integrations import (
    ConnectionRepository,  # noqa: TC001
)

logger = get_logger(__name__)

_UNSET = object()
"""Sentinel value to distinguish 'not provided' from None."""


class ConnectionCatalog:
    """Central registry for external service connections.

    Thread-safe via ``asyncio.Lock`` for cache invalidation.
    All writes go through the persistence layer; reads use an
    in-memory cache that is invalidated on mutation.

    Args:
        repository: Persistence repository for connections.
        secret_backend: Backend for credential storage.
    """

    def __init__(
        self,
        repository: ConnectionRepository,
        secret_backend: SecretBackend,
    ) -> None:
        self._repo = repository
        self._secret_backend = secret_backend
        self._cache: dict[str, Connection] = {}
        self._cache_lock = asyncio.Lock()
        self._cache_valid = False

    async def _ensure_cache(self) -> None:
        """Populate the cache from persistence if invalid."""
        if self._cache_valid:
            return
        async with self._cache_lock:
            # Re-check under lock (double-checked locking)
            if not self._cache_valid:
                all_conns = await self._repo.list_all()
                self._cache = {c.name: c for c in all_conns}
                self._cache_valid = True

    def _invalidate_cache(self) -> None:
        self._cache_valid = False

    async def create(  # noqa: PLR0913
        self,
        *,
        name: str,
        connection_type: ConnectionType,
        auth_method: str,
        credentials: dict[str, str],
        base_url: str | None = None,
        metadata: dict[str, str] | None = None,
        health_check_enabled: bool = True,
    ) -> Connection:
        """Create a new connection.

        Validates credentials via the type's authenticator, encrypts
        them via the secret backend, and persists the connection.

        Args:
            name: Unique connection name.
            connection_type: Service type.
            auth_method: How credentials are provided.
            credentials: Plaintext credentials (encrypted before storage).
            base_url: Optional base URL.
            metadata: Optional user tags.
            health_check_enabled: Whether to probe health.

        Returns:
            The persisted connection.

        Raises:
            DuplicateConnectionError: If name already exists.
            InvalidConnectionAuthError: If credentials are invalid.
        """
        await self._ensure_cache()
        if name in self._cache:
            logger.warning(
                CONNECTION_DUPLICATE,
                connection_name=name,
            )
            msg = f"Connection '{name}' already exists"
            raise DuplicateConnectionError(msg)

        authenticator = get_authenticator(connection_type)
        try:
            authenticator.validate_credentials(credentials)
        except InvalidConnectionAuthError:
            logger.warning(
                CONNECTION_VALIDATION_FAILED,
                connection_name=name,
                connection_type=connection_type,
            )
            raise

        secret_id = str(uuid4())
        await self._secret_backend.store(
            secret_id,
            json.dumps(credentials).encode("utf-8"),
        )

        secret_ref = SecretRef(
            secret_id=NotBlankStr(secret_id),
            backend=NotBlankStr(self._secret_backend.backend_name),
        )
        now = datetime.now(UTC)
        connection = Connection(
            name=NotBlankStr(name),
            connection_type=connection_type,
            auth_method=AuthMethod(auth_method),
            base_url=NotBlankStr(base_url) if base_url else None,
            secret_refs=(secret_ref,),
            health_check_enabled=health_check_enabled,
            metadata=metadata or {},
            created_at=now,
            updated_at=now,
        )
        await self._repo.save(connection)
        self._invalidate_cache()
        logger.info(
            CONNECTION_CREATED,
            connection_name=name,
            connection_type=connection_type,
        )
        return connection

    async def get(self, name: str) -> Connection | None:
        """Retrieve a connection by name."""
        await self._ensure_cache()
        return self._cache.get(name)

    async def get_or_raise(self, name: str) -> Connection:
        """Retrieve a connection by name, or raise.

        Raises:
            ConnectionNotFoundError: If the connection does not exist.
        """
        conn = await self.get(name)
        if conn is None:
            logger.warning(CONNECTION_NOT_FOUND, connection_name=name)
            msg = f"Connection '{name}' not found"
            raise ConnectionNotFoundError(msg)
        return conn

    async def list_all(self) -> tuple[Connection, ...]:
        """List all connections."""
        await self._ensure_cache()
        return tuple(self._cache.values())

    async def list_by_type(
        self,
        connection_type: ConnectionType,
    ) -> tuple[Connection, ...]:
        """List connections of a specific type."""
        await self._ensure_cache()
        return tuple(
            c for c in self._cache.values() if c.connection_type == connection_type
        )

    async def update(
        self,
        name: str,
        *,
        base_url: str | None | object = _UNSET,
        metadata: dict[str, str] | None = None,
        health_check_enabled: bool | None = None,
    ) -> Connection:
        """Update a connection's mutable fields.

        Raises:
            ConnectionNotFoundError: If the connection does not exist.
        """
        existing = await self.get_or_raise(name)
        updates: dict[str, object] = {"updated_at": datetime.now(UTC)}
        if base_url is not _UNSET:
            updates["base_url"] = NotBlankStr(base_url) if base_url else None
        if metadata is not None:
            updates["metadata"] = metadata
        if health_check_enabled is not None:
            updates["health_check_enabled"] = health_check_enabled
        updated = existing.model_copy(update=updates)
        await self._repo.save(updated)
        self._invalidate_cache()
        logger.info(CONNECTION_UPDATED, connection_name=name)
        return updated

    async def update_health(
        self,
        name: str,
        *,
        status: ConnectionStatus,
        checked_at: datetime,
    ) -> Connection:
        """Update a connection's health status.

        Raises:
            ConnectionNotFoundError: If the connection does not exist.
        """
        existing = await self.get_or_raise(name)
        updated = existing.model_copy(
            update={
                "health_status": status,
                "last_health_check_at": checked_at,
                "updated_at": datetime.now(UTC),
            },
        )
        await self._repo.save(updated)
        self._invalidate_cache()
        return updated

    async def delete(self, name: str) -> None:
        """Delete a connection and its secrets.

        Raises:
            ConnectionNotFoundError: If the connection does not exist.
        """
        existing = await self.get_or_raise(name)
        for ref in existing.secret_refs:
            await self._secret_backend.delete(ref.secret_id)
        await self._repo.delete(name)
        self._invalidate_cache()
        logger.info(CONNECTION_DELETED, connection_name=name)

    async def get_credentials(self, name: str) -> dict[str, str]:
        """Retrieve decrypted credentials for a connection.

        Resolves all ``SecretRef`` entries and returns the merged
        credential dict.

        Raises:
            ConnectionNotFoundError: If the connection does not exist.
            SecretRetrievalError: If decryption fails.
        """
        conn = await self.get_or_raise(name)
        merged: dict[str, str] = {}
        for ref in conn.secret_refs:
            raw = await self._secret_backend.retrieve(ref.secret_id)
            if raw is not None:
                data = json.loads(raw.decode("utf-8"))
                if isinstance(data, dict):
                    merged.update(data)
        return copy.deepcopy(merged)
