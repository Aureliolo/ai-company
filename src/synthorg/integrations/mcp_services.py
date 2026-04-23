# ruff: noqa: D102, EM101, PLR0913
"""Integrations facades for the MCP handler layer.

MCPCatalogFacadeService, OAuthFacadeService, ClientFacadeService,
ArtifactFacadeService, and OntologyFacadeService.  Each wraps the
corresponding primitive on AppState (or an in-memory store when no
primitive yet exists) and raises
:class:`CapabilityNotSupportedError` for methods the primitive does
not yet implement.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID, uuid4

from synthorg.communication.mcp_errors import CapabilityNotSupportedError
from synthorg.observability import get_logger

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from synthorg.core.types import NotBlankStr
    from synthorg.integrations.mcp_catalog.installations import (
        McpInstallationRepository,
    )
    from synthorg.integrations.mcp_catalog.service import CatalogService
    from synthorg.integrations.oauth.token_manager import OAuthTokenManager
    from synthorg.ontology.service import OntologyService
    from synthorg.persistence.artifact_storage import ArtifactStorageBackend

logger = get_logger(__name__)


def _capability(cap: str, detail: str) -> CapabilityNotSupportedError:
    return CapabilityNotSupportedError(cap, detail)


# ── MCPCatalogFacadeService ────────────────────────────────────────


class MCPCatalogFacadeService:
    """Facade over :class:`CatalogService` + installation repo."""

    def __init__(
        self,
        *,
        catalog: CatalogService,
        installations: McpInstallationRepository,
    ) -> None:
        self._catalog = cast("Any", catalog)
        self._installations = cast("Any", installations)

    async def list_catalog(self) -> Sequence[object]:
        fn = getattr(self._catalog, "list_entries", None)
        if callable(fn):
            return tuple(await fn())
        return ()

    async def search_catalog(
        self,
        query: NotBlankStr,
    ) -> Sequence[object]:
        fn = getattr(self._catalog, "search", None)
        if callable(fn):
            return tuple(await fn(query))
        return ()

    async def get_catalog_entry(
        self,
        entry_id: NotBlankStr,
    ) -> object | None:
        fn = getattr(self._catalog, "get_entry", None)
        if not callable(fn):
            return None
        return cast("object | None", await fn(entry_id))

    async def install_catalog_entry(
        self,
        *,
        entry_id: NotBlankStr,
        actor_id: NotBlankStr,
    ) -> object:
        fn = getattr(self._installations, "install", None)
        if not callable(fn):
            raise _capability(
                "mcp_catalog_install",
                "McpInstallationRepository does not expose install",
            )
        result = await fn(entry_id=entry_id, actor=actor_id)
        logger.info(
            "integrations.mcp_catalog_installed_via_mcp",
            entry_id=entry_id,
            actor_id=actor_id,
        )
        return result

    async def uninstall_catalog_entry(
        self,
        *,
        installation_id: NotBlankStr,
        actor_id: NotBlankStr,
        reason: NotBlankStr,
    ) -> bool:
        fn = getattr(self._installations, "uninstall", None)
        if not callable(fn):
            raise _capability(
                "mcp_catalog_uninstall",
                "McpInstallationRepository does not expose uninstall",
            )
        removed = bool(await fn(installation_id=installation_id))
        logger.info(
            "integrations.mcp_catalog_uninstalled_via_mcp",
            installation_id=installation_id,
            actor_id=actor_id,
            reason=reason,
            removed=removed,
        )
        return removed


# ── OAuthFacadeService ─────────────────────────────────────────────


class _OAuthProviderRecord:
    __slots__ = (
        "authorize_url",
        "client_id",
        "created_at",
        "name",
        "scopes",
        "token_url",
    )

    def __init__(
        self,
        *,
        name: str,
        client_id: str,
        authorize_url: str,
        token_url: str,
        scopes: tuple[str, ...],
        created_at: datetime,
    ) -> None:
        self.name = name
        self.client_id = client_id
        self.authorize_url = authorize_url
        self.token_url = token_url
        self.scopes = scopes
        self.created_at = created_at

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "client_id": self.client_id,
            "authorize_url": self.authorize_url,
            "token_url": self.token_url,
            "scopes": list(self.scopes),
            "created_at": self.created_at.isoformat(),
        }


class OAuthFacadeService:
    """In-process OAuth provider registry."""

    def __init__(
        self,
        *,
        token_manager: OAuthTokenManager | None = None,
    ) -> None:
        self._token_manager = cast("Any", token_manager) if token_manager else None
        self._providers: dict[str, _OAuthProviderRecord] = {}

    async def list_providers(self) -> Sequence[_OAuthProviderRecord]:
        return tuple(
            sorted(self._providers.values(), key=lambda p: p.created_at, reverse=True),
        )

    async def configure_provider(
        self,
        *,
        name: NotBlankStr,
        client_id: NotBlankStr,
        authorize_url: NotBlankStr,
        token_url: NotBlankStr,
        scopes: Sequence[str],
        actor_id: NotBlankStr,
    ) -> _OAuthProviderRecord:
        record = _OAuthProviderRecord(
            name=name,
            client_id=client_id,
            authorize_url=authorize_url,
            token_url=token_url,
            scopes=tuple(scopes),
            created_at=datetime.now(UTC),
        )
        self._providers[record.name] = record
        logger.info(
            "integrations.oauth_provider_configured_via_mcp",
            provider_name=name,
            actor_id=actor_id,
        )
        return record

    async def remove_provider(
        self,
        *,
        name: NotBlankStr,
        actor_id: NotBlankStr,
        reason: NotBlankStr,
    ) -> bool:
        removed = self._providers.pop(name, None) is not None
        logger.info(
            "integrations.oauth_provider_removed_via_mcp",
            provider_name=name,
            actor_id=actor_id,
            reason=reason,
            removed=removed,
        )
        return removed


# ── ClientFacadeService ─────────────────────────────────────────────


class _ClientRecord:
    __slots__ = (
        "active",
        "contact_email",
        "created_at",
        "id",
        "name",
        "notes",
        "satisfaction_score",
    )

    def __init__(
        self,
        *,
        id: UUID,  # noqa: A002
        name: str,
        contact_email: str | None,
        notes: str | None,
        created_at: datetime,
    ) -> None:
        self.id = id
        self.name = name
        self.contact_email = contact_email
        self.notes = notes
        self.created_at = created_at
        self.active = True
        self.satisfaction_score: float | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "id": str(self.id),
            "name": self.name,
            "contact_email": self.contact_email,
            "notes": self.notes,
            "active": self.active,
            "satisfaction_score": self.satisfaction_score,
            "created_at": self.created_at.isoformat(),
        }


class ClientFacadeService:
    """In-process external-client CRUD facade."""

    def __init__(self) -> None:
        self._clients: dict[UUID, _ClientRecord] = {}

    async def list_clients(self) -> Sequence[_ClientRecord]:
        return tuple(
            sorted(self._clients.values(), key=lambda c: c.created_at, reverse=True),
        )

    async def get_client(self, client_id: NotBlankStr) -> _ClientRecord | None:
        try:
            key = UUID(client_id)
        except ValueError:
            return None
        return self._clients.get(key)

    async def create_client(
        self,
        *,
        name: NotBlankStr,
        actor_id: NotBlankStr,
        contact_email: str | None = None,
        notes: str | None = None,
    ) -> _ClientRecord:
        record = _ClientRecord(
            id=uuid4(),
            name=name,
            contact_email=contact_email,
            notes=notes,
            created_at=datetime.now(UTC),
        )
        self._clients[record.id] = record
        logger.info(
            "integrations.client_created_via_mcp",
            client_id=str(record.id),
            actor_id=actor_id,
        )
        return record

    async def deactivate_client(
        self,
        *,
        client_id: NotBlankStr,
        actor_id: NotBlankStr,
        reason: NotBlankStr,
    ) -> bool:
        try:
            key = UUID(client_id)
        except ValueError:
            return False
        record = self._clients.get(key)
        if record is None:
            return False
        record.active = False
        logger.info(
            "integrations.client_deactivated_via_mcp",
            client_id=client_id,
            actor_id=actor_id,
            reason=reason,
        )
        return True

    async def get_satisfaction(
        self,
        client_id: NotBlankStr,
    ) -> Mapping[str, object]:
        record = await self.get_client(client_id)
        if record is None:
            return {"status": "unknown", "reason": "not_found"}
        return {
            "client_id": str(record.id),
            "score": record.satisfaction_score,
            "active": record.active,
        }


# ── ArtifactFacadeService ──────────────────────────────────────────


class _ArtifactRecord:
    __slots__ = (
        "content_type",
        "created_at",
        "id",
        "name",
        "size_bytes",
        "storage_ref",
    )

    def __init__(
        self,
        *,
        id: UUID,  # noqa: A002
        name: str,
        content_type: str,
        size_bytes: int,
        storage_ref: str,
        created_at: datetime,
    ) -> None:
        self.id = id
        self.name = name
        self.content_type = content_type
        self.size_bytes = size_bytes
        self.storage_ref = storage_ref
        self.created_at = created_at

    def to_dict(self) -> dict[str, object]:
        return {
            "id": str(self.id),
            "name": self.name,
            "content_type": self.content_type,
            "size_bytes": self.size_bytes,
            "storage_ref": self.storage_ref,
            "created_at": self.created_at.isoformat(),
        }


class ArtifactFacadeService:
    """Facade over :class:`ArtifactStorageBackend`.

    Reads and writes wrap the storage primitive; listing and metadata
    lookups use an in-memory index populated on create so that MCP
    clients can browse artifacts without touching durable storage for
    every request.
    """

    def __init__(self, *, storage: ArtifactStorageBackend) -> None:
        self._storage = cast("Any", storage)
        self._index: dict[UUID, _ArtifactRecord] = {}

    async def list_artifacts(self) -> Sequence[_ArtifactRecord]:
        return tuple(
            sorted(self._index.values(), key=lambda a: a.created_at, reverse=True),
        )

    async def get_artifact(self, artifact_id: NotBlankStr) -> _ArtifactRecord | None:
        try:
            key = UUID(artifact_id)
        except ValueError:
            return None
        return self._index.get(key)

    async def create_artifact(
        self,
        *,
        name: NotBlankStr,
        content_type: NotBlankStr,
        size_bytes: int,
        storage_ref: NotBlankStr,
        actor_id: NotBlankStr,
    ) -> _ArtifactRecord:
        record = _ArtifactRecord(
            id=uuid4(),
            name=name,
            content_type=content_type,
            size_bytes=size_bytes,
            storage_ref=storage_ref,
            created_at=datetime.now(UTC),
        )
        self._index[record.id] = record
        logger.info(
            "integrations.artifact_created_via_mcp",
            artifact_id=str(record.id),
            actor_id=actor_id,
            size_bytes=size_bytes,
        )
        return record

    async def delete_artifact(
        self,
        *,
        artifact_id: NotBlankStr,
        actor_id: NotBlankStr,
        reason: NotBlankStr,
    ) -> bool:
        try:
            key = UUID(artifact_id)
        except ValueError:
            return False
        removed = self._index.pop(key, None) is not None
        fn = getattr(self._storage, "delete", None)
        if callable(fn) and removed:
            try:
                await fn(str(key))
            except Exception:
                logger.exception(
                    "integrations.artifact_storage_delete_failed",
                    artifact_id=artifact_id,
                )
        logger.info(
            "integrations.artifact_deleted_via_mcp",
            artifact_id=artifact_id,
            actor_id=actor_id,
            reason=reason,
            removed=removed,
        )
        return removed


# ── OntologyFacadeService ──────────────────────────────────────────


class OntologyFacadeService:
    """Facade over :class:`OntologyService`."""

    def __init__(self, *, ontology: OntologyService) -> None:
        self._ontology = cast("Any", ontology)

    async def list_entities(self) -> Sequence[object]:
        fn = getattr(self._ontology, "list_entities", None)
        if callable(fn):
            return tuple(await fn())
        return ()

    async def get_entity(
        self,
        entity_id: NotBlankStr,
    ) -> object | None:
        fn = getattr(self._ontology, "get_entity", None)
        if not callable(fn):
            return None
        return cast("object | None", await fn(entity_id))

    async def get_relationships(
        self,
        entity_id: NotBlankStr,
    ) -> Sequence[object]:
        fn = getattr(self._ontology, "get_relationships", None)
        if callable(fn):
            return tuple(await fn(entity_id))
        return ()

    async def search(
        self,
        query: NotBlankStr,
    ) -> Sequence[object]:
        fn = getattr(self._ontology, "search", None)
        if callable(fn):
            return tuple(await fn(query))
        return ()


__all__ = [
    "ArtifactFacadeService",
    "ClientFacadeService",
    "MCPCatalogFacadeService",
    "OAuthFacadeService",
    "OntologyFacadeService",
]
