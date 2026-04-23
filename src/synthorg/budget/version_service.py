"""Service facade for ``BudgetConfig`` version history reads.

Wraps the :class:`VersionRepository` for ``BudgetConfig`` so MCP
handlers (and any other caller) can read snapshot history without
reaching into ``app_state.persistence`` directly, keeping the
persistence boundary closed from the controller edge.
"""

from typing import TYPE_CHECKING

from synthorg.observability import get_logger

if TYPE_CHECKING:
    from synthorg.budget.config import BudgetConfig
    from synthorg.persistence.version_repo import VersionRepository
    from synthorg.versioning.models import VersionSnapshot

logger = get_logger(__name__)

_ENTITY_ID = "default"


class BudgetConfigVersionsService:
    """Read facade over the ``BudgetConfig`` version snapshot repository.

    Exposes exactly the three read methods MCP / REST callers need
    (``list_versions``, ``count_versions``, ``get_version``) so the
    underlying :class:`VersionRepository` stays inside
    ``synthorg.persistence`` and consumers stay on the service layer.

    Args:
        version_repo: The ``VersionRepository[BudgetConfig]`` instance
            from the persistence backend.
    """

    def __init__(
        self,
        *,
        version_repo: VersionRepository[BudgetConfig],
    ) -> None:
        self._repo = version_repo

    async def list_versions(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[tuple[VersionSnapshot[BudgetConfig], ...], int]:
        """Return a page of budget config version snapshots + total count.

        Args:
            limit: Page size.
            offset: Page offset.

        Returns:
            Tuple of ``(snapshots, total)`` where ``total`` is the
            unfiltered count reported by the repository.
        """
        versions = await self._repo.list_versions(
            _ENTITY_ID,
            limit=limit,
            offset=offset,
        )
        total = await self._repo.count_versions(_ENTITY_ID)
        return versions, total

    async def get_version(
        self,
        version_num: int,
    ) -> VersionSnapshot[BudgetConfig] | None:
        """Fetch a single version snapshot by number.

        Args:
            version_num: The 1-indexed version number.

        Returns:
            The snapshot record, or ``None`` if the version is missing.
        """
        return await self._repo.get_version(_ENTITY_ID, version_num)
