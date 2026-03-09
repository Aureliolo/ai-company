"""Memory consolidation — strategies, retention, archival, and service.

Re-exports the public API so consumers can import from
``ai_company.memory.consolidation`` directly.
"""

from ai_company.memory.consolidation.archival import ArchivalStore
from ai_company.memory.consolidation.config import (
    ArchivalConfig,
    ConsolidationConfig,
    RetentionConfig,
)
from ai_company.memory.consolidation.models import (
    ArchivalEntry,
    ConsolidationResult,
    RetentionRule,
)
from ai_company.memory.consolidation.retention import RetentionEnforcer
from ai_company.memory.consolidation.service import MemoryConsolidationService
from ai_company.memory.consolidation.simple_strategy import (
    SimpleConsolidationStrategy,
)
from ai_company.memory.consolidation.strategy import ConsolidationStrategy

__all__ = [
    "ArchivalConfig",
    "ArchivalEntry",
    "ArchivalStore",
    "ConsolidationConfig",
    "ConsolidationResult",
    "ConsolidationStrategy",
    "MemoryConsolidationService",
    "RetentionConfig",
    "RetentionEnforcer",
    "RetentionRule",
    "SimpleConsolidationStrategy",
]
