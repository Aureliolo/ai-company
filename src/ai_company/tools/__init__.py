"""Tool system — base abstraction, registry, invoker, permissions, and errors."""

from .base import BaseTool, ToolExecutionResult
from .errors import (
    ToolError,
    ToolExecutionError,
    ToolNotFoundError,
    ToolParameterError,
    ToolPermissionDeniedError,
)
from .examples.echo import EchoTool
from .invoker import ToolInvoker
from .permissions import ToolPermissionChecker
from .registry import ToolRegistry

__all__ = [
    "BaseTool",
    "EchoTool",
    "ToolError",
    "ToolExecutionError",
    "ToolExecutionResult",
    "ToolInvoker",
    "ToolNotFoundError",
    "ToolParameterError",
    "ToolPermissionChecker",
    "ToolPermissionDeniedError",
    "ToolRegistry",
]
