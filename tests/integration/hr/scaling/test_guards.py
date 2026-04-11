"""Integration: guard chain enforcement.

Tests cooldown, rate limit, and conflict resolution working
together in the full guard chain.
"""

import pytest

from synthorg.hr.scaling.config import GuardConfig, ScalingConfig
from synthorg.hr.scaling.context import ScalingContextBuilder
from synthorg.hr.scaling.enums import ScalingActionType
from synthorg.hr.scaling.factory import (
    create_scaling_guards,
    create_scaling_strategies,
)
from synthorg.hr.scaling.guards.cooldown import CooldownGuard
from synthorg.hr.scaling.guards.rate_limit import RateLimitGuard
from synthorg.hr.scaling.service import ScalingService
from synthorg.hr.scaling.signals.workload import WorkloadSignalSource

from .conftest import AGENT_IDS


@pytest.mark.integration
class TestGuardChain:
    """Guard chain integration: cooldown + rate limit + conflict."""

    async def test_rate_limit_blocks_excess_hires(self) -> None:
        """Rate limit drops decisions after the daily cap is reached."""
        config = ScalingConfig(
            guards=GuardConfig(max_hires_per_day=1),
        )
        strategies = create_scaling_strategies(config)
        guard = create_scaling_guards(config)

        builder = ScalingContextBuilder(
            workload_source=WorkloadSignalSource(max_concurrent_tasks=3),
        )

        service = ScalingService(
            strategies=strategies,
            guard=guard,
            context_builder=builder,
            config=config,
        )

        from synthorg.engine.assignment.models import AgentWorkload

        workloads = tuple(
            AgentWorkload(
                agent_id=aid,
                active_task_count=3,
                total_cost_usd=10.0,
            )
            for aid in AGENT_IDS
        )

        kwargs = {"workload_kwargs": {"workloads": workloads}}

        # First evaluation should produce a hire.
        d1 = await service.evaluate(agent_ids=AGENT_IDS, context_kwargs=kwargs)
        hires1 = [d for d in d1 if d.action_type == ScalingActionType.HIRE]
        assert len(hires1) >= 1

        # Record the hire in the rate limiter.
        # Access the composite guard's inner rate limit guard.
        from synthorg.hr.scaling.guards.composite import CompositeScalingGuard

        assert isinstance(guard, CompositeScalingGuard)
        for g in guard.get_guards():
            if isinstance(g, RateLimitGuard):
                for h in hires1:
                    await g.record_action(h)

        # Second evaluation should be blocked by rate limit.
        d2 = await service.evaluate(agent_ids=AGENT_IDS, context_kwargs=kwargs)
        hires2 = [d for d in d2 if d.action_type == ScalingActionType.HIRE]
        assert len(hires2) == 0

    async def test_cooldown_blocks_repeated_actions(self) -> None:
        """Cooldown drops decisions within the cooldown window."""
        config = ScalingConfig(
            guards=GuardConfig(cooldown_seconds=3600),
        )
        strategies = create_scaling_strategies(config)
        guard = create_scaling_guards(config)

        builder = ScalingContextBuilder(
            workload_source=WorkloadSignalSource(max_concurrent_tasks=3),
        )

        service = ScalingService(
            strategies=strategies,
            guard=guard,
            context_builder=builder,
            config=config,
        )

        from synthorg.engine.assignment.models import AgentWorkload

        workloads = tuple(
            AgentWorkload(
                agent_id=aid,
                active_task_count=3,
                total_cost_usd=10.0,
            )
            for aid in AGENT_IDS
        )

        kwargs = {"workload_kwargs": {"workloads": workloads}}

        d1 = await service.evaluate(agent_ids=AGENT_IDS, context_kwargs=kwargs)
        hires1 = [d for d in d1 if d.action_type == ScalingActionType.HIRE]
        assert len(hires1) >= 1

        # Record the hire in the cooldown guard.
        from synthorg.hr.scaling.guards.composite import CompositeScalingGuard

        assert isinstance(guard, CompositeScalingGuard)
        for g in guard.get_guards():
            if isinstance(g, CooldownGuard):
                for h in hires1:
                    await g.record_action(h)

        # Second evaluation within cooldown should be blocked.
        d2 = await service.evaluate(agent_ids=AGENT_IDS, context_kwargs=kwargs)
        hires2 = [d for d in d2 if d.action_type == ScalingActionType.HIRE]
        assert len(hires2) == 0
