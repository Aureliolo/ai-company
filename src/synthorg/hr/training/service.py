"""Training service orchestrator.

Executes the full training pipeline: source resolution, parallel
extraction + curation, sequential guard chain, memory storage.
"""

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from synthorg.core.enums import MemoryCategory
from synthorg.hr.training.models import (
    ContentType,
    TrainingGuardDecision,
    TrainingItem,
    TrainingPlanStatus,
    TrainingResult,
)
from synthorg.memory.models import MemoryMetadata, MemoryStoreRequest
from synthorg.observability import get_logger
from synthorg.observability.events.training import (
    HR_TRAINING_GUARD_EVALUATION,
    HR_TRAINING_ITEMS_EXTRACTED,
    HR_TRAINING_PLAN_EXECUTED,
    HR_TRAINING_PLAN_IDEMPOTENT,
    HR_TRAINING_SKIPPED,
    HR_TRAINING_STORE_FAILED,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from synthorg.core.types import NotBlankStr
    from synthorg.hr.training.models import TrainingPlan
    from synthorg.hr.training.protocol import (
        ContentExtractor,
        CurationStrategy,
        SourceSelector,
        TrainingGuard,
    )
    from synthorg.memory.protocol import MemoryBackend

logger = get_logger(__name__)

# Map content types to memory categories for storage.
_CONTENT_TYPE_TO_CATEGORY: dict[ContentType, MemoryCategory] = {
    ContentType.PROCEDURAL: MemoryCategory.PROCEDURAL,
    ContentType.SEMANTIC: MemoryCategory.SEMANTIC,
    ContentType.TOOL_PATTERNS: MemoryCategory.PROCEDURAL,
}

# Internal type alias for curated items map passed through pipeline.
_CuratedMap = dict[ContentType, tuple[TrainingItem, ...]]


class TrainingService:
    """Training pipeline orchestrator.

    Executes the full training flow: source resolution, parallel
    extraction + curation, sequential guard chain, and memory
    storage.  All pipeline state is local to each ``execute()``
    call -- no instance state leaks between invocations.

    Args:
        selector: Source agent selector.
        extractors: Content extractors keyed by content type.
        curation: Curation strategy.
        guards: Guard chain (applied in order).
        memory_backend: Memory backend for storing items.
        training_namespace: Memory namespace for stored items.
        training_tags: Default tags for stored items.
    """

    def __init__(  # noqa: PLR0913
        self,
        *,
        selector: SourceSelector,
        extractors: Mapping[ContentType, ContentExtractor],
        curation: CurationStrategy,
        guards: tuple[TrainingGuard, ...],
        memory_backend: MemoryBackend,
        training_namespace: str = "training",
        training_tags: tuple[str, ...] = ("learned_from_seniors",),
    ) -> None:
        self._selector = selector
        self._extractors = extractors
        self._curation = curation
        self._guards = guards
        self._memory_backend = memory_backend
        self._training_namespace = training_namespace
        self._training_tags = training_tags

    async def execute(self, plan: TrainingPlan) -> TrainingResult:
        """Execute the full training pipeline.

        Args:
            plan: Training plan to execute.

        Returns:
            Training result with pipeline metrics.
        """
        started_at = datetime.now(UTC)

        # 1. Idempotency check.
        if plan.status == TrainingPlanStatus.EXECUTED:
            logger.info(
                HR_TRAINING_PLAN_IDEMPOTENT,
                plan_id=str(plan.id),
            )
            return self._empty_result(plan, started_at)

        # 2. Skip check.
        if plan.skip_training:
            logger.info(
                HR_TRAINING_SKIPPED,
                plan_id=str(plan.id),
            )
            return self._empty_result(plan, started_at)

        # 3. Source resolution.
        source_ids = await self._resolve_sources(plan)

        # 4. Parallel extraction + curation.
        extracted, curated, curated_items = await self._extract_and_curate(
            plan, source_ids
        )

        # 5. Sequential guard chain.
        guarded, errors, guarded_items = await self._apply_guards(plan, curated_items)

        # 6. Storage.
        stored = await self._store_items(plan, guarded_items)

        completed_at = datetime.now(UTC)

        logger.info(
            HR_TRAINING_PLAN_EXECUTED,
            plan_id=str(plan.id),
            source_count=len(source_ids),
            extracted_total=sum(c for _, c in extracted),
            stored_total=sum(c for _, c in stored),
        )

        return TrainingResult(
            plan_id=plan.id,
            new_agent_id=plan.new_agent_id,
            source_agents_used=source_ids,
            items_extracted=extracted,
            items_after_curation=curated,
            items_after_guards=guarded,
            items_stored=stored,
            errors=errors,
            started_at=started_at,
            completed_at=completed_at,
        )

    async def preview(self, plan: TrainingPlan) -> TrainingResult:
        """Dry-run: extract + curate without guards or storage.

        Args:
            plan: Training plan to preview.

        Returns:
            Result with extraction and curation counts only.
        """
        started_at = datetime.now(UTC)
        source_ids = await self._resolve_sources(plan)
        extracted, curated, _curated_items = await self._extract_and_curate(
            plan, source_ids
        )

        return TrainingResult(
            plan_id=plan.id,
            new_agent_id=plan.new_agent_id,
            source_agents_used=source_ids,
            items_extracted=extracted,
            items_after_curation=curated,
            started_at=started_at,
            completed_at=datetime.now(UTC),
        )

    async def _resolve_sources(
        self,
        plan: TrainingPlan,
    ) -> tuple[NotBlankStr, ...]:
        """Resolve source agent IDs."""
        if plan.override_sources:
            return plan.override_sources
        return await self._selector.select(
            new_agent_role=plan.new_agent_role,
            new_agent_level=plan.new_agent_level,
        )

    async def _extract_and_curate(
        self,
        plan: TrainingPlan,
        source_ids: tuple[NotBlankStr, ...],
    ) -> tuple[
        tuple[tuple[ContentType, int], ...],
        tuple[tuple[ContentType, int], ...],
        _CuratedMap,
    ]:
        """Run extraction + curation in parallel per content type.

        Returns extracted counts, curated counts, and the curated
        items map (local, not stored on self).
        """
        extracted_counts: list[tuple[ContentType, int]] = []
        curated_counts: list[tuple[ContentType, int]] = []
        curated_items: _CuratedMap = {}

        async def _process(ct: ContentType) -> None:
            extractor = self._extractors.get(ct)
            if extractor is None:
                return

            items = await extractor.extract(
                source_agent_ids=source_ids,
                new_agent_role=plan.new_agent_role,
                new_agent_level=plan.new_agent_level,
            )
            extracted_counts.append((ct, len(items)))

            logger.debug(
                HR_TRAINING_ITEMS_EXTRACTED,
                content_type=ct.value,
                count=len(items),
            )

            curated = await self._curation.curate(
                items,
                new_agent_role=plan.new_agent_role,
                new_agent_level=plan.new_agent_level,
                content_type=ct,
            )
            curated_counts.append((ct, len(curated)))
            curated_items[ct] = curated

        async with asyncio.TaskGroup() as tg:
            for ct in plan.enabled_content_types:
                tg.create_task(_process(ct))

        return (
            tuple(extracted_counts),
            tuple(curated_counts),
            curated_items,
        )

    async def _apply_guards(
        self,
        plan: TrainingPlan,
        curated_items: _CuratedMap,
    ) -> tuple[
        tuple[tuple[ContentType, int], ...],
        tuple[str, ...],
        _CuratedMap,
    ]:
        """Apply guard chain sequentially per content type.

        Returns guarded counts, errors, and the guarded items map.
        """
        guarded_counts: list[tuple[ContentType, int]] = []
        all_errors: list[str] = []
        guarded_items: _CuratedMap = {}

        for ct, items in curated_items.items():
            current_items = items
            for guard in self._guards:
                decision: TrainingGuardDecision = await guard.evaluate(
                    current_items,
                    content_type=ct,
                    plan=plan,
                )

                logger.debug(
                    HR_TRAINING_GUARD_EVALUATION,
                    guard=guard.name,
                    content_type=ct.value,
                    approved=len(decision.approved_items),
                    rejected=decision.rejected_count,
                )

                current_items = decision.approved_items
                all_errors.extend(decision.rejection_reasons)

            guarded_counts.append((ct, len(current_items)))
            guarded_items[ct] = current_items

        return tuple(guarded_counts), tuple(all_errors), guarded_items

    async def _store_items(
        self,
        plan: TrainingPlan,
        guarded_items: _CuratedMap,
    ) -> tuple[tuple[ContentType, int], ...]:
        """Store approved items to memory backend."""
        stored_counts: list[tuple[ContentType, int]] = []

        for ct, items in guarded_items.items():
            stored = 0
            category = _CONTENT_TYPE_TO_CATEGORY.get(ct, MemoryCategory.PROCEDURAL)

            for item in items:
                tags = (
                    *self._training_tags,
                    f"training:{plan.id}",
                    f"source:{item.source_agent_id}",
                )
                try:
                    request = MemoryStoreRequest(
                        category=category,
                        namespace=self._training_namespace,
                        content=item.content,
                        metadata=MemoryMetadata(
                            source=f"training:{plan.id}",
                            confidence=item.relevance_score,
                            tags=tags,
                        ),
                    )
                    await self._memory_backend.store(
                        plan.new_agent_id,
                        request,
                    )
                    stored += 1
                except Exception:
                    logger.warning(
                        HR_TRAINING_STORE_FAILED,
                        plan_id=str(plan.id),
                        item_id=str(item.id),
                        content_type=ct.value,
                    )

            stored_counts.append((ct, stored))

        return tuple(stored_counts)

    @staticmethod
    def _empty_result(
        plan: TrainingPlan,
        started_at: datetime,
    ) -> TrainingResult:
        """Build an empty result for skipped/idempotent plans."""
        return TrainingResult(
            plan_id=plan.id,
            new_agent_id=plan.new_agent_id,
            started_at=started_at,
            completed_at=datetime.now(UTC),
        )
