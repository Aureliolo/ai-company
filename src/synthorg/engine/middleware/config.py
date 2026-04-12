"""Middleware configuration re-exports.

The canonical definitions live in ``synthorg.core.middleware_config``
to avoid circular imports (``core.company`` -> ``engine.*`` chain).
This module re-exports them for convenience so engine-layer code
can import from ``synthorg.engine.middleware.config``.
"""

from synthorg.core.middleware_config import (
    DEFAULT_AGENT_CHAIN,
    DEFAULT_COORDINATION_CHAIN,
    AgentMiddlewareConfig,
    AuthorityDeferenceConfig,
    ClarificationGateConfig,
    CoordinationMiddlewareConfig,
    MiddlewareConfig,
)

__all__ = [
    "DEFAULT_AGENT_CHAIN",
    "DEFAULT_COORDINATION_CHAIN",
    "AgentMiddlewareConfig",
    "AuthorityDeferenceConfig",
    "ClarificationGateConfig",
    "CoordinationMiddlewareConfig",
    "MiddlewareConfig",
]
