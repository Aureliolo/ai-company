"""Shared helpers for workflow controllers."""

from typing import TYPE_CHECKING, Any

from synthorg.api.auth.models import AuthenticatedUser
from synthorg.engine.workflow.version import WorkflowDefinitionVersion
from synthorg.observability import get_logger
from synthorg.observability.events.api import API_AUTH_USER_FALLBACK

if TYPE_CHECKING:
    from litestar import Request

    from synthorg.engine.workflow.definition import WorkflowDefinition

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


def build_version_snapshot(
    definition: WorkflowDefinition,
    saved_by: str,
) -> WorkflowDefinitionVersion:
    """Build a version snapshot from a definition.

    The snapshot's ``saved_at`` is set to the definition's
    ``updated_at`` timestamp, not the current time.

    Args:
        definition: The workflow definition to snapshot.
        saved_by: User ID of who triggered the save.

    Returns:
        An immutable ``WorkflowDefinitionVersion`` snapshot.
    """
    return WorkflowDefinitionVersion(
        definition_id=definition.id,
        version=definition.version,
        name=definition.name,
        description=definition.description,
        workflow_type=definition.workflow_type,
        nodes=definition.nodes,
        edges=definition.edges,
        created_by=definition.created_by,
        saved_by=saved_by,
        saved_at=definition.updated_at,
    )
