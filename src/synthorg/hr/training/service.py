"""Training service orchestrator.

Executes the full training pipeline: source resolution, parallel
extraction + curation, sequential guard chain, memory storage.
"""

import asyncio
import copy
from datetime import UTC, datetime
from types import MappingProxyType
from typing import TYPE_CHECKING

from synthorg.core.enums import MemoryCategory
from synthorg.hr.training.models import (
    ContentType,
    TrainingApprovalHandle,
    TrainingGuardDecision,
    TrainingItem,
    TrainingPlanStatus,
    TrainingResult,
)
from synthorg.memory.errors import MemoryError as _MemoryError
from synthorg.memory.models import MemoryMetadata, MemoryStoreRequest
from synthorg.observability import get_logger
from synthorg.observability.events.training import (
    HR_TRAINING_CURATION_FAILED,
    HR_TRAINING_EXTRACTION_FAILED,
    HR_TRAINING_GUARD_EVALUATION,
    HR_TRAINING_GUARD_FAILED,
    HR_TRAINING_ITEMS_EXTRACTED,
    HR_TRAINING_PLAN_EXECUTED,
    HR_TRAINING_PLAN_FAILED,
    HR_TRAINING_PLAN_IDEMPOTENT,
    HR_TRAINING_REVIEW_PENDING,
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
    storage.  Idempotency is enforced per ``plan.id`` within this
    service instance: concurrent or repeated ``execute()`` calls
    with the same plan id see a no-op after the first successful
    run.

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
        # Deep copy + freeze so external mutation of the caller-owned
        # mapping cannot alter pipeline behavior mid-flight.
        self._extractors: Mapping[ContentType, ContentExtractor] = MappingProxyType(
            copy.deepcopy(dict(extractors)),
        )
        self._curation = curation
        self._guards = guards
        self._memory_backend = memory_backend
        self._training_namespace = training_namespace
        self._training_tags = training_tags
        self._executed_plan_ids: set[str] = set()
        self._idempotency_lock = asyncio.Lock()

    async def execute(self, plan: TrainingPlan) -> TrainingResult:
        """Execute the full training pipeline.

        Idempotent by ``plan.id``: re-running the same plan after a
        successful execution returns an empty result without touching
        the memory backend.  Concurrent calls are serialized on the
        idempotency lock so exactly one caller performs the run.

        Args:
            plan: Training plan to execute.

        Returns:
            Training result with pipeline metrics.
        """
        started_at = datetime.now(UTC)

        # Pre-flight short-circuits do not require the lock.
        if plan.status == TrainingPlanStatus.EXECUTED:
            logger.info(
                HR_TRAINING_PLAN_IDEMPOTENT,
                plan_id=str(plan.id),
                reason="status_executed",
            )
            return self._empty_result(plan, started_at)

        if plan.skip_training:
            logger.info(
                HR_TRAINING_SKIPPED,
                plan_id=str(plan.id),
            )
            return self._empty_result(plan, started_at)

        async with self._idempotency_lock:
            if str(plan.id) in self._executed_plan_ids:
                logger.info(
                    HR_TRAINING_PLAN_IDEMPOTENT,
                    plan_id=str(plan.id),
                    reason="already_executed_in_service",
                )
                return self._empty_result(plan, started_at)

            try:
                result = await self._run_pipeline(plan, started_at)
            except Exception as exc:
                logger.exception(
                    HR_TRAINING_PLAN_FAILED,
                    plan_id=str(plan.id),
                    error=str(exc),
                )
                raise
            self._executed_plan_ids.add(str(plan.id))
            return result

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

    async def _run_pipeline(
        self,
        plan: TrainingPlan,
        started_at: datetime,
    ) -> TrainingResult:
        """Execute extraction, curation, guards, and storage."""
        source_ids = await self._resolve_sources(plan)
        extracted, curated, curated_items = await self._extract_and_curate(
            plan, source_ids
        )
        (
            guarded,
            errors,
            guarded_items,
            approval_id,
            pending_approvals,
        ) = await self._apply_guards(plan, curated_items)
        stored = await self._store_items(plan, guarded_items)

        completed_at = datetime.now(UTC)

        logger.info(
            HR_TRAINING_PLAN_EXECUTED,
            plan_id=str(plan.id),
            source_count=len(source_ids),
            extracted_total=sum(c for _, c in extracted),
            stored_total=sum(c for _, c in stored),
            review_pending=bool(pending_approvals),
        )

        return TrainingResult(
            plan_id=plan.id,
            new_agent_id=plan.new_agent_id,
            source_agents_used=source_ids,
            items_extracted=extracted,
            items_after_curation=curated,
            items_after_guards=guarded,
            items_stored=stored,
            approval_item_id=approval_id,
            pending_approvals=pending_approvals,
            review_pending=bool(pending_approvals),
            errors=errors,
            started_at=started_at,
            completed_at=completed_at,
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
            new_agent_department=plan.new_agent_department,
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

        Each content type runs extraction then curation in its own
        task.  Results are returned from each task and merged after
        the TaskGroup completes -- no shared mutable state during
        the parallel phase.  Iteration order is deterministic via
        sorted content type values.
        """
        ordered_types = tuple(
            sorted(plan.enabled_content_types, key=lambda ct: ct.value),
        )

        async with asyncio.TaskGroup() as tg:
            tasks = [
                tg.create_task(
                    self._extract_and_curate_one(plan, source_ids, ct),
                )
                for ct in ordered_types
            ]

        extracted_counts: list[tuple[ContentType, int]] = []
        curated_counts: list[tuple[ContentType, int]] = []
        curated_items: _CuratedMap = {}

        for task in tasks:
            result = task.result()
            if result is None:
                continue
            ct, ext_count, cur_count, curated = result
            extracted_counts.append((ct, ext_count))
            curated_counts.append((ct, cur_count))
            curated_items[ct] = curated

        return (
            tuple(extracted_counts),
            tuple(curated_counts),
            curated_items,
        )

    async def _extract_and_curate_one(
        self,
        plan: TrainingPlan,
        source_ids: tuple[NotBlankStr, ...],
        ct: ContentType,
    ) -> tuple[ContentType, int, int, tuple[TrainingItem, ...]] | None:
        """Extract + curate a single content type with error logging."""
        extractor = self._extractors.get(ct)
        if extractor is None:
            msg = (
                f"No extractor configured for content type "
                f"{ct.value!r} (plan {plan.id})"
            )
            raise RuntimeError(msg)

        try:
            items = await extractor.extract(
                source_agent_ids=source_ids,
                new_agent_role=plan.new_agent_role,
                new_agent_level=plan.new_agent_level,
            )
        except Exception as exc:
            logger.exception(
                HR_TRAINING_EXTRACTION_FAILED,
                plan_id=str(plan.id),
                content_type=ct.value,
                error=str(exc),
            )
            raise

        logger.debug(
            HR_TRAINING_ITEMS_EXTRACTED,
            content_type=ct.value,
            count=len(items),
        )

        try:
            curated = await self._curation.curate(
                items,
                new_agent_role=plan.new_agent_role,
                new_agent_level=plan.new_agent_level,
                content_type=ct,
            )
        except Exception as exc:
            logger.exception(
                HR_TRAINING_CURATION_FAILED,
                plan_id=str(plan.id),
                content_type=ct.value,
                error=str(exc),
            )
            raise

        return ct, len(items), len(curated), curated

    async def _apply_guards(
        self,
        plan: TrainingPlan,
        curated_items: _CuratedMap,
    ) -> tuple[
        tuple[tuple[ContentType, int], ...],
        tuple[str, ...],
        _CuratedMap,
        str | None,
        tuple[TrainingApprovalHandle, ...],
    ]:
        """Apply guard chain sequentially per content type.

        Returns guarded counts, errors, guarded items map, the first
        approval item id (for backwards-compatible callers), and the
        full tuple of pending approval handles so no ID is lost when
        multiple content types trigger review.
        """
        guarded_counts: list[tuple[ContentType, int]] = []
        all_errors: list[str] = []
        guarded_items: _CuratedMap = {}
        approval_handles: list[TrainingApprovalHandle] = []

        for ct in sorted(curated_items.keys(), key=lambda c: c.value):
            items = curated_items[ct]
            current_items, errors, handle = await self._run_guards_for_type(
                plan,
                ct,
                items,
            )
            all_errors.extend(errors)
            if handle is not None:
                approval_handles.append(handle)
            guarded_counts.append((ct, len(current_items)))
            guarded_items[ct] = current_items

        approval_id = (
            str(approval_handles[0].approval_item_id) if approval_handles else None
        )

        if approval_handles:
            logger.info(
                HR_TRAINING_REVIEW_PENDING,
                plan_id=str(plan.id),
                approval_count=len(approval_handles),
                content_types=[h.content_type.value for h in approval_handles],
            )

        return (
            tuple(guarded_counts),
            tuple(all_errors),
            guarded_items,
            approval_id,
            tuple(approval_handles),
        )

    async def _run_guards_for_type(
        self,
        plan: TrainingPlan,
        ct: ContentType,
        items: tuple[TrainingItem, ...],
    ) -> tuple[
        tuple[TrainingItem, ...],
        list[str],
        TrainingApprovalHandle | None,
    ]:
        """Apply the guard chain to a single content type."""
        current_items = items
        errors: list[str] = []
        handle: TrainingApprovalHandle | None = None

        for guard in self._guards:
            try:
                decision: TrainingGuardDecision = await guard.evaluate(
                    current_items,
                    content_type=ct,
                    plan=plan,
                )
            except Exception as exc:
                logger.exception(
                    HR_TRAINING_GUARD_FAILED,
                    plan_id=str(plan.id),
                    guard=guard.name,
                    content_type=ct.value,
                    error=str(exc),
                )
                raise

            logger.debug(
                HR_TRAINING_GUARD_EVALUATION,
                guard=guard.name,
                content_type=ct.value,
                approved=len(decision.approved_items),
                rejected=decision.rejected_count,
            )

            current_items = decision.approved_items
            errors.extend(decision.rejection_reasons)

            if decision.approval_item_id is not None:
                handle = TrainingApprovalHandle(
                    approval_item_id=decision.approval_item_id,
                    content_type=ct,
                    item_count=decision.rejected_count,
                )

        return current_items, errors, handle

    async def _store_items(
        self,
        plan: TrainingPlan,
        guarded_items: _CuratedMap,
    ) -> tuple[tuple[ContentType, int], ...]:
        """Store approved items to memory backend in parallel per type."""
        stored_counts: list[tuple[ContentType, int]] = []

        for ct in sorted(guarded_items.keys(), key=lambda c: c.value):
            items = guarded_items[ct]
            stored = await self._store_items_for_type(plan, ct, items)
            stored_counts.append((ct, stored))

        return tuple(stored_counts)

    async def _store_items_for_type(
        self,
        plan: TrainingPlan,
        ct: ContentType,
        items: tuple[TrainingItem, ...],
    ) -> int:
        """Store a single content type's items concurrently."""
        if not items:
            return 0

        category = _CONTENT_TYPE_TO_CATEGORY.get(ct, MemoryCategory.PROCEDURAL)

        async with asyncio.TaskGroup() as tg:
            store_tasks = [
                tg.create_task(self._store_one_item(plan, ct, category, item))
                for item in items
            ]

        return sum(1 for task in store_tasks if task.result())

    async def _store_one_item(
        self,
        plan: TrainingPlan,
        ct: ContentType,
        category: MemoryCategory,
        item: TrainingItem,
    ) -> bool:
        """Store a single training item, logging any store failure."""
        tags = (
            *self._training_tags,
            f"training:{plan.id}",
            f"source:{item.source_agent_id}",
        )
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
        try:
            await self._memory_backend.store(plan.new_agent_id, request)
        except _MemoryError as exc:
            logger.warning(
                HR_TRAINING_STORE_FAILED,
                plan_id=str(plan.id),
                item_id=str(item.id),
                content_type=ct.value,
                error=str(exc),
            )
            return False
        return True

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
