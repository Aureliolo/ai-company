"""Repository protocol for custom personality preset persistence.

Extracted into its own module because ``repositories.py`` is at the
800-line file-size limit (same pattern as ``artifact_project_repos.py``).
"""

from typing import Protocol, runtime_checkable

from synthorg.core.types import NotBlankStr  # noqa: TC001


@runtime_checkable
class PersonalityPresetRepository(Protocol):
    """CRUD interface for user-defined personality preset persistence.

    Stores custom presets as JSON blobs alongside metadata.
    Builtin presets live in code and are never persisted here.
    """

    async def save(
        self,
        name: NotBlankStr,
        config_json: str,
        description: str,
        created_at: str,
        updated_at: str,
    ) -> None:
        """Persist a custom preset (insert or update on conflict).

        Args:
            name: Lowercase preset identifier (primary key).
            config_json: Serialized ``PersonalityConfig`` as JSON.
            description: Human-readable description.
            created_at: ISO 8601 creation timestamp.
            updated_at: ISO 8601 last-update timestamp.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...

    async def get(
        self,
        name: NotBlankStr,
    ) -> tuple[str, str, str, str] | None:
        """Retrieve a custom preset by name.

        Args:
            name: Preset identifier.

        Returns:
            ``(config_json, description, created_at, updated_at)``
            or ``None`` if not found.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...

    async def list_all(
        self,
    ) -> tuple[tuple[str, str, str, str, str], ...]:
        """List all custom presets ordered by name.

        Returns:
            Tuples of ``(name, config_json, description, created_at,
            updated_at)``.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...

    async def delete(self, name: NotBlankStr) -> bool:
        """Delete a custom preset by name.

        Args:
            name: Preset identifier.

        Returns:
            ``True`` if a row was deleted, ``False`` if not found.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...

    async def count(self) -> int:
        """Return the number of stored custom presets.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...
