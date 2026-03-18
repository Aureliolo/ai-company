"""Execution loop auto-selection based on task complexity and budget state.

Provides a pure ``select_loop_type`` function that maps task complexity
and optional budget utilization to a loop type string, and a
``build_execution_loop`` factory that instantiates the concrete loop.

The default rules follow the design spec (section 6.5):
simple -> ReAct, medium -> Plan-and-Execute, complex/epic -> Hybrid.
"""

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from synthorg.core.enums import Complexity
from synthorg.engine.plan_execute_loop import PlanExecuteLoop
from synthorg.engine.react_loop import ReactLoop
from synthorg.observability import get_logger
from synthorg.observability.events.execution import (
    EXECUTION_LOOP_BUDGET_DOWNGRADE,
    EXECUTION_LOOP_HYBRID_FALLBACK,
)

if TYPE_CHECKING:
    from synthorg.engine.approval_gate import ApprovalGate
    from synthorg.engine.compaction import CompactionCallback
    from synthorg.engine.loop_protocol import ExecutionLoop
    from synthorg.engine.plan_models import PlanExecuteConfig
    from synthorg.engine.stagnation import StagnationDetector

logger = get_logger(__name__)


class AutoLoopRule(BaseModel):
    """Maps a task complexity level to an execution loop type.

    Attributes:
        complexity: The task complexity this rule matches.
        loop_type: The loop type to use (e.g. ``"react"``,
            ``"plan_execute"``, ``"hybrid"``).
    """

    model_config = ConfigDict(frozen=True)

    complexity: Complexity = Field(description="Task complexity level")
    loop_type: str = Field(description="Loop type identifier")


DEFAULT_AUTO_LOOP_RULES: tuple[AutoLoopRule, ...] = (
    AutoLoopRule(complexity=Complexity.SIMPLE, loop_type="react"),
    AutoLoopRule(complexity=Complexity.MEDIUM, loop_type="plan_execute"),
    AutoLoopRule(complexity=Complexity.COMPLEX, loop_type="hybrid"),
    AutoLoopRule(complexity=Complexity.EPIC, loop_type="hybrid"),
)


class AutoLoopConfig(BaseModel):
    """Configuration for automatic execution loop selection.

    Attributes:
        rules: Ordered rules mapping complexity to loop type.
        budget_tight_threshold: Monthly budget utilization percentage
            at or above which the budget is considered tight.  When
            tight, hybrid selections are downgraded to plan_execute.
        hybrid_fallback: Loop type to use when hybrid is selected but
            not yet implemented.  Set to ``None`` to keep hybrid
            (useful once the HybridLoop class exists).
    """

    model_config = ConfigDict(frozen=True)

    rules: tuple[AutoLoopRule, ...] = Field(
        default=DEFAULT_AUTO_LOOP_RULES,
        description="Complexity-to-loop mapping rules",
    )
    budget_tight_threshold: int = Field(
        default=80,
        ge=0,
        le=100,
        description="Budget utilization % that triggers tight-budget mode",
    )
    hybrid_fallback: str | None = Field(
        default="plan_execute",
        description="Fallback loop when hybrid is selected but unavailable",
    )


def select_loop_type(
    *,
    complexity: Complexity,
    rules: tuple[AutoLoopRule, ...],
    budget_utilization_pct: float | None = None,
    budget_tight_threshold: int = 80,
    hybrid_fallback: str | None = "plan_execute",
) -> str:
    """Select the execution loop type for a task.

    Applies three layers of logic in order:

    1. **Rule matching** -- find the first rule whose complexity matches.
       Falls back to ``"react"`` when no rule matches.
    2. **Budget-aware downgrade** -- if the matched type is ``"hybrid"``
       and the monthly budget utilization is at or above
       ``budget_tight_threshold``, downgrade to ``"plan_execute"``.
    3. **Hybrid fallback** -- if the type is still ``"hybrid"`` and
       ``hybrid_fallback`` is not ``None``, replace with the fallback
       (the Hybrid loop class is not yet implemented).

    Args:
        complexity: Task's estimated complexity.
        rules: Mapping rules from complexity to loop type.
        budget_utilization_pct: Current monthly budget utilization
            as a percentage (0--100+).  ``None`` means unknown.
        budget_tight_threshold: Percentage at or above which budget
            is considered tight.
        hybrid_fallback: Replacement loop type when hybrid is selected
            but unavailable.  ``None`` preserves the hybrid selection.

    Returns:
        Loop type string: ``"react"``, ``"plan_execute"``, or
        ``"hybrid"``.
    """
    # 1. Rule matching
    loop_type = "react"
    for rule in rules:
        if rule.complexity == complexity:
            loop_type = rule.loop_type
            break

    # 2. Budget-aware downgrade (hybrid only)
    if (
        loop_type == "hybrid"
        and budget_utilization_pct is not None
        and budget_utilization_pct >= budget_tight_threshold
    ):
        logger.info(
            EXECUTION_LOOP_BUDGET_DOWNGRADE,
            original=loop_type,
            downgraded_to="plan_execute",
            budget_utilization_pct=budget_utilization_pct,
            budget_tight_threshold=budget_tight_threshold,
        )
        loop_type = "plan_execute"

    # 3. Hybrid fallback (not yet implemented)
    if loop_type == "hybrid" and hybrid_fallback is not None:
        logger.info(
            EXECUTION_LOOP_HYBRID_FALLBACK,
            fallback_to=hybrid_fallback,
        )
        loop_type = hybrid_fallback

    return loop_type


def build_execution_loop(
    loop_type: str,
    *,
    approval_gate: ApprovalGate | None = None,
    stagnation_detector: StagnationDetector | None = None,
    compaction_callback: CompactionCallback | None = None,
    plan_execute_config: PlanExecuteConfig | None = None,
) -> ExecutionLoop:
    """Build an ``ExecutionLoop`` instance from a loop type string.

    Args:
        loop_type: One of ``"react"`` or ``"plan_execute"``.
        approval_gate: Optional approval gate to wire into the loop.
        stagnation_detector: Optional stagnation detector.
        compaction_callback: Optional compaction callback.
        plan_execute_config: Configuration for the plan-execute loop
            (ignored when ``loop_type`` is not ``"plan_execute"``).

    Returns:
        A concrete ``ExecutionLoop`` implementation.

    Raises:
        ValueError: If ``loop_type`` is not recognized.
    """
    if loop_type == "react":
        return ReactLoop(
            approval_gate=approval_gate,
            stagnation_detector=stagnation_detector,
            compaction_callback=compaction_callback,
        )
    if loop_type == "plan_execute":
        return PlanExecuteLoop(
            config=plan_execute_config,
            approval_gate=approval_gate,
            stagnation_detector=stagnation_detector,
            compaction_callback=compaction_callback,
        )
    msg = f"Unknown loop type: {loop_type!r}"
    raise ValueError(msg)
