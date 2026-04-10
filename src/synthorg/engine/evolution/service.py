"""Evolution service -- orchestrates the evolution pipeline.

Trigger -> build context -> proposer -> guards -> adapter.apply.
"""

import asyncio
from typing import TYPE_CHECKING

from synthorg.engine.evolution.models import (
    AdaptationAxis,
    AdaptationDecision,
    AdaptationProposal,
    EvolutionEvent,
)
from synthorg.observability import get_logger
from synthorg.observability.events.evolution import (
    EVOLUTION_ADAPTATION_FAILED,
    EVOLUTION_ADAPTED,
    EVOLUTION_CONTEXT_BUILD_FAILED,
    EVOLUTION_GUARDS_PASSED,
    EVOLUTION_GUARDS_REJECTED,
    EVOLUTION_PROPOSAL_GENERATED,
    EVOLUTION_SERVICE_COMPLETE,
    EVOLUTION_SERVICE_STARTED,
)

if TYPE_CHECKING:
    from synthorg.core.types import NotBlankStr
    from synthorg.engine.evolution.config import EvolutionConfig
    from synthorg.engine.evolution.protocols import (
        AdaptationAdapter,
        AdaptationGuard,
        AdaptationProposer,
        EvolutionContext,
    )
    from synthorg.engine.identity.store.protocol import (
        IdentityVersionStore,
    )
    from synthorg.hr.performance.tracker import PerformanceTracker
    from synthorg.memory.models import MemoryEntry
    from synthorg.memory.protocol import MemoryBackend

logger = get_logger(__name__)


class EvolutionService:
    """Orchestrates the agent evolution pipeline.

    Pipeline:
    1. Build ``EvolutionContext`` from identity store, tracker, memory
    2. Call proposer to generate ``AdaptationProposal``(s)
    3. For each proposal, run through guards
    4. For approved proposals, dispatch to matching adapter by axis
    5. Record ``EvolutionEvent``

    Args:
        identity_store: Versioned identity storage.
        tracker: Performance tracker for snapshot data.
        proposer: Adaptation proposer strategy.
        guard: Adaptation guard (typically CompositeGuard).
        adapters: Mapping from axis to adapter.
        memory_backend: Memory backend for context retrieval.
        config: Evolution configuration.
    """

    def __init__(  # noqa: PLR0913
        self,
        *,
        identity_store: IdentityVersionStore,
        tracker: PerformanceTracker,
        proposer: AdaptationProposer,
        guard: AdaptationGuard,
        adapters: dict[AdaptationAxis, AdaptationAdapter],
        memory_backend: MemoryBackend | None = None,
        config: EvolutionConfig,
    ) -> None:
        self._identity_store = identity_store
        self._tracker = tracker
        self._proposer = proposer
        self._guard = guard
        self._adapters = adapters
        self._memory_backend = memory_backend
        self._config = config

    async def evolve(
        self,
        *,
        agent_id: NotBlankStr,
    ) -> tuple[EvolutionEvent, ...]:
        """Run the evolution pipeline for an agent.

        Args:
            agent_id: Agent to evolve.

        Returns:
            Tuple of evolution events (one per proposal).
            Empty if no proposals or all rejected.
        """
        if not self._config.enabled:
            return ()

        logger.info(
            EVOLUTION_SERVICE_STARTED,
            agent_id=str(agent_id),
        )

        # 1. Build context.
        try:
            context = await self._build_context(agent_id)
        except MemoryError, RecursionError:
            raise
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning(
                EVOLUTION_CONTEXT_BUILD_FAILED,
                agent_id=str(agent_id),
                error=f"{type(exc).__name__}: {exc}",
                exc_info=True,
            )
            return ()

        # 2. Generate proposals.
        proposals = await self._proposer.propose(
            agent_id=agent_id,
            context=context,
        )
        if not proposals:
            logger.info(
                EVOLUTION_SERVICE_COMPLETE,
                agent_id=str(agent_id),
                proposals=0,
                applied=0,
            )
            return ()

        logger.info(
            EVOLUTION_PROPOSAL_GENERATED,
            agent_id=str(agent_id),
            proposal_count=len(proposals),
        )

        # 3-4. Evaluate guards and apply.
        events: list[EvolutionEvent] = []
        for proposal in proposals:
            event = await self._process_proposal(agent_id, proposal)
            events.append(event)

        applied_count = sum(1 for e in events if e.applied)
        logger.info(
            EVOLUTION_SERVICE_COMPLETE,
            agent_id=str(agent_id),
            proposals=len(proposals),
            applied=applied_count,
        )
        return tuple(events)

    async def _process_proposal(  # noqa: C901
        self,
        agent_id: NotBlankStr,
        proposal: AdaptationProposal,
    ) -> EvolutionEvent:
        """Evaluate a single proposal through guards and apply."""
        # Check if the axis is enabled.
        axis_enabled = self._is_axis_enabled(proposal.axis)
        if not axis_enabled:
            decision = AdaptationDecision(
                proposal_id=proposal.id,
                approved=False,
                guard_name="config",
                reason=f"axis {proposal.axis.value} is disabled",
            )
            return EvolutionEvent(
                agent_id=agent_id,
                proposal=proposal,
                decision=decision,
                applied=False,
            )

        # Run through guards.
        decision = await self._guard.evaluate(proposal)
        if not decision.approved:
            logger.info(
                EVOLUTION_GUARDS_REJECTED,
                agent_id=str(agent_id),
                axis=proposal.axis.value,
                guard=str(decision.guard_name),
                reason=str(decision.reason),
            )
            return EvolutionEvent(
                agent_id=agent_id,
                proposal=proposal,
                decision=decision,
                applied=False,
            )

        logger.info(
            EVOLUTION_GUARDS_PASSED,
            agent_id=str(agent_id),
            axis=proposal.axis.value,
        )

        # Get version before adaptation (for identity changes).
        version_before: int | None = None
        version_after: int | None = None
        if proposal.axis == AdaptationAxis.IDENTITY:
            versions = await self._identity_store.list_versions(
                agent_id,
            )
            if versions:
                version_before = versions[0].version

        # Apply the adaptation.
        adapter = self._adapters.get(proposal.axis)
        if adapter is None:
            logger.warning(
                EVOLUTION_ADAPTATION_FAILED,
                agent_id=str(agent_id),
                axis=proposal.axis.value,
                error=f"no adapter for axis {proposal.axis.value}",
            )
            return EvolutionEvent(
                agent_id=agent_id,
                proposal=proposal,
                decision=decision,
                applied=False,
            )

        try:
            await adapter.apply(proposal, agent_id)
        except MemoryError, RecursionError:
            raise
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning(
                EVOLUTION_ADAPTATION_FAILED,
                agent_id=str(agent_id),
                axis=proposal.axis.value,
                error=f"{type(exc).__name__}: {exc}",
                exc_info=True,
            )
            return EvolutionEvent(
                agent_id=agent_id,
                proposal=proposal,
                decision=decision,
                applied=False,
            )

        # Get version after adaptation.
        if proposal.axis == AdaptationAxis.IDENTITY:
            versions = await self._identity_store.list_versions(
                agent_id,
            )
            if versions:
                version_after = versions[0].version

        logger.info(
            EVOLUTION_ADAPTED,
            agent_id=str(agent_id),
            axis=proposal.axis.value,
            version_before=version_before,
            version_after=version_after,
        )

        return EvolutionEvent(
            agent_id=agent_id,
            proposal=proposal,
            decision=decision,
            applied=True,
            identity_version_before=version_before,
            identity_version_after=version_after,
        )

    def _is_axis_enabled(self, axis: AdaptationAxis) -> bool:
        """Check if an adaptation axis is enabled in config."""
        adapter_cfg = self._config.adapters
        if axis == AdaptationAxis.IDENTITY:
            return adapter_cfg.identity
        if axis == AdaptationAxis.STRATEGY_SELECTION:
            return adapter_cfg.strategy_selection
        if axis == AdaptationAxis.PROMPT_TEMPLATE:
            return adapter_cfg.prompt_template
        return False  # type: ignore[unreachable]  # pragma: no cover

    async def _build_context(
        self,
        agent_id: NotBlankStr,
    ) -> EvolutionContext:
        """Build the evolution context for an agent."""
        from synthorg.engine.evolution.protocols import (  # noqa: PLC0415
            EvolutionContext,
        )

        identity = await self._identity_store.get_current(agent_id)
        if identity is None:
            msg = f"Agent {agent_id!r} not found in identity store"
            raise ValueError(msg)

        # Get performance snapshot (best-effort).
        snapshot = None
        try:
            snapshot = await self._tracker.get_snapshot(agent_id)
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.debug(
                "evolution.context.snapshot_failed",
                agent_id=str(agent_id),
            )

        # Get recent procedural memories (best-effort).
        memories: tuple[MemoryEntry, ...] = ()
        if self._memory_backend is not None:
            try:
                from synthorg.core.enums import (  # noqa: PLC0415
                    MemoryCategory,
                )
                from synthorg.memory.models import (  # noqa: PLC0415
                    MemoryQuery,
                )

                result = await self._memory_backend.retrieve(
                    agent_id,
                    MemoryQuery(
                        text="procedural evolution context",
                        categories=frozenset([MemoryCategory.PROCEDURAL]),
                        limit=10,
                    ),
                )
                memories = result
            except MemoryError, RecursionError:
                raise
            except Exception:
                logger.debug(
                    "evolution.context.memory_failed",
                    agent_id=str(agent_id),
                )

        # Get recent task metrics.
        task_results = self._tracker.get_task_metrics(
            agent_id=agent_id,
        )
        # Limit to most recent 20.
        recent_tasks = task_results[-20:] if task_results else ()

        return EvolutionContext(
            agent_id=agent_id,
            identity=identity,
            performance_snapshot=snapshot,
            recent_task_results=tuple(recent_tasks),
            recent_procedural_memories=memories,
        )
