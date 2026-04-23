"""Meta (self-improvement) domain MCP handlers.

5 tools.  Two are live -- ``list_mcp_tools`` reflects the registry and
``get_mcp_server_config`` returns the server metadata.  The others
need a ``SelfImprovementService`` facade on ``app_state`` that is not
yet exposed, so they return ``not_supported``.
"""

from collections.abc import Mapping  # noqa: TC003 -- PEP 649 annotation
from types import MappingProxyType
from typing import Any

from synthorg.meta.mcp.handler_protocol import (
    ToolHandler,  # noqa: TC001 -- PEP 649 annotation
)
from synthorg.meta.mcp.handlers.common import err, not_supported, ok
from synthorg.observability import get_logger, safe_error_description
from synthorg.observability.events.mcp import (
    MCP_HANDLER_INVOKE_FAILED,
    MCP_HANDLER_INVOKE_SUCCESS,
)

logger = get_logger(__name__)


_WHY_CONFIG = (
    "self-improvement config read requires SelfImprovementService; "
    "no facade on app_state yet"
)
_WHY_RULES = (
    "custom-rule listing runs through the custom_rules controller; "
    "no service facade on app_state"
)
_WHY_TRIGGER = (
    "improvement-cycle triggering is invoked through the scheduler "
    "on app_state.ceremony_scheduler, not through an MCP entry point"
)


def _log_failed(tool: str, exc: Exception) -> None:
    logger.warning(
        MCP_HANDLER_INVOKE_FAILED,
        tool_name=tool,
        error_type=type(exc).__name__,
        error=safe_error_description(exc),
    )


async def _meta_get_config(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: Any = None,  # noqa: ARG001
) -> str:
    return not_supported("synthorg_meta_get_config", _WHY_CONFIG)


async def _meta_list_rules(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: Any = None,  # noqa: ARG001
) -> str:
    return not_supported("synthorg_meta_list_rules", _WHY_RULES)


async def _meta_list_mcp_tools(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: Any = None,  # noqa: ARG001
) -> str:
    tool = "synthorg_meta_list_mcp_tools"
    # Deferred import breaks the handlers->server->handlers import cycle.
    from synthorg.meta.mcp.server import get_registry  # noqa: PLC0415

    try:
        registry = get_registry()
        tools = list(registry.get_tool_definitions())
    except Exception as exc:
        _log_failed(tool, exc)
        return err(exc)
    logger.info(MCP_HANDLER_INVOKE_SUCCESS, tool_name=tool)
    return ok(data=tools)


async def _meta_get_mcp_server_config(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: Any = None,  # noqa: ARG001
) -> str:
    tool = "synthorg_meta_get_mcp_server_config"
    from synthorg.meta.mcp.server import get_server_config  # noqa: PLC0415

    try:
        config = get_server_config()
    except Exception as exc:
        _log_failed(tool, exc)
        return err(exc)
    logger.info(MCP_HANDLER_INVOKE_SUCCESS, tool_name=tool)
    return ok(data=config)


async def _meta_trigger_cycle(
    *,
    app_state: Any,  # noqa: ARG001
    arguments: dict[str, Any],  # noqa: ARG001
    actor: Any = None,  # noqa: ARG001
) -> str:
    return not_supported("synthorg_meta_trigger_cycle", _WHY_TRIGGER)


META_HANDLERS: Mapping[str, ToolHandler] = MappingProxyType(
    {
        "synthorg_meta_get_config": _meta_get_config,
        "synthorg_meta_list_rules": _meta_list_rules,
        "synthorg_meta_list_mcp_tools": _meta_list_mcp_tools,
        "synthorg_meta_get_mcp_server_config": _meta_get_mcp_server_config,
        "synthorg_meta_trigger_cycle": _meta_trigger_cycle,
    },
)
