"""MCP server catalog service.

Provides browsing, searching, and installation of curated
MCP servers from the bundled catalog.
"""

import json
from pathlib import Path

from synthorg.core.types import NotBlankStr
from synthorg.integrations.connections.models import (
    CatalogEntry,
    ConnectionType,
)
from synthorg.integrations.errors import CatalogEntryNotFoundError
from synthorg.observability import get_logger
from synthorg.observability.events.integrations import (
    MCP_CATALOG_BROWSED,
    MCP_SERVER_INSTALL_FAILED,
)

logger = get_logger(__name__)

_BUNDLED_PATH = Path(__file__).parent / "bundled.json"


class CatalogService:
    """Browse, search, and install MCP servers from the bundled catalog.

    The catalog is a static JSON file shipped with the package.
    Each entry describes an MCP server with its NPM package, required
    connection type, transport, and capabilities.

    Args:
        catalog_path: Path to the bundled JSON catalog.
    """

    def __init__(
        self,
        catalog_path: Path | None = None,
    ) -> None:
        self._path = catalog_path or _BUNDLED_PATH
        self._entries: tuple[CatalogEntry, ...] = ()
        self._loaded = False

    def _load(self) -> None:
        """Load the catalog from disk (lazy, once)."""
        if self._loaded:
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            servers = raw.get("servers", [])
            entries = []
            for s in servers:
                conn_type = s.get("required_connection_type")
                entries.append(
                    CatalogEntry(
                        id=NotBlankStr(s["id"]),
                        name=NotBlankStr(s["name"]),
                        description=s.get("description", ""),
                        npm_package=(
                            NotBlankStr(s["npm_package"])
                            if s.get("npm_package")
                            else None
                        ),
                        required_connection_type=(
                            ConnectionType(conn_type) if conn_type else None
                        ),
                        transport=s.get("transport", "stdio"),
                        capabilities=tuple(s.get("capabilities", ())),
                        tags=tuple(s.get("tags", ())),
                    ),
                )
            self._entries = tuple(entries)
        except json.JSONDecodeError, KeyError, FileNotFoundError:
            logger.exception(
                MCP_SERVER_INSTALL_FAILED,
                error="failed to load bundled catalog",
            )
            self._entries = ()
        self._loaded = True

    async def browse(self) -> tuple[CatalogEntry, ...]:
        """Return all catalog entries.

        Returns:
            Tuple of all curated MCP server entries.
        """
        self._load()
        logger.debug(MCP_CATALOG_BROWSED, count=len(self._entries))
        return self._entries

    async def search(self, query: str) -> tuple[CatalogEntry, ...]:
        """Search catalog by name, description, or tags.

        Args:
            query: Search query string (case-insensitive).

        Returns:
            Matching entries.
        """
        self._load()
        q = query.lower()
        return tuple(
            e
            for e in self._entries
            if q in e.name.lower()
            or q in e.description.lower()
            or any(q in tag.lower() for tag in e.tags)
        )

    async def get_entry(self, entry_id: str) -> CatalogEntry:
        """Look up a catalog entry by ID.

        Raises:
            CatalogEntryNotFoundError: If the entry does not exist.
        """
        self._load()
        for entry in self._entries:
            if entry.id == entry_id:
                return entry
        msg = f"Catalog entry '{entry_id}' not found"
        raise CatalogEntryNotFoundError(msg)
