"""Protocol definition for MCP tool handlers.

Split out from :mod:`synthorg.meta.mcp.invoker` so handler modules can
import :class:`ToolHandler` at runtime (needed by PEP 649 lazy
annotation evaluation on module-level ``MEMORY_HANDLERS: Mapping[str,
ToolHandler]`` style declarations) without pulling in the tool registry
+ provider + persistence chain that ``invoker`` drags through
``synthorg.tools.base``.  Keeping this module dependency-free breaks
the circular-import risk that otherwise surfaces when every handler
module tries to import ``ToolHandler`` from the invoker.
"""

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from synthorg.core.agent import AgentIdentity


class ToolHandler(Protocol):
    """Protocol for MCP tool handler functions.

    Handlers receive the application state, parsed arguments, and the
    calling actor identity (when available), returning a
    JSON-serialized string result.  The ``actor`` argument is threaded
    from the invoker so destructive-op guardrails can enforce
    attribution; handlers that don't care about identity accept it and
    ignore it.
    """

    async def __call__(
        self,
        *,
        app_state: Any,
        arguments: dict[str, Any],
        actor: AgentIdentity | None = None,
    ) -> str:
        """Execute the tool logic.

        Args:
            app_state: Application state providing service access.
            arguments: Parsed tool arguments from the MCP call.
            actor: Calling agent identity (typically
                ``AgentIdentity``), or ``None`` when the invoker was
                not supplied one.  Destructive-op handlers require
                non-``None``.

        Returns:
            JSON-serialized result string.
        """
        ...
