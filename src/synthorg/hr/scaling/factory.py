"""Scaling service factory.

Assembles a fully wired ScalingService from configuration
and injected dependencies.
"""

from typing import TYPE_CHECKING

from synthorg.hr.scaling.context import ScalingContextBuilder
from synthorg.hr.scaling.guards.approval_gate import ApprovalGateGuard
from synthorg.hr.scaling.guards.composite import CompositeScalingGuard
from synthorg.hr.scaling.guards.conflict_resolver import ConflictResolver
from synthorg.hr.scaling.guards.cooldown import CooldownGuard
from synthorg.hr.scaling.guards.rate_limit import RateLimitGuard
from synthorg.hr.scaling.signals.budget import BudgetSignalSource
from synthorg.hr.scaling.signals.skill import SkillSignalSource
from synthorg.hr.scaling.signals.workload import WorkloadSignalSource
from synthorg.hr.scaling.strategies.budget_cap import BudgetCapStrategy
from synthorg.hr.scaling.strategies.skill_gap import SkillGapStrategy
from synthorg.hr.scaling.strategies.workload import (
    WorkloadAutoScaleStrategy,
)
from synthorg.hr.scaling.triggers.batched import BatchedScalingTrigger
from synthorg.observability import get_logger

if TYPE_CHECKING:
    from synthorg.api.approval_store import ApprovalStore
    from synthorg.hr.scaling.config import ScalingConfig
    from synthorg.hr.scaling.protocols import ScalingGuard, ScalingStrategy

logger = get_logger(__name__)


def create_scaling_strategies(
    config: ScalingConfig,
) -> tuple[ScalingStrategy, ...]:
    """Create enabled strategies from configuration.

    Args:
        config: Scaling configuration.

    Returns:
        Tuple of enabled strategy instances.
    """
    strategies: list[ScalingStrategy] = []

    if config.workload.enabled:
        strategies.append(
            WorkloadAutoScaleStrategy(
                hire_threshold=config.workload.hire_threshold,
                prune_threshold=config.workload.prune_threshold,
            ),
        )

    if config.budget_cap.enabled:
        strategies.append(
            BudgetCapStrategy(
                safety_margin=config.budget_cap.safety_margin,
                headroom_fraction=config.budget_cap.headroom_fraction,
            ),
        )

    if config.skill_gap.enabled:
        strategies.append(
            SkillGapStrategy(
                enabled=True,
                min_missing_skills=config.skill_gap.min_missing_skills,
            ),
        )

    return tuple(strategies)


def create_scaling_guards(
    config: ScalingConfig,
    *,
    approval_store: ApprovalStore | None = None,
) -> ScalingGuard:
    """Create the guard chain from configuration.

    Args:
        config: Scaling configuration.
        approval_store: Optional approval store for the approval gate.

    Returns:
        A CompositeScalingGuard or single guard.
    """
    priority_map = {name: idx for idx, name in enumerate(config.priority_order)}

    guards: list[ScalingGuard] = [
        ConflictResolver(priority=priority_map),
        CooldownGuard(cooldown_seconds=config.guards.cooldown_seconds),
        RateLimitGuard(
            max_hires_per_day=config.guards.max_hires_per_day,
            max_prunes_per_day=config.guards.max_prunes_per_day,
        ),
    ]

    if approval_store is not None:
        guards.append(
            ApprovalGateGuard(
                approval_store=approval_store,
                expiry_days=config.guards.approval_expiry_days,
            ),
        )

    return CompositeScalingGuard(guards=tuple(guards))


def create_scaling_context_builder(
    config: ScalingConfig,
) -> ScalingContextBuilder:
    """Create the context builder from configuration.

    Args:
        config: Scaling configuration.

    Returns:
        Configured ScalingContextBuilder.
    """
    workload_src = WorkloadSignalSource() if config.workload.enabled else None
    budget_src = BudgetSignalSource() if config.budget_cap.enabled else None
    skill_src = SkillSignalSource() if config.skill_gap.enabled else None

    return ScalingContextBuilder(
        workload_source=workload_src,
        budget_source=budget_src,
        skill_source=skill_src,
    )


def create_scaling_trigger(
    config: ScalingConfig,
) -> BatchedScalingTrigger:
    """Create the trigger from configuration.

    Args:
        config: Scaling configuration.

    Returns:
        Configured trigger.
    """
    return BatchedScalingTrigger(
        interval_seconds=config.triggers.batched_interval_seconds,
    )
