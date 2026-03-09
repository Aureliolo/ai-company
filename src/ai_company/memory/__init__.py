"""Agent memory system — protocols, models, config, and factory.

Re-exports the protocols (``MemoryBackend``, ``MemoryCapabilities``,
``SharedKnowledgeStore``, ``MemoryInjectionStrategy``), domain models,
config models, factory, retrieval pipeline, and error hierarchy so
consumers can import from ``ai_company.memory`` directly.
"""

from ai_company.memory.capabilities import MemoryCapabilities
from ai_company.memory.config import (
    CompanyMemoryConfig,
    MemoryOptionsConfig,
    MemoryStorageConfig,
)
from ai_company.memory.errors import (
    MemoryCapabilityError,
    MemoryConfigError,
    MemoryConnectionError,
    MemoryError,  # noqa: A004
    MemoryNotFoundError,
    MemoryRetrievalError,
    MemoryStoreError,
)
from ai_company.memory.factory import create_memory_backend
from ai_company.memory.injection import (
    DefaultTokenEstimator,
    InjectionPoint,
    InjectionStrategy,
    MemoryInjectionStrategy,
    TokenEstimator,
)
from ai_company.memory.models import (
    MemoryEntry,
    MemoryMetadata,
    MemoryQuery,
    MemoryStoreRequest,
)
from ai_company.memory.protocol import MemoryBackend
from ai_company.memory.ranking import ScoredMemory
from ai_company.memory.retrieval_config import MemoryRetrievalConfig
from ai_company.memory.retriever import ContextInjectionStrategy
from ai_company.memory.shared import SharedKnowledgeStore

__all__ = [
    "CompanyMemoryConfig",
    "ContextInjectionStrategy",
    "DefaultTokenEstimator",
    "InjectionPoint",
    "InjectionStrategy",
    "MemoryBackend",
    "MemoryCapabilities",
    "MemoryCapabilityError",
    "MemoryConfigError",
    "MemoryConnectionError",
    "MemoryEntry",
    "MemoryError",
    "MemoryInjectionStrategy",
    "MemoryMetadata",
    "MemoryNotFoundError",
    "MemoryOptionsConfig",
    "MemoryQuery",
    "MemoryRetrievalConfig",
    "MemoryRetrievalError",
    "MemoryStorageConfig",
    "MemoryStoreError",
    "MemoryStoreRequest",
    "ScoredMemory",
    "SharedKnowledgeStore",
    "TokenEstimator",
    "create_memory_backend",
]
