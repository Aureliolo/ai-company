"""Sandbox error hierarchy.

All sandbox errors inherit from ``ToolError`` so that sandbox failures
surface through the standard tool error path.
"""

from ai_company.tools.errors import ToolError


class SandboxError(ToolError):
    """Base exception for sandbox-layer errors."""


class SandboxTimeoutError(SandboxError):
    """Execution was killed because it exceeded the timeout.

    Note: ``SubprocessSandbox`` signals timeouts via
    ``SandboxResult.timed_out`` rather than raising this exception,
    so callers can access partial output.  This class exists for
    future sandbox backends (e.g. Docker) that may raise on timeout
    instead of returning a result.
    """


class SandboxStartError(SandboxError):
    """Failed to start the sandboxed subprocess."""
