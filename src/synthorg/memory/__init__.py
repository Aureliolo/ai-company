"""Agent memory system -- protocols, models, config, and factory.

Re-exports protocols (``MemoryBackend``, ``MemoryCapabilities``,
``SharedKnowledgeStore``, ``MemoryInjectionStrategy``,
``OrgMemoryBackend``, ``ConsolidationStrategy``, ``ArchivalStore``),
concrete backends (``Mem0MemoryBackend``), domain models, config
models, factory, retrieval pipeline, consolidation, org memory, and
error hierarchy so consumers can import from ``synthorg.memory``
directly.

Hybrid search: ``BM25Tokenizer``, ``SparseVector``,
``FusionStrategy``, ``fuse_ranked_lists``.

Tool-based strategy: ``ToolBasedInjectionStrategy``.

Query reformulation: ``QueryReformulator``, ``SufficiencyChecker``,
``LLMQueryReformulator``, ``LLMSufficiencyChecker``.
"""

from synthorg.memory.backends.mem0 import (
    Mem0EmbedderConfig,
    Mem0MemoryBackend,
)
from synthorg.memory.capabilities import MemoryCapabilities
from synthorg.memory.config import (
    CompanyMemoryConfig,
    EmbedderOverrideConfig,
    MemoryOptionsConfig,
    MemoryStorageConfig,
)
from synthorg.memory.consolidation import (
    ArchivalMode,
    ArchivalStore,
    ConsolidationConfig,
    ConsolidationResult,
    ConsolidationStrategy,
    ContentDensity,
    DualModeConsolidationStrategy,
    MemoryConsolidationService,
    RetentionEnforcer,
    SimpleConsolidationStrategy,
)
from synthorg.memory.errors import (
    MemoryCapabilityError,
    MemoryConfigError,
    MemoryConnectionError,
    MemoryError,  # noqa: A004
    MemoryNotFoundError,
    MemoryRetrievalError,
    MemoryStoreError,
)
from synthorg.memory.factory import create_memory_backend
from synthorg.memory.injection import (
    DefaultTokenEstimator,
    InjectionPoint,
    InjectionStrategy,
    MemoryInjectionStrategy,
    TokenEstimator,
)
from synthorg.memory.models import (
    MemoryEntry,
    MemoryMetadata,
    MemoryQuery,
    MemoryStoreRequest,
)
from synthorg.memory.org import (
    OrgFact,
    OrgFactAuthor,
    OrgFactStore,
    OrgFactWriteRequest,
    OrgMemoryBackend,
    OrgMemoryConfig,
    OrgMemoryError,
    OrgMemoryQuery,
    SQLiteOrgFactStore,
    create_org_memory_backend,
)
from synthorg.memory.protocol import MemoryBackend
from synthorg.memory.ranking import FusionStrategy, ScoredMemory, fuse_ranked_lists
from synthorg.memory.reformulation import (
    LLMQueryReformulator,
    LLMSufficiencyChecker,
    QueryReformulator,
    SufficiencyChecker,
)
from synthorg.memory.retrieval_config import MemoryRetrievalConfig
from synthorg.memory.retriever import ContextInjectionStrategy
from synthorg.memory.shared import SharedKnowledgeStore
from synthorg.memory.sparse import BM25Tokenizer, SparseVector
from synthorg.memory.tool_retriever import ToolBasedInjectionStrategy

__all__ = [
    "ArchivalMode",
    "ArchivalStore",
    # Hybrid search
    "BM25Tokenizer",
    "CompanyMemoryConfig",
    "ConsolidationConfig",
    "ConsolidationResult",
    "ConsolidationStrategy",
    "ContentDensity",
    "ContextInjectionStrategy",
    "DefaultTokenEstimator",
    "DualModeConsolidationStrategy",
    "EmbedderOverrideConfig",
    "FusionStrategy",
    "InjectionPoint",
    "InjectionStrategy",
    # Query reformulation
    "LLMQueryReformulator",
    "LLMSufficiencyChecker",
    "Mem0EmbedderConfig",
    "Mem0MemoryBackend",
    "MemoryBackend",
    "MemoryCapabilities",
    "MemoryCapabilityError",
    "MemoryConfigError",
    "MemoryConnectionError",
    "MemoryConsolidationService",
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
    "OrgFact",
    "OrgFactAuthor",
    "OrgFactStore",
    "OrgFactWriteRequest",
    "OrgMemoryBackend",
    "OrgMemoryConfig",
    "OrgMemoryError",
    "OrgMemoryQuery",
    "QueryReformulator",
    "RetentionEnforcer",
    "SQLiteOrgFactStore",
    "ScoredMemory",
    "SharedKnowledgeStore",
    "SimpleConsolidationStrategy",
    "SparseVector",
    "SufficiencyChecker",
    "TokenEstimator",
    # Tool-based strategy
    "ToolBasedInjectionStrategy",
    "create_memory_backend",
    "create_org_memory_backend",
    "fuse_ranked_lists",
]
