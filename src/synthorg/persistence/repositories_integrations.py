"""Repository protocols for integration persistence.

Defines CRUD interfaces for connections, OAuth states, and webhook
receipts.  Split from ``repositories.py`` to keep files under the
800-line limit.
"""

from typing import Protocol, runtime_checkable

from synthorg.integrations.connections.models import (
    Connection,  # noqa: TC001
    ConnectionType,  # noqa: TC001
    OAuthState,  # noqa: TC001
    WebhookReceipt,  # noqa: TC001
)


@runtime_checkable
class ConnectionRepository(Protocol):
    """CRUD + query interface for Connection persistence."""

    async def save(self, connection: Connection) -> None:
        """Persist a connection (insert or upsert)."""
        ...

    async def get(self, name: str) -> Connection | None:
        """Retrieve a connection by name."""
        ...

    async def list_all(self) -> tuple[Connection, ...]:
        """List all connections."""
        ...

    async def list_by_type(
        self,
        connection_type: ConnectionType,
    ) -> tuple[Connection, ...]:
        """List connections of a specific type."""
        ...

    async def delete(self, name: str) -> bool:
        """Delete a connection by name.

        Returns:
            ``True`` if the connection existed and was deleted.
        """
        ...


@runtime_checkable
class ConnectionSecretRepository(Protocol):
    """Low-level CRUD for encrypted secret blobs.

    Used by ``EncryptedSqliteSecretBackend``; other backends
    manage their own storage.
    """

    async def store(
        self,
        secret_id: str,
        encrypted_value: bytes,
        key_version: int,
    ) -> None:
        """Persist an encrypted secret."""
        ...

    async def retrieve(self, secret_id: str) -> bytes | None:
        """Retrieve an encrypted secret blob."""
        ...

    async def delete(self, secret_id: str) -> bool:
        """Delete an encrypted secret."""
        ...


@runtime_checkable
class OAuthStateRepository(Protocol):
    """CRUD for transient OAuth authorization states."""

    async def save(self, state: OAuthState) -> None:
        """Persist an OAuth state."""
        ...

    async def get(self, state_token: str) -> OAuthState | None:
        """Retrieve by state token."""
        ...

    async def delete(self, state_token: str) -> bool:
        """Delete a state token (consumed or expired)."""
        ...

    async def cleanup_expired(self) -> int:
        """Delete all expired states.

        Returns:
            Number of deleted rows.
        """
        ...


@runtime_checkable
class WebhookReceiptRepository(Protocol):
    """CRUD for webhook receipt log entries."""

    async def log(self, receipt: WebhookReceipt) -> None:
        """Persist a webhook receipt."""
        ...

    async def get_by_connection(
        self,
        connection_name: str,
        *,
        limit: int = 100,
    ) -> tuple[WebhookReceipt, ...]:
        """List receipts for a connection, newest first."""
        ...

    async def cleanup_old(self, retention_days: int) -> int:
        """Delete receipts older than *retention_days*.

        Returns:
            Number of deleted rows.
        """
        ...
