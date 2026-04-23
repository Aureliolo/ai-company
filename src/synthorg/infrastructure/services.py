# ruff: noqa: D102, EM101, E501
"""Infrastructure facades for the MCP handler layer.

Thin per-subdomain facades used by the infrastructure MCP tools
(settings, providers, backup, users, projects, requests, setup,
simulations, template packs, audit, events, integration health).
Each facade wraps the already-attached AppState primitive and lifts
the common audit-log pattern into a single owner.

For operations whose underlying primitive does not yet expose the
required method the facade raises
:class:`~synthorg.communication.mcp_errors.CapabilityNotSupportedError`,
which the MCP handler translates to a typed ``not_supported`` envelope.
This keeps the distinction between "handler wired, primitive
capability missing" and "handler unwired" observable on the wire.

Primitives are stored internally as :class:`Any` so the facade can
introspect capabilities at runtime (``getattr`` + ``callable``
checks) without fighting protocol-type narrowing when the primitive
is still evolving.

Method-level docstrings are intentionally thin (``# ruff: noqa: D102, EM101, EM102, E501, TRY003``
at module scope) because the class-level docstrings describe the
facade's role and the method names are self-documenting pass-throughs.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID, uuid4

from synthorg.communication.mcp_errors import CapabilityNotSupportedError
from synthorg.observability import get_logger
from synthorg.observability.events.settings import (
    SETTINGS_VALUE_DELETED,
    SETTINGS_VALUE_SET,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from synthorg.api.auth.service import AuthService
    from synthorg.backup.service import BackupService as CoreBackupService
    from synthorg.client.simulation_state import ClientSimulationState
    from synthorg.communication.event_stream.stream import EventStreamHub
    from synthorg.core.types import NotBlankStr
    from synthorg.integrations.health.prober import HealthProberService
    from synthorg.providers.health import ProviderHealthTracker
    from synthorg.providers.management.service import ProviderManagementService
    from synthorg.providers.registry import ProviderRegistry
    from synthorg.security.audit import AuditLog
    from synthorg.settings.service import SettingsService

logger = get_logger(__name__)


def _capability_missing(
    capability: str,
    detail: str,
) -> CapabilityNotSupportedError:
    """Shared helper for typed capability-gap errors."""
    return CapabilityNotSupportedError(capability, detail)


def _require_callable(
    target: Any,
    method_name: str,
    capability: str,
    detail: str,
) -> Any:
    """Return a callable attribute or raise ``CapabilityNotSupportedError``."""
    fn = getattr(target, method_name, None)
    if not callable(fn):
        raise _capability_missing(capability, detail)
    return fn


# ── SettingsReadService ──────────────────────────────────────────────


class SettingsReadService:
    """Facade over :class:`SettingsService` for MCP."""

    def __init__(self, *, settings: SettingsService) -> None:
        self._settings = cast("Any", settings)

    async def list_settings(self) -> Mapping[str, object]:
        fn = _require_callable(
            self._settings,
            "snapshot",
            "settings_list",
            "SettingsService does not expose snapshot()",
        )
        return dict(fn())

    async def get_setting(self, key: NotBlankStr) -> object | None:
        fn = _require_callable(
            self._settings,
            "snapshot",
            "settings_get",
            "SettingsService does not expose snapshot()",
        )
        return dict(fn()).get(key)

    async def update_setting(
        self,
        *,
        key: NotBlankStr,
        value: object,
        actor_id: NotBlankStr,
    ) -> None:
        fn = _require_callable(
            self._settings,
            "set",
            "settings_update",
            "SettingsService does not expose a mutator",
        )
        await fn(key=key, value=value, actor=actor_id)
        logger.info(SETTINGS_VALUE_SET, key=key, actor_id=actor_id)

    async def delete_setting(
        self,
        *,
        key: NotBlankStr,
        actor_id: NotBlankStr,
        reason: NotBlankStr,
    ) -> None:
        fn = _require_callable(
            self._settings,
            "delete",
            "settings_delete",
            "SettingsService does not expose delete",
        )
        await fn(key=key, actor=actor_id)
        logger.info(
            SETTINGS_VALUE_DELETED,
            key=key,
            actor_id=actor_id,
            reason=reason,
        )


# ── ProviderReadService ──────────────────────────────────────────────


class ProviderReadService:
    """Facade over provider registry + health tracker + management."""

    def __init__(
        self,
        *,
        registry: ProviderRegistry,
        health: ProviderHealthTracker,
        management: ProviderManagementService,
    ) -> None:
        self._registry = cast("Any", registry)
        self._health = cast("Any", health)
        self._management = cast("Any", management)

    async def list_providers(self) -> Sequence[object]:
        fn = _require_callable(
            self._registry,
            "list_providers",
            "provider_list",
            "ProviderRegistry does not expose list_providers",
        )
        return tuple(fn())

    async def get_provider(self, provider_id: NotBlankStr) -> object | None:
        fn = _require_callable(
            self._registry,
            "get_provider",
            "provider_get",
            "ProviderRegistry does not expose get_provider",
        )
        return cast("object | None", fn(provider_id))

    async def get_health(
        self,
        provider_id: NotBlankStr | None = None,
    ) -> Mapping[str, object]:
        status_fn = _require_callable(
            self._health,
            "get_status",
            "provider_health",
            "ProviderHealthTracker does not expose get_status",
        )
        if provider_id is None:
            ids_fn = _require_callable(
                self._registry,
                "list_provider_ids",
                "provider_health",
                "ProviderRegistry does not expose list_provider_ids",
            )
            return {pid: status_fn(pid) for pid in ids_fn()}
        return {provider_id: status_fn(provider_id)}

    async def test_connection(
        self,
        provider_id: NotBlankStr,
    ) -> Mapping[str, object]:
        fn = _require_callable(
            self._management,
            "test_provider",
            "provider_test",
            "ProviderManagementService does not expose test_provider",
        )
        return {"provider_id": provider_id, "result": await fn(provider_id)}


# ── BackupFacadeService ──────────────────────────────────────────────


class BackupFacadeService:
    """Facade wrapping :class:`BackupService`."""

    def __init__(self, *, service: CoreBackupService) -> None:
        self._service = cast("Any", service)

    async def list_backups(self) -> Sequence[object]:
        return tuple(await self._service.list_backups())

    async def get_backup(self, backup_id: NotBlankStr) -> object:
        return await self._service.get_backup(backup_id)

    async def create_backup(
        self,
        *,
        trigger: object,
        components: object = None,
    ) -> object:
        return await self._service.create_backup(trigger=trigger, components=components)

    async def delete_backup(
        self,
        *,
        backup_id: NotBlankStr,
        actor_id: NotBlankStr,
        reason: NotBlankStr,
    ) -> None:
        await self._service.delete_backup(backup_id)
        logger.info(
            "backup.deleted_via_mcp",
            backup_id=backup_id,
            actor_id=actor_id,
            reason=reason,
        )

    async def restore_backup(
        self,
        *,
        backup_id: NotBlankStr,
        actor_id: NotBlankStr,
        reason: NotBlankStr,
    ) -> Mapping[str, object]:
        logger.info(
            "backup.restore_via_mcp",
            backup_id=backup_id,
            actor_id=actor_id,
            reason=reason,
        )
        await self._service.restore_from_backup(backup_id)
        return {"backup_id": backup_id, "restored": True}


# ── UserService ──────────────────────────────────────────────────────


class UserFacadeService:
    """Facade over :class:`AuthService` for user CRUD."""

    def __init__(self, *, auth_service: AuthService) -> None:
        self._auth = cast("Any", auth_service)

    async def list_users(self) -> Sequence[object]:
        fn = _require_callable(
            self._auth,
            "list_users",
            "user_list",
            "AuthService does not expose list_users; populate via durable user repository",
        )
        return tuple(await fn())

    async def get_user(self, user_id: NotBlankStr) -> object | None:
        fn = _require_callable(
            self._auth,
            "get_user",
            "user_get",
            "AuthService does not expose get_user",
        )
        return cast("object | None", await fn(user_id))

    async def create_user(self) -> None:
        raise _capability_missing(
            "user_create",
            "users are provisioned via the onboarding flow, not MCP",
        )

    async def update_user(self) -> None:
        raise _capability_missing(
            "user_update",
            "user mutations go through the auth controller, not MCP",
        )

    async def delete_user(
        self,
        *,
        user_id: NotBlankStr,  # noqa: ARG002 - part of public contract
        actor_id: NotBlankStr,  # noqa: ARG002
        reason: NotBlankStr,  # noqa: ARG002
    ) -> None:
        raise _capability_missing(
            "user_delete",
            "user deletion is a protected operator workflow",
        )


# ── ProjectService ──────────────────────────────────────────────────


class _ProjectRecord:
    __slots__ = ("created_at", "description", "id", "metadata", "name")

    def __init__(
        self,
        *,
        id: UUID,  # noqa: A002
        name: str,
        description: str,
        created_at: datetime,
        metadata: Mapping[str, str] | None = None,
    ) -> None:
        self.id = id
        self.name = name
        self.description = description
        self.created_at = created_at
        self.metadata = dict(metadata or {})

    def to_dict(self) -> dict[str, object]:
        return {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "metadata": dict(self.metadata),
        }


class ProjectFacadeService:
    """In-process project CRUD facade."""

    def __init__(self) -> None:
        self._projects: dict[UUID, _ProjectRecord] = {}

    async def list_projects(self) -> Sequence[_ProjectRecord]:
        return tuple(
            sorted(
                self._projects.values(),
                key=lambda p: p.created_at,
                reverse=True,
            ),
        )

    async def get_project(self, project_id: NotBlankStr) -> _ProjectRecord | None:
        try:
            key = UUID(project_id)
        except ValueError:
            return None
        return self._projects.get(key)

    async def create_project(
        self,
        *,
        name: NotBlankStr,
        description: NotBlankStr,
        actor_id: NotBlankStr,
        metadata: Mapping[str, str] | None = None,
    ) -> _ProjectRecord:
        record = _ProjectRecord(
            id=uuid4(),
            name=name,
            description=description,
            created_at=datetime.now(UTC),
            metadata=metadata,
        )
        self._projects[record.id] = record
        logger.info(
            "projects.created_via_mcp",
            project_id=str(record.id),
            actor_id=actor_id,
        )
        return record

    async def update_project(
        self,
        *,
        project_id: NotBlankStr,
        actor_id: NotBlankStr,
        name: NotBlankStr | None = None,
        description: NotBlankStr | None = None,
        metadata: Mapping[str, str] | None = None,
    ) -> _ProjectRecord | None:
        try:
            key = UUID(project_id)
        except ValueError:
            return None
        record = self._projects.get(key)
        if record is None:
            return None
        if name is not None:
            record.name = name
        if description is not None:
            record.description = description
        if metadata is not None:
            record.metadata = dict(metadata)
        logger.info(
            "projects.updated_via_mcp",
            project_id=project_id,
            actor_id=actor_id,
        )
        return record

    async def delete_project(
        self,
        *,
        project_id: NotBlankStr,
        actor_id: NotBlankStr,
        reason: NotBlankStr,
    ) -> bool:
        try:
            key = UUID(project_id)
        except ValueError:
            return False
        removed = self._projects.pop(key, None) is not None
        logger.info(
            "projects.deleted_via_mcp",
            project_id=project_id,
            actor_id=actor_id,
            reason=reason,
            removed=removed,
        )
        return removed


# ── RequestsService ─────────────────────────────────────────────────


class _RequestRecord:
    __slots__ = ("body", "created_at", "id", "requested_by", "title")

    def __init__(
        self,
        *,
        id: UUID,  # noqa: A002
        title: str,
        body: str,
        requested_by: str,
        created_at: datetime,
    ) -> None:
        self.id = id
        self.title = title
        self.body = body
        self.requested_by = requested_by
        self.created_at = created_at

    def to_dict(self) -> dict[str, object]:
        return {
            "id": str(self.id),
            "title": self.title,
            "body": self.body,
            "requested_by": self.requested_by,
            "created_at": self.created_at.isoformat(),
        }


class RequestsFacadeService:
    """In-process operator-request facade."""

    def __init__(self) -> None:
        self._requests: dict[UUID, _RequestRecord] = {}

    async def list_requests(self) -> Sequence[_RequestRecord]:
        return tuple(
            sorted(
                self._requests.values(),
                key=lambda r: r.created_at,
                reverse=True,
            ),
        )

    async def get_request(self, request_id: NotBlankStr) -> _RequestRecord | None:
        try:
            key = UUID(request_id)
        except ValueError:
            return None
        return self._requests.get(key)

    async def create_request(
        self,
        *,
        title: NotBlankStr,
        body: NotBlankStr,
        requested_by: NotBlankStr,
    ) -> _RequestRecord:
        record = _RequestRecord(
            id=uuid4(),
            title=title,
            body=body,
            requested_by=requested_by,
            created_at=datetime.now(UTC),
        )
        self._requests[record.id] = record
        logger.info(
            "requests.created_via_mcp",
            request_id=str(record.id),
            requested_by=requested_by,
        )
        return record


# ── SetupService ────────────────────────────────────────────────────


class SetupFacadeService:
    """Setup status + initialisation facade."""

    def __init__(self) -> None:
        self._initialised_at: datetime | None = None

    async def get_status(self) -> Mapping[str, object]:
        return {
            "initialised": self._initialised_at is not None,
            "initialised_at": (
                self._initialised_at.isoformat()
                if self._initialised_at is not None
                else None
            ),
        }

    async def initialize(self) -> None:
        raise _capability_missing(
            "setup_initialize",
            "initialisation is driven through the setup controller + CLI wizard",
        )


# ── SimulationService ──────────────────────────────────────────────


class SimulationFacadeService:
    """Facade over :class:`ClientSimulationState`."""

    def __init__(self, *, state: ClientSimulationState) -> None:
        self._state = cast("Any", state)

    async def list_simulations(self) -> Sequence[object]:
        fn = getattr(self._state, "list_scenarios", None)
        if callable(fn):
            return tuple(fn())
        return ()

    async def get_simulation(self, simulation_id: NotBlankStr) -> object | None:
        fn = getattr(self._state, "get_scenario", None)
        if callable(fn):
            return cast("object | None", fn(simulation_id))
        return None

    async def create_simulation(self) -> None:
        raise _capability_missing(
            "simulation_create",
            "simulation scenarios are loaded from config at start-up",
        )


# ── TemplatePackService ────────────────────────────────────────────


class _TemplatePackRecord:
    __slots__ = ("id", "installed_at", "name", "version")

    def __init__(
        self,
        *,
        id: UUID,  # noqa: A002
        name: str,
        version: str,
        installed_at: datetime,
    ) -> None:
        self.id = id
        self.name = name
        self.version = version
        self.installed_at = installed_at

    def to_dict(self) -> dict[str, object]:
        return {
            "id": str(self.id),
            "name": self.name,
            "version": self.version,
            "installed_at": self.installed_at.isoformat(),
        }


class TemplatePackFacadeService:
    """In-process template-pack registry."""

    def __init__(self) -> None:
        self._packs: dict[UUID, _TemplatePackRecord] = {}

    async def list_packs(self) -> Sequence[_TemplatePackRecord]:
        return tuple(
            sorted(
                self._packs.values(),
                key=lambda p: p.installed_at,
                reverse=True,
            ),
        )

    async def get_pack(self, pack_id: NotBlankStr) -> _TemplatePackRecord | None:
        try:
            key = UUID(pack_id)
        except ValueError:
            return None
        return self._packs.get(key)

    async def install_pack(
        self,
        *,
        name: NotBlankStr,
        version: NotBlankStr,
        actor_id: NotBlankStr,
    ) -> _TemplatePackRecord:
        record = _TemplatePackRecord(
            id=uuid4(),
            name=name,
            version=version,
            installed_at=datetime.now(UTC),
        )
        self._packs[record.id] = record
        logger.info(
            "template_packs.installed_via_mcp",
            pack_id=str(record.id),
            pack_name=name,
            actor_id=actor_id,
        )
        return record

    async def uninstall_pack(
        self,
        *,
        pack_id: NotBlankStr,
        actor_id: NotBlankStr,
        reason: NotBlankStr,
    ) -> bool:
        try:
            key = UUID(pack_id)
        except ValueError:
            return False
        removed = self._packs.pop(key, None) is not None
        logger.info(
            "template_packs.uninstalled_via_mcp",
            pack_id=pack_id,
            actor_id=actor_id,
            reason=reason,
            removed=removed,
        )
        return removed


# ── AuditReadService ────────────────────────────────────────────────


class AuditReadService:
    """Read facade over :class:`AuditLog`."""

    def __init__(self, *, audit_log: AuditLog) -> None:
        self._audit = cast("Any", audit_log)

    async def list_entries(self, *, limit: int = 100) -> Sequence[object]:
        fn = getattr(self._audit, "list_entries", None)
        if callable(fn):
            return tuple(fn())[:limit]
        return ()


# ── EventsReadService ──────────────────────────────────────────────


class EventsReadService:
    """Read facade over :class:`EventStreamHub`."""

    def __init__(self, *, hub: EventStreamHub) -> None:
        self._hub = cast("Any", hub)

    async def list_events(self, *, limit: int = 100) -> Sequence[object]:
        fn = getattr(self._hub, "recent_events", None)
        if callable(fn):
            return tuple(fn(limit=limit))
        return ()


# ── IntegrationHealthService ──────────────────────────────────────


class IntegrationHealthFacadeService:
    """Read facade over :class:`HealthProberService`."""

    def __init__(self, *, prober: HealthProberService) -> None:
        self._prober = cast("Any", prober)

    async def get_all(self) -> Mapping[str, object]:
        fn = getattr(self._prober, "snapshot", None)
        if callable(fn):
            return dict(fn())
        return {}

    async def get_one(self, integration_id: NotBlankStr) -> object | None:
        snapshot = await self.get_all()
        return snapshot.get(integration_id)


__all__ = [
    "AuditReadService",
    "BackupFacadeService",
    "EventsReadService",
    "IntegrationHealthFacadeService",
    "ProjectFacadeService",
    "ProviderReadService",
    "RequestsFacadeService",
    "SettingsReadService",
    "SetupFacadeService",
    "SimulationFacadeService",
    "TemplatePackFacadeService",
    "UserFacadeService",
]
