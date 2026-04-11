"""Unit tests for training mode service orchestrator."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from synthorg.core.enums import SeniorityLevel
from synthorg.hr.training.models import (
    ContentType,
    TrainingGuardDecision,
    TrainingItem,
    TrainingPlan,
    TrainingPlanStatus,
)
from synthorg.hr.training.service import TrainingService


def _now() -> datetime:
    return datetime.now(UTC)


def _make_item(
    *,
    content: str = "Knowledge item",
    content_type: ContentType = ContentType.PROCEDURAL,
) -> TrainingItem:
    return TrainingItem(
        source_agent_id="senior-1",
        content_type=content_type,
        content=content,
        created_at=_now(),
        relevance_score=0.8,
    )


def _make_plan(
    *,
    skip_training: bool = False,
    require_review: bool = False,
    status: TrainingPlanStatus = TrainingPlanStatus.PENDING,
    executed_at: datetime | None = None,
) -> TrainingPlan:
    return TrainingPlan(
        new_agent_id="new-1",
        new_agent_role="engineer",
        new_agent_level=SeniorityLevel.JUNIOR,
        skip_training=skip_training,
        require_review=require_review,
        status=status,
        executed_at=executed_at,
        created_at=_now(),
    )


def _make_guard_decision(
    items: tuple[TrainingItem, ...],
) -> TrainingGuardDecision:
    return TrainingGuardDecision(
        approved_items=items,
        rejected_count=0,
        guard_name="test",
    )


def _make_service(
    *,
    selector: AsyncMock | None = None,
    extractors: dict | None = None,
    curation: AsyncMock | None = None,
    guards: tuple | None = None,
    memory_backend: AsyncMock | None = None,
) -> TrainingService:
    """Build a TrainingService with mocked dependencies."""
    if selector is None:
        selector = AsyncMock()
        selector.select.return_value = ("senior-1",)

    if extractors is None:
        ext = AsyncMock()
        ext.content_type = ContentType.PROCEDURAL
        ext.extract.return_value = (_make_item(),)
        extractors = {ContentType.PROCEDURAL: ext}

    if curation is None:
        curation = AsyncMock()
        curation.curate.side_effect = lambda items, **kw: items

    if guards is None:
        guard = AsyncMock()
        guard.evaluate.side_effect = lambda items, **kw: _make_guard_decision(items)
        guards = (guard,)

    if memory_backend is None:
        memory_backend = AsyncMock()
        memory_backend.store.return_value = "stored-id"

    return TrainingService(
        selector=selector,
        extractors=extractors,
        curation=curation,
        guards=guards,
        memory_backend=memory_backend,
        training_namespace="training",
        training_tags=("learned_from_seniors",),
    )


@pytest.mark.unit
class TestTrainingServiceExecute:
    """TrainingService.execute() tests."""

    async def test_full_pipeline(self) -> None:
        service = _make_service()
        plan = _make_plan()
        result = await service.execute(plan)

        assert result.new_agent_id == "new-1"
        assert len(result.source_agents_used) > 0
        assert len(result.items_stored) > 0

    async def test_idempotent_re_execution(self) -> None:
        service = _make_service()
        plan = _make_plan(
            status=TrainingPlanStatus.EXECUTED,
            executed_at=_now(),
        )
        result = await service.execute(plan)
        # Should return empty result (no-op)
        assert result.items_stored == ()

    async def test_skip_training(self) -> None:
        service = _make_service()
        plan = _make_plan(skip_training=True)
        result = await service.execute(plan)
        assert result.items_stored == ()

    async def test_uses_override_sources(self) -> None:
        selector = AsyncMock()
        service = _make_service(selector=selector)
        plan = TrainingPlan(
            new_agent_id="new-1",
            new_agent_role="engineer",
            new_agent_level=SeniorityLevel.JUNIOR,
            override_sources=("override-1", "override-2"),
            require_review=False,
            created_at=_now(),
        )
        result = await service.execute(plan)
        # Selector should NOT be called when override_sources is set
        selector.select.assert_not_called()
        assert "override-1" in result.source_agents_used

    async def test_stores_to_memory_backend(self) -> None:
        backend = AsyncMock()
        backend.store.return_value = "stored-id"
        service = _make_service(memory_backend=backend)
        plan = _make_plan(require_review=False)
        await service.execute(plan)
        backend.store.assert_called()

    async def test_collects_guard_errors(self) -> None:
        guard = AsyncMock()
        guard.evaluate.return_value = TrainingGuardDecision(
            approved_items=(),
            rejected_count=5,
            guard_name="test_guard",
            rejection_reasons=("Rejected by test",),
        )
        service = _make_service(guards=(guard,))
        plan = _make_plan()
        result = await service.execute(plan)
        assert len(result.errors) > 0


@pytest.mark.unit
class TestTrainingServicePreview:
    """TrainingService.preview() tests."""

    async def test_preview_does_not_store(self) -> None:
        backend = AsyncMock()
        service = _make_service(memory_backend=backend)
        plan = _make_plan()
        result = await service.preview(plan)
        backend.store.assert_not_called()
        assert result.items_stored == ()

    async def test_preview_returns_extraction_counts(self) -> None:
        service = _make_service()
        plan = _make_plan()
        result = await service.preview(plan)
        assert len(result.items_extracted) > 0
        assert len(result.items_after_curation) > 0
