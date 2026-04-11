"""MCP catalog installations.

Records catalog entries that the dashboard has installed, keyed by
catalog entry id. Persists out-of-band from the user-owned YAML
config so installs survive restarts without touching the file, and
so the MCP bridge can merge these rows into its effective server
list at startup (see :mod:`synthorg.integrations.mcp_catalog.install`).

The primary key on ``catalog_entry_id`` makes install idempotent:
re-installing the same entry is a safe upsert that refreshes
``installed_at`` and overwrites the associated ``connection_name``.
"""

from typing import Protocol, runtime_checkable

from pydantic import AwareDatetime, BaseModel, ConfigDict

from synthorg.core.types import NotBlankStr  # noqa: TC001


class McpInstallation(BaseModel):
    """A recorded MCP catalog installation.

    Attributes:
        catalog_entry_id: Unique id of the installed catalog entry.
        connection_name: Name of the bound connection, or ``None``
            for connectionless servers (filesystem, memory, etc.).
        installed_at: When the install was recorded.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    catalog_entry_id: NotBlankStr
    connection_name: NotBlankStr | None = None
    installed_at: AwareDatetime


@runtime_checkable
class McpInstallationRepository(Protocol):
    """CRUD interface for MCP catalog installations."""

    async def save(self, installation: McpInstallation) -> None:
        """Upsert an installation (idempotent on catalog_entry_id)."""
        ...

    async def get(self, catalog_entry_id: NotBlankStr) -> McpInstallation | None:
        """Fetch an installation by catalog entry id."""
        ...

    async def list_all(self) -> tuple[McpInstallation, ...]:
        """List all recorded installations."""
        ...

    async def delete(self, catalog_entry_id: NotBlankStr) -> bool:
        """Delete an installation.

        Returns:
            ``True`` if a row was deleted.
        """
        ...
