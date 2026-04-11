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
    MCP_CATALOG_ENTRY_NOT_FOUND,
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
        """Load the catalog from disk (lazy, once).

        A corrupt or missing bundled catalog is a release-time
        regression, not a runtime degradation: log the failure
        with full traceback and re-raise so callers see an error
        instead of silently reading an empty catalog.
        """
        if self._loaded:
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            # Guard root/entry shapes so a malformed file like ``[]``
            # or ``{"servers": ["oops"]}`` surfaces through the same
            # logged failure path instead of escaping as an unlogged
            # ``AttributeError`` on the ``raw.get`` / ``s.get`` calls.
            if not isinstance(raw, dict):
                msg = "bundled catalog root must be a JSON object"
                raise TypeError(msg)  # noqa: TRY301
            servers = raw.get("servers", [])
            if not isinstance(servers, list):
                msg = "bundled catalog 'servers' must be a list"
                raise TypeError(msg)  # noqa: TRY301
            entries = []
            for s in servers:
                if not isinstance(s, dict):
                    msg = "bundled catalog entry must be a JSON object"
                    raise TypeError(msg)  # noqa: TRY301
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
        except json.JSONDecodeError, KeyError, FileNotFoundError:
            logger.exception(
                MCP_SERVER_INSTALL_FAILED,
                error="failed to load bundled catalog",
            )
            raise
        except ValueError, TypeError, AttributeError:
            # Catches ``ConnectionType(conn_type)`` enum rejection,
            # the shape-guard TypeErrors above, ``CatalogEntry``
            # Pydantic validation errors, and any residual
            # ``AttributeError`` from an unexpected payload shape
            # (belt-and-braces) so malformed bundled entries always
            # surface as a logged failure instead of escaping silently.
            logger.exception(
                MCP_SERVER_INSTALL_FAILED,
                error="bundled catalog entry failed model validation",
            )
            raise
        self._entries = tuple(entries)
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
        logger.warning(
            MCP_CATALOG_ENTRY_NOT_FOUND,
            entry_id=entry_id,
            known_count=len(self._entries),
        )
        msg = f"Catalog entry '{entry_id}' not found"
        raise CatalogEntryNotFoundError(msg)
