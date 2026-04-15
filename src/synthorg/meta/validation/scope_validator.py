"""Scope validator for code modification proposals.

Enforces path restrictions via allowlist/denylist glob patterns,
ensuring generated code changes target only permitted areas of
the framework.
"""

from fnmatch import fnmatch
from typing import TYPE_CHECKING

from synthorg.observability import get_logger
from synthorg.observability.events.meta import META_CODE_SCOPE_VIOLATION

if TYPE_CHECKING:
    from synthorg.meta.models import CodeChange

logger = get_logger(__name__)


class ScopeValidator:
    """Validates that proposed code changes target allowed paths.

    A path is allowed if it matches at least one ``allowed_paths``
    pattern AND matches no ``forbidden_paths`` patterns. Forbidden
    patterns always take precedence over allowed patterns.

    Args:
        allowed_paths: Glob patterns for permitted file paths.
        forbidden_paths: Glob patterns for forbidden file paths.
    """

    def __init__(
        self,
        *,
        allowed_paths: tuple[str, ...],
        forbidden_paths: tuple[str, ...],
    ) -> None:
        self._allowed = allowed_paths
        self._forbidden = forbidden_paths

    def is_path_allowed(self, file_path: str) -> bool:
        """Check if a single file path is within scope.

        Args:
            file_path: Relative path from project root.

        Returns:
            True if the path is allowed, False otherwise.
        """
        normalized = file_path.replace("\\", "/")
        for pattern in self._forbidden:
            if fnmatch(normalized, pattern):
                return False
        return any(fnmatch(normalized, p) for p in self._allowed)

    def validate_changes(
        self,
        changes: tuple[CodeChange, ...],
    ) -> tuple[str, ...]:
        """Validate all code changes against scope restrictions.

        Args:
            changes: Proposed code changes to validate.

        Returns:
            Tuple of violation descriptions (empty if all valid).
        """
        violations: list[str] = []
        for change in changes:
            if not self.is_path_allowed(change.file_path):
                violation = (
                    f"Path '{change.file_path}' is outside "
                    f"allowed scope for code modifications"
                )
                violations.append(violation)
                logger.warning(
                    META_CODE_SCOPE_VIOLATION,
                    file_path=change.file_path,
                    operation=change.operation.value,
                )
        return tuple(violations)
