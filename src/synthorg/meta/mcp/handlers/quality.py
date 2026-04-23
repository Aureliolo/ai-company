"""Quality domain MCP handlers.

9 tools covering quality scores, reviews, and evaluation-config version
history.  The quality subsystem in the engine is protocol-based
(``RubricGrader``, ``CriteriaDecomposer``) and the concrete scoring
store is reached via ``performance_tracker.quality_override_store``,
which is not designed as a read surface.  Reviews and evaluation
versions have dedicated controllers but no service facade on
``app_state``; they return a ``not_supported`` envelope for now.
"""

from collections.abc import Mapping  # noqa: TC003 -- PEP 649 annotation
from types import MappingProxyType
from typing import Any

from synthorg.meta.mcp.handler_protocol import (
    ToolHandler,  # noqa: TC001 -- PEP 649 annotation
)
from synthorg.meta.mcp.handlers.common import not_supported
from synthorg.observability import get_logger

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


async def _quality_get_summary(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: Any = None,  # noqa: ARG001
) -> str:
    return not_supported("synthorg_quality_get_summary", _WHY_QUALITY)


async def _quality_get_agent_quality(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: Any = None,  # noqa: ARG001
) -> str:
    return not_supported("synthorg_quality_get_agent_quality", _WHY_QUALITY)


async def _quality_list_scores(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: Any = None,  # noqa: ARG001
) -> str:
    return not_supported("synthorg_quality_list_scores", _WHY_QUALITY)


async def _reviews_list(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: Any = None,  # noqa: ARG001
) -> str:
    return not_supported("synthorg_reviews_list", _WHY_REVIEWS)


async def _reviews_get(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: Any = None,  # noqa: ARG001
) -> str:
    return not_supported("synthorg_reviews_get", _WHY_REVIEWS)


async def _reviews_create(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: Any = None,  # noqa: ARG001
) -> str:
    return not_supported("synthorg_reviews_create", _WHY_REVIEWS)


async def _reviews_update(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: Any = None,  # noqa: ARG001
) -> str:
    return not_supported("synthorg_reviews_update", _WHY_REVIEWS)


async def _evaluation_versions_list(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: Any = None,  # noqa: ARG001
) -> str:
    return not_supported("synthorg_evaluation_versions_list", _WHY_EVAL_VERSIONS)


async def _evaluation_versions_get(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: Any = None,  # noqa: ARG001
) -> str:
    return not_supported("synthorg_evaluation_versions_get", _WHY_EVAL_VERSIONS)


QUALITY_HANDLERS: Mapping[str, ToolHandler] = MappingProxyType(
    {
        "synthorg_quality_get_summary": _quality_get_summary,
        "synthorg_quality_get_agent_quality": _quality_get_agent_quality,
        "synthorg_quality_list_scores": _quality_list_scores,
        "synthorg_reviews_list": _reviews_list,
        "synthorg_reviews_get": _reviews_get,
        "synthorg_reviews_create": _reviews_create,
        "synthorg_reviews_update": _reviews_update,
        "synthorg_evaluation_versions_list": _evaluation_versions_list,
        "synthorg_evaluation_versions_get": _evaluation_versions_get,
    },
)
