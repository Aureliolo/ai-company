"""Conflict resolution subsystem (DESIGN_SPEC §5.6).

Strategy implementations (``AuthorityResolver``, ``DebateResolver``,
``HumanEscalationResolver``, ``HybridResolver``) are NOT re-exported
here to avoid circular imports.  Import them directly from their
respective modules (e.g. ``conflict_resolution.authority_strategy``).
"""

from ai_company.communication.conflict_resolution.config import (
    ConflictResolutionConfig,
    DebateConfig,
    HybridConfig,
)
from ai_company.communication.conflict_resolution.models import (
    Conflict,
    ConflictPosition,
    ConflictResolution,
    ConflictResolutionOutcome,
    DissentRecord,
)
from ai_company.communication.conflict_resolution.protocol import (
    ConflictResolver,
    JudgeEvaluator,
)
from ai_company.communication.conflict_resolution.service import (
    ConflictResolutionService,
)

__all__ = [
    "Conflict",
    "ConflictPosition",
    "ConflictResolution",
    "ConflictResolutionConfig",
    "ConflictResolutionOutcome",
    "ConflictResolutionService",
    "ConflictResolver",
    "DebateConfig",
    "DissentRecord",
    "HybridConfig",
    "JudgeEvaluator",
]
