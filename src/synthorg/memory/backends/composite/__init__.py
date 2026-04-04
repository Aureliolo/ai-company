"""Composite memory backend -- namespace-based routing."""

from synthorg.memory.backends.composite.adapter import CompositeBackend
from synthorg.memory.backends.composite.config import CompositeBackendConfig

__all__ = ["CompositeBackend", "CompositeBackendConfig"]
