"""Route guards for access control.

Guards read the authenticated user identity from ``connection.user``
(populated by the auth middleware) and check role-based permissions.

The ``require_roles`` factory creates guards for arbitrary role sets.
Pre-built constants cover common patterns::

    require_ceo              -- CEO only
    require_ceo_or_manager   -- CEO or Manager
    require_approval_roles   -- CEO, Manager, or Board Member
"""

from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

from litestar.connection import ASGIConnection  # noqa: TC002
from litestar.exceptions import PermissionDeniedException

from synthorg.observability import get_logger
from synthorg.observability.events.api import API_GUARD_DENIED

logger = get_logger(__name__)


class HumanRole(StrEnum):
    """Recognised human roles for access control."""

    CEO = "ceo"
    MANAGER = "manager"
    BOARD_MEMBER = "board_member"
    PAIR_PROGRAMMER = "pair_programmer"
    OBSERVER = "observer"
    SYSTEM = "system"


# --- Role sets --------------------------------------------------------

_WRITE_ROLES: frozenset[HumanRole] = frozenset(
    {
        HumanRole.CEO,
        HumanRole.MANAGER,
        HumanRole.PAIR_PROGRAMMER,
    }
)
_READ_ROLES: frozenset[HumanRole] = _WRITE_ROLES | frozenset(
    {HumanRole.OBSERVER, HumanRole.BOARD_MEMBER},
)


def _get_role(connection: ASGIConnection) -> HumanRole | None:  # type: ignore[type-arg]
    """Extract the human role from the authenticated user."""
    user = connection.scope.get("user")
    if user is not None and hasattr(user, "role"):
        try:
            return HumanRole(user.role)
        except ValueError:
            logger.warning(
                API_GUARD_DENIED,
                guard="_get_role",
                invalid_role=str(user.role),
                path=str(connection.url.path),
            )
            return None
    return None


def has_write_role(role: HumanRole) -> bool:
    """Return True if the role grants write access.

    Use this for inline role checks instead of importing ``_WRITE_ROLES``
    directly.  The write set includes CEO, Manager, and Pair Programmer.
    """
    return role in _WRITE_ROLES


def require_write_access(
    connection: ASGIConnection,  # type: ignore[type-arg]
    _: object,
) -> None:
    """Guard that allows only write-capable human roles.

    Checks ``connection.user.role`` for ``ceo``, ``manager``,
    or ``pair_programmer``.  Board members are excluded (they
    may only observe and approve).  The ``system`` role is
    intentionally excluded -- use ``require_roles()`` with the
    desired roles for endpoints the CLI needs to reach.

    Args:
        connection: The incoming connection.
        _: Route handler (unused).

    Raises:
        PermissionDeniedException: If the role is not permitted.
    """
    role = _get_role(connection)
    if role not in _WRITE_ROLES:
        logger.warning(
            API_GUARD_DENIED,
            guard="require_write_access",
            role=role,
            path=str(connection.url.path),
        )
        raise PermissionDeniedException(detail="Write access denied")


def require_read_access(
    connection: ASGIConnection,  # type: ignore[type-arg]
    _: object,
) -> None:
    """Guard that allows all human roles (excludes SYSTEM).

    Checks ``connection.user.role`` for any human role
    including ``observer`` and ``board_member``.  The internal
    ``system`` role is excluded -- use ``require_roles()`` for
    endpoints the CLI needs to reach.

    Args:
        connection: The incoming connection.
        _: Route handler (unused).

    Raises:
        PermissionDeniedException: If the role is not permitted.
    """
    role = _get_role(connection)
    if role not in _READ_ROLES:
        logger.warning(
            API_GUARD_DENIED,
            guard="require_read_access",
            role=role,
            path=str(connection.url.path),
        )
        raise PermissionDeniedException(detail="Read access denied")


# --- Guard factory ----------------------------------------------------


def require_roles(
    *roles: HumanRole,
) -> Callable[[ASGIConnection, object], None]:  # type: ignore[type-arg]
    """Create a guard that allows only the specified roles.

    Args:
        *roles: One or more ``HumanRole`` members to permit.

    Returns:
        A guard function compatible with Litestar's guard protocol.

    Raises:
        ValueError: If no roles are provided.
    """
    if not roles:
        msg = "require_roles() requires at least one role"
        raise ValueError(msg)

    allowed = frozenset(roles)
    label = ",".join(sorted(r.value for r in allowed))

    def guard(
        connection: ASGIConnection,  # type: ignore[type-arg]
        _: object,
    ) -> None:
        role = _get_role(connection)
        if role not in allowed:
            logger.warning(
                API_GUARD_DENIED,
                guard=f"require_roles({label})",
                role=role,
                path=str(connection.url.path),
            )
            raise PermissionDeniedException(detail="Access denied")

    guard.__name__ = f"require_roles({label})"
    guard.__qualname__ = f"require_roles({label})"
    return guard


# --- Named guard constants --------------------------------------------

require_ceo = require_roles(HumanRole.CEO)
"""Guard allowing only the CEO role."""

require_ceo_or_manager = require_roles(HumanRole.CEO, HumanRole.MANAGER)
"""Guard allowing CEO or Manager roles."""

require_approval_roles = require_roles(
    HumanRole.CEO,
    HumanRole.MANAGER,
    HumanRole.BOARD_MEMBER,
)
"""Guard allowing roles that can approve or reject actions."""
