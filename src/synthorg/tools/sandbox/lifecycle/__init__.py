"""Pluggable sandbox container lifecycle strategies."""

from synthorg.tools.sandbox.lifecycle.config import SandboxLifecycleConfig
from synthorg.tools.sandbox.lifecycle.factory import create_lifecycle_strategy
from synthorg.tools.sandbox.lifecycle.protocol import (
    ContainerHandle,
    SandboxLifecycleStrategy,
)

__all__ = [
    "ContainerHandle",
    "SandboxLifecycleConfig",
    "SandboxLifecycleStrategy",
    "create_lifecycle_strategy",
]
