"""Shell command tool -- execute commands in a sandboxed environment.

Delegates to a ``SandboxBackend`` for isolated execution.  Commands
are validated against allow/blocklist before execution.  Output is
truncated at ``max_output_bytes``.
"""

import copy
from typing import Any, Final

from synthorg.observability import get_logger
from synthorg.observability.events.terminal import (
    TERMINAL_COMMAND_FAILED,
    TERMINAL_COMMAND_START,
    TERMINAL_COMMAND_SUCCESS,
    TERMINAL_COMMAND_TIMEOUT,
)
from synthorg.tools.base import ToolExecutionResult
from synthorg.tools.sandbox.errors import SandboxError
from synthorg.tools.terminal.base_terminal_tool import BaseTerminalTool

logger = get_logger(__name__)

_PARAMETERS_SCHEMA: Final[dict[str, Any]] = {
    "type": "object",
    "properties": {
        "command": {
            "type": "string",
            "description": "Shell command to execute",
        },
        "working_directory": {
            "type": "string",
            "description": "Working directory (relative to workspace)",
        },
        "timeout": {
            "type": "number",
            "description": "Command timeout in seconds",
            "minimum": 1,
            "maximum": 600,
        },
    },
    "required": ["command"],
    "additionalProperties": False,
}


class ShellCommandTool(BaseTerminalTool):
    """Execute shell commands in a sandboxed environment.

    Commands are validated against the allow/blocklist before
    execution.  Output (stdout + stderr) is captured and truncated
    at ``max_output_bytes``.

    When no sandbox backend is provided, returns an error (terminal
    tools require sandboxed execution).

    Examples:
        Execute a command::

            tool = ShellCommandTool(sandbox=my_sandbox)
            result = await tool.execute(arguments={"command": "ls -la"})
    """

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the shell command tool.

        Args:
            **kwargs: Passed to ``BaseTerminalTool.__init__``.
        """
        super().__init__(
            name="shell_command",
            description=(
                "Execute a shell command in a sandboxed environment. "
                "Output is captured and returned."
            ),
            parameters_schema=copy.deepcopy(_PARAMETERS_SCHEMA),
            **kwargs,
        )

    async def execute(
        self,
        *,
        arguments: dict[str, Any],
    ) -> ToolExecutionResult:
        """Execute a shell command.

        Args:
            arguments: Must contain ``command``; optionally
                ``working_directory`` and ``timeout``.

        Returns:
            A ``ToolExecutionResult`` with command output.
        """
        command: str = arguments["command"]
        working_dir: str | None = arguments.get("working_directory")
        raw_timeout = arguments.get("timeout")
        timeout: float = (
            raw_timeout if raw_timeout is not None else self._config.default_timeout
        )

        if not command.strip():
            return ToolExecutionResult(
                content="Empty command",
                is_error=True,
            )

        # Blocklist check first (higher priority than allowlist)
        if self._is_command_blocked(command):
            return ToolExecutionResult(
                content=f"Command blocked by security policy: {command!r}",
                is_error=True,
            )

        # Allowlist check
        if not self._is_command_allowed(command):
            return ToolExecutionResult(
                content=(
                    f"Command not in allowlist: {command!r}. "
                    f"Allowed prefixes: {self._config.command_allowlist}"
                ),
                is_error=True,
            )

        if self._sandbox is None:
            return ToolExecutionResult(
                content=(
                    "Terminal tools require a sandbox backend. "
                    "No sandbox is configured."
                ),
                is_error=True,
            )

        logger.info(
            TERMINAL_COMMAND_START,
            command=command,
            timeout=timeout,
        )

        return await self._execute_sandboxed(command, timeout, working_dir)

    async def _execute_sandboxed(
        self,
        command: str,
        timeout: float,  # noqa: ASYNC109  -- passed to sandbox, not asyncio
        working_dir: str | None = None,
    ) -> ToolExecutionResult:
        """Execute the command through the sandbox backend.

        Args:
            command: Shell command to execute.
            timeout: Execution timeout in seconds.
            working_dir: Optional working directory path.

        Returns:
            A ``ToolExecutionResult`` with the output.
        """
        if self._sandbox is None:  # pragma: no cover -- guarded by caller
            msg = "_execute_sandboxed called without sandbox"
            raise RuntimeError(msg)

        from pathlib import Path  # noqa: PLC0415

        if working_dir:
            cwd = Path(working_dir)
            if cwd.is_absolute():
                return ToolExecutionResult(
                    content=(
                        f"Absolute working_directory not allowed: {working_dir!r}. "
                        "Use a path relative to the workspace."
                    ),
                    is_error=True,
                )
        else:
            cwd = None

        try:
            result = await self._sandbox.execute(
                command="bash",
                args=("-c", command),
                cwd=cwd,
                timeout=timeout,
            )
        except SandboxError as exc:
            logger.warning(
                TERMINAL_COMMAND_FAILED,
                command=command,
                error=str(exc),
            )
            return ToolExecutionResult(
                content=f"Sandbox error: {exc}",
                is_error=True,
            )

        if result.timed_out:
            logger.warning(
                TERMINAL_COMMAND_TIMEOUT,
                command=command,
                timeout=timeout,
            )
            return ToolExecutionResult(
                content=f"Command timed out after {timeout}s",
                is_error=True,
                metadata={"timed_out": True},
            )

        # Combine stdout and stderr
        output = result.stdout or ""
        if result.stderr:
            if output:
                output += "\n"
            output += result.stderr

        # Truncate if needed (account for marker in the byte budget)
        truncated = False
        if len(output) > self._config.max_output_bytes:
            truncated = True
            marker = (
                f"\n\n[Truncated: output exceeded"
                f" {self._config.max_output_bytes:,} bytes]"
            )
            output = output[: max(0, self._config.max_output_bytes - len(marker))]
            output += marker

        if result.success:
            logger.info(
                TERMINAL_COMMAND_SUCCESS,
                command=command,
                returncode=result.returncode,
                output_length=len(output),
            )
        else:
            logger.warning(
                TERMINAL_COMMAND_FAILED,
                command=command,
                returncode=result.returncode,
            )

        return ToolExecutionResult(
            content=output or "(no output)",
            is_error=not result.success,
            metadata={
                "returncode": result.returncode,
                "timed_out": result.timed_out,
                "truncated": truncated,
            },
        )
