"""Stub repository implementations for integration tables.

These in-memory stubs allow the persistence backends to satisfy
the ``PersistenceBackend`` protocol immediately.  Full SQLite and
Postgres implementations will replace these as integration features
are exercised.

All reads return deep copies so callers cannot mutate internal
state by holding references to returned models. Even though the
domain models are frozen Pydantic ``BaseModel`` instances, their
mutable fields (``dict`` metadata) would otherwise still be
aliased to the stored value.
"""

import copy

from synthorg.integrations.connections.models import (
    Connection,  # noqa: TC001
    ConnectionType,  # noqa: TC001
    OAuthState,  # noqa: TC001
    WebhookReceipt,  # noqa: TC001
)


class StubConnectionRepository:
    """In-memory stub for ConnectionRepository."""

    def __init__(self) -> None:
        self._store: dict[str, Connection] = {}

    async def save(self, connection: Connection) -> None:
        """Persist a connection (deep-copied on write)."""
        self._store[connection.name] = copy.deepcopy(connection)

    async def get(self, name: str) -> Connection | None:
        """Retrieve by name (deep-copied on read)."""
        existing = self._store.get(name)
        return copy.deepcopy(existing) if existing is not None else None

    async def list_all(self) -> tuple[Connection, ...]:
        """List all (deep-copied)."""
        return tuple(copy.deepcopy(c) for c in self._store.values())

    async def list_by_type(
        self,
        connection_type: ConnectionType,
    ) -> tuple[Connection, ...]:
        """List by type (deep-copied)."""
        return tuple(
            copy.deepcopy(c)
            for c in self._store.values()
            if c.connection_type == connection_type
        )

    async def delete(self, name: str) -> bool:
        """Delete by name."""
        return self._store.pop(name, None) is not None


class StubConnectionSecretRepository:
    """In-memory stub for ConnectionSecretRepository."""

    def __init__(self) -> None:
        self._store: dict[str, bytes] = {}

    async def store(
        self,
        secret_id: str,
        encrypted_value: bytes,
        key_version: int,  # noqa: ARG002
    ) -> None:
        """Persist a secret (bytes are immutable, no copy needed)."""
        self._store[secret_id] = encrypted_value

    async def retrieve(self, secret_id: str) -> bytes | None:
        """Retrieve a secret."""
        return self._store.get(secret_id)

    async def delete(self, secret_id: str) -> bool:
        """Delete a secret."""
        return self._store.pop(secret_id, None) is not None


class StubOAuthStateRepository:
    """In-memory stub for OAuthStateRepository."""

    def __init__(self) -> None:
        self._store: dict[str, OAuthState] = {}

    async def save(self, state: OAuthState) -> None:
        """Persist a state (deep-copied)."""
        self._store[state.state_token] = copy.deepcopy(state)

    async def get(self, state_token: str) -> OAuthState | None:
        """Retrieve by token (deep-copied)."""
        existing = self._store.get(state_token)
        return copy.deepcopy(existing) if existing is not None else None

    async def delete(self, state_token: str) -> bool:
        """Delete by token."""
        return self._store.pop(state_token, None) is not None

    async def cleanup_expired(self) -> int:
        """No-op for stub."""
        return 0


class StubWebhookReceiptRepository:
    """In-memory stub for WebhookReceiptRepository."""

    def __init__(self) -> None:
        self._store: list[WebhookReceipt] = []

    async def log(self, receipt: WebhookReceipt) -> None:
        """Persist a receipt (deep-copied)."""
        self._store.append(copy.deepcopy(receipt))

    async def get_by_connection(
        self,
        connection_name: str,
        *,
        limit: int = 100,
    ) -> tuple[WebhookReceipt, ...]:
        """List by connection (deep-copied), newest-first."""
        # ``self._store`` is append-ordered, so the most recent
        # receipts live at the end. The repository contract asks
        # callers to receive newest-first, so reverse before slicing.
        matches = [
            copy.deepcopy(r)
            for r in reversed(self._store)
            if r.connection_name == connection_name
        ]
        return tuple(matches[:limit])

    async def cleanup_old(
        self,
        retention_days: int,  # noqa: ARG002
    ) -> int:
        """No-op for stub."""
        return 0
