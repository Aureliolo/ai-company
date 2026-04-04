"""Memory consolidation -- strategies, retention, archival, and service.

Re-exports the public API so consumers can import from
``synthorg.memory.consolidation`` directly.
"""

from synthorg.memory.consolidation.abstractive import AbstractiveSummarizer
from synthorg.memory.consolidation.archival import ArchivalStore
from synthorg.memory.consolidation.config import (
    ArchivalConfig,
    ConsolidationConfig,
    DualModeConfig,
    RetentionConfig,
)
from synthorg.memory.consolidation.density import ContentDensity, DensityClassifier
from synthorg.memory.consolidation.distillation import (
    DistillationRequest,
    capture_distillation,
)
from synthorg.memory.consolidation.dual_mode_strategy import (
    DualModeConsolidationStrategy,
)
from synthorg.memory.consolidation.extractive import ExtractivePreserver
from synthorg.memory.consolidation.llm_strategy import LLMConsolidationStrategy
from synthorg.memory.consolidation.models import (
    ArchivalEntry,
    ArchivalIndexEntry,
    ArchivalMode,
    ArchivalModeAssignment,
    ConsolidationResult,
    RetentionRule,
)
from synthorg.memory.consolidation.retention import RetentionEnforcer
from synthorg.memory.consolidation.service import MemoryConsolidationService
from synthorg.memory.consolidation.simple_strategy import (
    SimpleConsolidationStrategy,
)
from synthorg.memory.consolidation.strategy import ConsolidationStrategy

__all__ = [
    "AbstractiveSummarizer",
    "ArchivalConfig",
    "ArchivalEntry",
    "ArchivalIndexEntry",
    "ArchivalMode",
    "ArchivalModeAssignment",
    "ArchivalStore",
    "ConsolidationConfig",
    "ConsolidationResult",
    "ConsolidationStrategy",
    "ContentDensity",
    "DensityClassifier",
    "DistillationRequest",
    "DualModeConfig",
    "DualModeConsolidationStrategy",
    "ExtractivePreserver",
    "LLMConsolidationStrategy",
    "MemoryConsolidationService",
    "RetentionConfig",
    "RetentionEnforcer",
    "RetentionRule",
    "SimpleConsolidationStrategy",
    "capture_distillation",
]
