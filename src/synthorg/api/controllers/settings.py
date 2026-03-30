"""Settings controller -- CRUD for runtime-editable settings."""

from typing import Any

from litestar import Controller, delete, get, post, put
from litestar.datastructures import State  # noqa: TC002
from litestar.exceptions import (
    ClientException,
    InternalServerException,
    NotFoundException,
)
from litestar.status_codes import HTTP_204_NO_CONTENT
from pydantic import BaseModel, ConfigDict, Field

from synthorg.api.dto import ApiResponse
from synthorg.api.guards import require_ceo_or_manager, require_read_access
from synthorg.api.path_params import PathKey, PathNamespace  # noqa: TC001
from synthorg.api.state import AppState  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.config import DEFAULT_SINKS, SinkConfig
from synthorg.observability.enums import LogLevel, SinkType
from synthorg.observability.events.settings import SETTINGS_ENCRYPTION_ERROR
from synthorg.observability.sink_config_builder import build_log_config_from_settings
from synthorg.settings.enums import SettingNamespace
from synthorg.settings.errors import (
    SettingNotFoundError,
    SettingsEncryptionError,
    SettingValidationError,
)
from synthorg.settings.models import SettingDefinition, SettingEntry  # noqa: TC001

logger = get_logger(__name__)

_VALID_NAMESPACES: frozenset[str] = frozenset(ns.value for ns in SettingNamespace)


class UpdateSettingRequest(BaseModel):
    """Request body for updating a setting value.

    Attributes:
        value: New value as a string (all types serialised).
    """

    model_config = ConfigDict(frozen=True)

    value: str = Field(max_length=8192, description="New value as string")


class TestSinkConfigRequest(BaseModel):
    """Request body for validating a sink configuration.

    Attributes:
        sink_overrides: JSON object of per-sink overrides.
        custom_sinks: JSON array of custom sink definitions.
    """

    model_config = ConfigDict(frozen=True)

    sink_overrides: str = Field(
        default="{}",
        max_length=65536,
        description="JSON object of per-sink overrides",
    )
    custom_sinks: str = Field(
        default="[]",
        max_length=65536,
        description="JSON array of custom sink definitions",
    )


class TestSinkConfigResponse(BaseModel):
    """Response body for sink configuration validation.

    Attributes:
        valid: Whether the configuration is valid.
        error: Validation error message (None when valid).
    """

    model_config = ConfigDict(frozen=True)

    valid: bool
    error: str | None = None


_CONSOLE_ID: str = "__console__"
_DEFAULT_FILE_PATHS: frozenset[str] = frozenset(
    s.file_path for s in DEFAULT_SINKS if s.file_path is not None
)


def _sink_to_dict(
    sink: SinkConfig,
    *,
    is_default: bool,
    routing_prefixes: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Convert a SinkConfig to a plain dict for API responses.

    Args:
        sink: Sink configuration to convert.
        is_default: Whether this is a default (built-in) sink.
        routing_prefixes: Custom routing prefixes (custom sinks only).

    Returns:
        Dict representation with all sink fields.
    """
    identifier: str
    if sink.sink_type == SinkType.CONSOLE:
        identifier = _CONSOLE_ID
    else:
        identifier = sink.file_path or ""

    rotation: dict[str, Any] | None = None
    if sink.rotation is not None:
        rotation = {
            "strategy": sink.rotation.strategy.value,
            "max_bytes": sink.rotation.max_bytes,
            "backup_count": sink.rotation.backup_count,
        }

    return {
        "identifier": identifier,
        "sink_type": sink.sink_type.value,
        "level": sink.level.value,
        "json_format": sink.json_format,
        "rotation": rotation,
        "is_default": is_default,
        "enabled": True,
        "routing_prefixes": list(routing_prefixes) if routing_prefixes else [],
    }


def _validate_namespace(namespace: str) -> None:
    """Raise 404 if namespace is not a known SettingNamespace member."""
    if namespace not in _VALID_NAMESPACES:
        msg = f"Unknown namespace: {namespace!r}"
        raise NotFoundException(msg)


class SettingsController(Controller):
    """CRUD for runtime-editable settings with schema introspection."""

    path = "/settings"
    tags = ("settings",)
    guards = [require_read_access]  # noqa: RUF012

    @get("/_schema")
    async def get_full_schema(
        self,
        state: State,
    ) -> ApiResponse[tuple[SettingDefinition, ...]]:
        """Return all setting definitions for UI schema generation.

        Args:
            state: Application state.

        Returns:
            All setting definitions.
        """
        app_state: AppState = state.app_state
        schema = app_state.settings_service.get_schema()
        return ApiResponse(data=schema)

    @get("/_schema/{namespace:str}")
    async def get_namespace_schema(
        self,
        state: State,
        namespace: PathNamespace,
    ) -> ApiResponse[tuple[SettingDefinition, ...]]:
        """Return setting definitions for a specific namespace.

        Args:
            state: Application state.
            namespace: Namespace to filter by.

        Returns:
            Definitions in the namespace.
        """
        _validate_namespace(namespace)
        app_state: AppState = state.app_state
        schema = app_state.settings_service.get_schema(namespace=namespace)
        return ApiResponse(data=schema)

    @get()
    async def list_all_settings(
        self,
        state: State,
    ) -> ApiResponse[tuple[SettingEntry, ...]]:
        """List all settings with resolved values.

        Sensitive values are masked.

        Args:
            state: Application state.

        Returns:
            All resolved setting entries.
        """
        app_state: AppState = state.app_state
        entries = await app_state.settings_service.get_all()
        return ApiResponse(data=entries)

    @get("/{namespace:str}")
    async def get_namespace_settings(
        self,
        state: State,
        namespace: PathNamespace,
    ) -> ApiResponse[tuple[SettingEntry, ...]]:
        """List resolved settings for a namespace.

        Args:
            state: Application state.
            namespace: Namespace to list.

        Returns:
            Resolved setting entries in the namespace.
        """
        _validate_namespace(namespace)
        app_state: AppState = state.app_state
        entries = await app_state.settings_service.get_namespace(namespace)
        return ApiResponse(data=entries)

    @get("/{namespace:str}/{key:str}")
    async def get_setting(
        self,
        state: State,
        namespace: PathNamespace,
        key: PathKey,
    ) -> ApiResponse[SettingEntry]:
        """Get a single resolved setting.

        Args:
            state: Application state.
            namespace: Setting namespace.
            key: Setting key.

        Returns:
            Resolved setting entry.
        """
        _validate_namespace(namespace)
        app_state: AppState = state.app_state
        try:
            entry = await app_state.settings_service.get_entry(namespace, key)
        except SettingNotFoundError as exc:
            raise NotFoundException(str(exc)) from exc
        return ApiResponse(data=entry)

    @put(
        "/{namespace:str}/{key:str}",
        guards=[require_ceo_or_manager],
    )
    async def update_setting(
        self,
        state: State,
        namespace: PathNamespace,
        key: PathKey,
        data: UpdateSettingRequest,
    ) -> ApiResponse[SettingEntry]:
        """Update a setting value.

        Args:
            state: Application state.
            namespace: Setting namespace.
            key: Setting key.
            data: Request body with new value.

        Returns:
            Updated setting entry.
        """
        _validate_namespace(namespace)
        app_state: AppState = state.app_state
        try:
            entry = await app_state.settings_service.set(namespace, key, data.value)
        except SettingNotFoundError as exc:
            raise NotFoundException(str(exc)) from exc
        except SettingValidationError as exc:
            raise ClientException(str(exc), status_code=422) from exc
        except SettingsEncryptionError:
            logger.exception(
                SETTINGS_ENCRYPTION_ERROR,
                namespace=namespace,
                key=key,
            )
            msg = "Internal error processing sensitive setting"
            raise InternalServerException(msg) from None
        return ApiResponse(data=entry)

    @delete(
        "/{namespace:str}/{key:str}",
        guards=[require_ceo_or_manager],
        status_code=HTTP_204_NO_CONTENT,
    )
    async def delete_setting(
        self,
        state: State,
        namespace: PathNamespace,
        key: PathKey,
    ) -> None:
        """Delete a DB override, reverting to next source in chain.

        Args:
            state: Application state.
            namespace: Setting namespace.
            key: Setting key.
        """
        _validate_namespace(namespace)
        app_state: AppState = state.app_state
        try:
            await app_state.settings_service.delete(namespace, key)
        except SettingNotFoundError as exc:
            raise NotFoundException(str(exc)) from exc

    # ── Observability sink endpoints ──────────────────────────────

    @get("/observability/sinks")
    async def list_sinks(
        self,
        state: State,
    ) -> ApiResponse[list[dict[str, Any]]]:
        """Return merged view of all configured log sinks.

        Reads ``sink_overrides`` and ``custom_sinks`` from settings,
        merges them with DEFAULT_SINKS via the sink config builder,
        and returns a flat list of all active sinks.

        Args:
            state: Application state.

        Returns:
            List of sink configuration dicts.
        """
        app_state: AppState = state.app_state
        svc = app_state.settings_service

        overrides_val = await svc.get(
            SettingNamespace.OBSERVABILITY,
            "sink_overrides",
        )
        custom_val = await svc.get(
            SettingNamespace.OBSERVABILITY,
            "custom_sinks",
        )

        result = build_log_config_from_settings(
            root_level=LogLevel.DEBUG,
            enable_correlation=True,
            sink_overrides_json=overrides_val.value,
            custom_sinks_json=custom_val.value,
        )

        sinks: list[dict[str, Any]] = []
        for sink in result.config.sinks:
            file_path = sink.file_path
            is_default = (
                sink.sink_type == SinkType.CONSOLE or file_path in _DEFAULT_FILE_PATHS
            )
            routing = (
                result.routing_overrides.get(file_path)
                if file_path is not None
                else None
            )
            sinks.append(
                _sink_to_dict(
                    sink,
                    is_default=is_default,
                    routing_prefixes=routing,
                )
            )

        # Also include disabled default sinks (those removed by overrides).
        active_ids = {s["identifier"] for s in sinks}
        for default_sink in DEFAULT_SINKS:
            identifier = (
                _CONSOLE_ID
                if default_sink.sink_type == SinkType.CONSOLE
                else (default_sink.file_path or "")
            )
            if identifier not in active_ids:
                entry = _sink_to_dict(
                    default_sink,
                    is_default=True,
                )
                entry["enabled"] = False
                sinks.append(entry)

        return ApiResponse(data=sinks)

    @post(
        "/observability/sinks/_test",
        guards=[require_ceo_or_manager],
    )
    async def test_sink_config(
        self,
        data: TestSinkConfigRequest,
    ) -> ApiResponse[TestSinkConfigResponse]:
        """Validate a sink configuration without persisting.

        Runs the sink config builder against the provided overrides
        and custom sinks to check for validation errors.

        Args:
            data: Request body with sink_overrides and custom_sinks.

        Returns:
            Validation result with valid flag and optional error.
        """
        try:
            build_log_config_from_settings(
                root_level=LogLevel.DEBUG,
                enable_correlation=True,
                sink_overrides_json=data.sink_overrides,
                custom_sinks_json=data.custom_sinks,
            )
        except ValueError as exc:
            return ApiResponse(
                data=TestSinkConfigResponse(valid=False, error=str(exc)),
            )
        return ApiResponse(
            data=TestSinkConfigResponse(valid=True),
        )
