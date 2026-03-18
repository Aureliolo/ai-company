"""Component backup handlers."""

from synthorg.backup.handlers.config_handler import ConfigComponentHandler
from synthorg.backup.handlers.memory import MemoryComponentHandler
from synthorg.backup.handlers.persistence import PersistenceComponentHandler
from synthorg.backup.handlers.protocol import ComponentHandler

__all__ = [
    "ComponentHandler",
    "ConfigComponentHandler",
    "MemoryComponentHandler",
    "PersistenceComponentHandler",
]
