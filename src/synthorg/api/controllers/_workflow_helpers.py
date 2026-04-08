"""Shared helpers for workflow controllers."""

from typing import TYPE_CHECKING, Any

from synthorg.api.auth.models import AuthenticatedUser
from synthorg.observability import get_logger
from synthorg.observability.events.api import API_AUTH_USER_FALLBACK

if TYPE_CHECKING:
    from litestar import Request

logger = get_logger(__name__)


def get_auth_user_id(request: Request[Any, Any, Any]) -> str:
    """Extract the authenticated user ID from a request.

    Args:
        request: The incoming Litestar request.

    Returns:
        The user ID string, or ``"api"`` when no
        ``AuthenticatedUser`` is in scope.
    """
    auth_user = request.scope.get("user")
    if isinstance(auth_user, AuthenticatedUser):
        return auth_user.user_id
    logger.debug(
        API_AUTH_USER_FALLBACK,
        reason="no AuthenticatedUser in scope",
        path=request.url.path,
    )
    return "api"
