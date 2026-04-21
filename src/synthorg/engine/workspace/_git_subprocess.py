"""System-internal git subprocess orchestration.

This module is NOT agent-facing. Agent-facing git operations live in
``synthorg.tools.git_tools`` and carry distinct security validation
(workspace-path confinement, env hardening). This module is a pure
process-management helper for :class:`SynthOrgGitWorktree` setup,
merge, and teardown flows, extracted from ``git_worktree.py`` per
PST-1 so the subprocess lifecycle lives in one focused place.
"""

import asyncio
from typing import TYPE_CHECKING

from synthorg.observability import get_logger

if TYPE_CHECKING:
    from pathlib import Path

logger = get_logger(__name__)


async def run_git_subprocess(
    repo_root: Path,
    *args: str,
    cmd_timeout: float,
    log_event: str,
) -> tuple[int, str, str]:
    """Run ``git *args`` in *repo_root* and decode stdout/stderr.

    Args:
        repo_root: Working directory for the git command.
        *args: Git command arguments (e.g. ``"worktree"``, ``"add"``).
        cmd_timeout: Maximum seconds to wait for completion.
        log_event: Structured-log event constant used on timeout.

    Returns:
        Tuple ``(return_code, stdout_text, stderr_text)``. On timeout,
        returns ``(-1, "", <message>)`` after killing the process.

    Raises:
        asyncio.CancelledError: Propagated (process is killed first).
    """
    # ``create_subprocess_exec`` can raise ``OSError`` before the process
    # ever starts (missing ``git`` binary, bad ``cwd``, resource limits,
    # ...). Returning the normal contract as ``(-1, "", <message>)``
    # keeps every caller simple -- they already handle the non-zero rc
    # branch and do not have to special-case a thrown exception.
    try:
        proc = await asyncio.create_subprocess_exec(
            "git",
            *args,
            cwd=str(repo_root),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except OSError as exc:
        msg = f"failed to spawn git subprocess: {exc.__class__.__name__}"
        logger.warning(
            log_event,
            error_type=exc.__class__.__name__,
            error=msg,
            args=args,
        )
        return (-1, "", msg)
    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(),
            timeout=cmd_timeout,
        )
    except TimeoutError:
        proc.kill()
        await proc.wait()
        msg = f"git {args[0] if args else ''} timed out after {cmd_timeout}s"
        logger.warning(
            log_event,
            error_type="TimeoutError",
            error=msg,
            args=args,
        )
        return (-1, "", msg)
    except asyncio.CancelledError:
        proc.kill()
        await proc.wait()
        raise

    rc = proc.returncode if proc.returncode is not None else -1
    return (
        rc,
        stdout_bytes.decode("utf-8", errors="replace").strip(),
        stderr_bytes.decode("utf-8", errors="replace").strip(),
    )
