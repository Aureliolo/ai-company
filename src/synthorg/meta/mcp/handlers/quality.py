"""Quality domain MCP handlers.

9 tools covering quality scores, reviews, and evaluation-config version
history.  The quality subsystem in the engine is protocol-based
(``RubricGrader``, ``CriteriaDecomposer``) and the concrete scoring
store is reached via ``performance_tracker.quality_override_store``,
which is not designed as a read surface.  Reviews and evaluation
versions have dedicated controllers but no service facade on
``app_state``; every handler returns a ``not_supported`` envelope
built via the shared :func:`_mk` factory (same pattern as ``signals``
and ``organization``) so actor typing stays consistent.
"""

from collections.abc import Mapping  # noqa: TC003 -- PEP 649 annotation
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from synthorg.meta.mcp.handler_protocol import (
    ToolHandler,  # noqa: TC001 -- PEP 649 annotation
)
from synthorg.meta.mcp.handlers.common import not_supported
from synthorg.observability import get_logger

if TYPE_CHECKING:
    from synthorg.core.agent import AgentIdentity

logger = get_logger(__name__)

_WHY_QUALITY = (
    "quality metrics are derived inside performance_tracker's scoring "
    "strategy; no public read method is exposed on app_state"
)
_WHY_REVIEWS = (
    "review-gate operations require review_gate_service + task "
    "context; use the /reviews REST API"
)
_WHY_EVAL_VERSIONS = (
    "evaluation-config version history lives behind its own "
    "controller; no service facade on app_state"
)


def _mk(tool: str, why: str) -> ToolHandler:
    """Build a ``not_supported`` handler with ToolHandler-conformant typing."""

    async def handler(
        *,
        app_state: Any,  # noqa: ARG001
        arguments: dict[str, Any],  # noqa: ARG001
        actor: AgentIdentity | None = None,  # noqa: ARG001
    ) -> str:
        return not_supported(tool, why)

    return handler


QUALITY_HANDLERS: Mapping[str, ToolHandler] = MappingProxyType(
    {
        "synthorg_quality_get_summary": _mk(
            "synthorg_quality_get_summary",
            _WHY_QUALITY,
        ),
        "synthorg_quality_get_agent_quality": _mk(
            "synthorg_quality_get_agent_quality",
            _WHY_QUALITY,
        ),
        "synthorg_quality_list_scores": _mk(
            "synthorg_quality_list_scores",
            _WHY_QUALITY,
        ),
        "synthorg_reviews_list": _mk("synthorg_reviews_list", _WHY_REVIEWS),
        "synthorg_reviews_get": _mk("synthorg_reviews_get", _WHY_REVIEWS),
        "synthorg_reviews_create": _mk("synthorg_reviews_create", _WHY_REVIEWS),
        "synthorg_reviews_update": _mk("synthorg_reviews_update", _WHY_REVIEWS),
        "synthorg_evaluation_versions_list": _mk(
            "synthorg_evaluation_versions_list",
            _WHY_EVAL_VERSIONS,
        ),
        "synthorg_evaluation_versions_get": _mk(
            "synthorg_evaluation_versions_get",
            _WHY_EVAL_VERSIONS,
        ),
    },
)
