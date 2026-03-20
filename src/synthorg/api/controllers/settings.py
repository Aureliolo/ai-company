"""Settings controller — CRUD for runtime-editable settings."""

from litestar import Controller, delete, get, put
from litestar.datastructures import State  # noqa: TC002
from litestar.exceptions import (
    ClientException,
    InternalServerException,
    NotFoundException,
)
from litestar.status_codes import HTTP_204_NO_CONTENT
from pydantic import BaseModel, ConfigDict, Field

from synthorg.api.dto import ApiResponse
from synthorg.api.guards import require_read_access, require_write_access
from synthorg.api.path_params import PathKey, PathNamespace  # noqa: TC001
from synthorg.api.state import AppState  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.settings import SETTINGS_ENCRYPTION_ERROR
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
        guards=[require_write_access],
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
        guards=[require_write_access],
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
