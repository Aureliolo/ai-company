"""Context budget management event constants for structured logging."""

from typing import Final

# Fill level tracking
CONTEXT_BUDGET_FILL_UPDATED: Final[str] = "context_budget.fill.updated"
CONTEXT_BUDGET_THRESHOLD_REACHED: Final[str] = "context_budget.threshold.reached"

# Compaction lifecycle
CONTEXT_BUDGET_COMPACTION_STARTED: Final[str] = "context_budget.compaction.started"
CONTEXT_BUDGET_COMPACTION_COMPLETED: Final[str] = "context_budget.compaction.completed"
CONTEXT_BUDGET_COMPACTION_FAILED: Final[str] = "context_budget.compaction.failed"
CONTEXT_BUDGET_COMPACTION_SKIPPED: Final[str] = "context_budget.compaction.skipped"

# Indicator injection
CONTEXT_BUDGET_INDICATOR_INJECTED: Final[str] = "context_budget.indicator.injected"
