"""Event constants for terminal/shell tool operations."""

from typing import Final

TERMINAL_COMMAND_START: Final[str] = "terminal.command.start"
TERMINAL_COMMAND_SUCCESS: Final[str] = "terminal.command.success"
TERMINAL_COMMAND_FAILED: Final[str] = "terminal.command.failed"
TERMINAL_COMMAND_TIMEOUT: Final[str] = "terminal.command.timeout"
TERMINAL_COMMAND_BLOCKED: Final[str] = "terminal.command.blocked"
