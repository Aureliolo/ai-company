"""Sandbox backend factory -- build and resolve backends from config.

Provides ``build_sandbox_backends`` to instantiate only the backends
referenced by a ``SandboxingConfig``, ``resolve_sandbox_for_category``
to look up the correct backend for a tool category, and
``cleanup_sandbox_backends`` to release resources.
"""

import asyncio
from types import MappingProxyType
from typing import TYPE_CHECKING

from synthorg.observability import get_logger
from synthorg.observability.events.sandbox import (
    SANDBOX_FACTORY_BUILT,
    SANDBOX_FACTORY_CLEANUP,
    SANDBOX_FACTORY_RESOLVE,
)
from synthorg.tools.sandbox.docker_sandbox import DockerSandbox
from synthorg.tools.sandbox.subprocess_sandbox import SubprocessSandbox

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from synthorg.core.enums import ToolCategory
    from synthorg.tools.sandbox.protocol import SandboxBackend
    from synthorg.tools.sandbox.sandboxing_config import SandboxingConfig

logger = get_logger(__name__)


def build_sandbox_backends(
    *,
    config: SandboxingConfig,
    workspace: Path,
) -> MappingProxyType[str, SandboxBackend]:
    """Build only the backend instances actually referenced by *config*.

    Collects which backend names are needed (the default plus all
    override values), then instantiates ``SubprocessSandbox`` and/or
    ``DockerSandbox`` with their respective sub-configs.

    Args:
        config: Top-level sandboxing configuration.
        workspace: Absolute path to the agent workspace root.

    Returns:
        A read-only mapping of backend name to backend instance.
        Only contains keys for backends that are actually referenced.
    """
    needed: set[str] = {config.default_backend}
    needed.update(config.overrides.values())

    backends: dict[str, SandboxBackend] = {}

    if "subprocess" in needed:
        backends["subprocess"] = SubprocessSandbox(
            config=config.subprocess,
            workspace=workspace,
        )

    if "docker" in needed:
        backends["docker"] = DockerSandbox(
            config=config.docker,
            workspace=workspace,
        )

    logger.info(
        SANDBOX_FACTORY_BUILT,
        backends=sorted(backends.keys()),
        default=config.default_backend,
        override_count=len(config.overrides),
    )
    return MappingProxyType(backends)


def resolve_sandbox_for_category(
    *,
    config: SandboxingConfig,
    backends: Mapping[str, SandboxBackend],
    category: ToolCategory,
) -> SandboxBackend:
    """Look up the correct backend for a tool category.

    Uses ``config.backend_for_category()`` to determine the backend
    name, then returns the corresponding instance from *backends*.

    Args:
        config: Top-level sandboxing configuration.
        backends: Mapping of backend name to backend instance.
        category: The tool category to resolve.

    Returns:
        The ``SandboxBackend`` instance for the given category.

    Raises:
        KeyError: If the resolved backend name is not present in
            *backends*.
    """
    backend_name = config.backend_for_category(category.value)
    try:
        backend = backends[backend_name]
    except KeyError:
        msg = (
            f"Backend {backend_name!r} resolved for category "
            f"{category.value!r} not found in backends mapping "
            f"(available: {sorted(backends.keys())})"
        )
        logger.warning(
            SANDBOX_FACTORY_RESOLVE,
            category=category.value,
            backend=backend_name,
            error=msg,
        )
        raise KeyError(msg) from None

    logger.debug(
        SANDBOX_FACTORY_RESOLVE,
        category=category.value,
        backend=backend_name,
    )
    return backend


async def cleanup_sandbox_backends(
    backends: Mapping[str, SandboxBackend],
) -> None:
    """Clean up all backends by calling ``cleanup()`` on each.

    Errors from individual backends are logged but do not prevent
    cleanup of remaining backends.  Uses ``asyncio.TaskGroup`` for
    parallel cleanup.

    Args:
        backends: Mapping of backend name to backend instance.
    """

    async def _cleanup_one(name: str, backend: SandboxBackend) -> None:
        logger.debug(SANDBOX_FACTORY_CLEANUP, backend=name)
        try:
            await backend.cleanup()
        except Exception:
            logger.warning(
                SANDBOX_FACTORY_CLEANUP,
                backend=name,
                error=f"cleanup failed for backend {name!r}",
                exc_info=True,
            )

    async with asyncio.TaskGroup() as tg:
        for name, backend in backends.items():
            tg.create_task(_cleanup_one(name, backend))
