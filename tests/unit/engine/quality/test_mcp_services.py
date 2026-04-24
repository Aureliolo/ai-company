"""Direct unit tests for the quality facade services."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from synthorg.communication.mcp_errors import CapabilityNotSupportedError
from synthorg.core.types import NotBlankStr
from synthorg.engine.quality.mcp_services import (
    EvaluationVersionService,
    QualityFacadeService,
    ReviewFacadeService,
)

pytestmark = pytest.mark.unit


# ── QualityFacadeService ──────────────────────────────────────────


class TestQualityFacadeService:
    async def test_get_summary_capability_gap_without_tracker_method(self) -> None:
        service = QualityFacadeService(tracker=SimpleNamespace())  # type: ignore[arg-type]
        with pytest.raises(CapabilityNotSupportedError):
            await service.get_summary()

    async def test_get_agent_quality_capability_gap(self) -> None:
        service = QualityFacadeService(tracker=SimpleNamespace())  # type: ignore[arg-type]
        with pytest.raises(CapabilityNotSupportedError):
            await service.get_agent_quality(NotBlankStr("agent-1"))

    async def test_list_scores_capability_gap(self) -> None:
        service = QualityFacadeService(tracker=SimpleNamespace())  # type: ignore[arg-type]
        with pytest.raises(CapabilityNotSupportedError):
            await service.list_scores()


# ── ReviewFacadeService ───────────────────────────────────────────


class TestReviewFacadeService:
    async def test_create_then_get(self) -> None:
        service = ReviewFacadeService()
        created = await service.create_review(
            task_id=NotBlankStr("task-1"),
            reviewer_id=NotBlankStr("bob"),
            verdict=NotBlankStr("approve"),
        )
        fetched = await service.get_review(NotBlankStr(str(created.id)))
        assert fetched is not None
        assert fetched.verdict == "approve"

    async def test_list_is_newest_first(self) -> None:
        service = ReviewFacadeService()
        first = await service.create_review(
            task_id=NotBlankStr("t1"),
            reviewer_id=NotBlankStr("r"),
            verdict=NotBlankStr("approve"),
        )
        second = await service.create_review(
            task_id=NotBlankStr("t2"),
            reviewer_id=NotBlankStr("r"),
            verdict=NotBlankStr("reject"),
        )
        page, total = await service.list_reviews()
        assert total == 2
        assert page[0].id == second.id
        assert page[1].id == first.id

    async def test_update_patches_fields(self) -> None:
        service = ReviewFacadeService()
        created = await service.create_review(
            task_id=NotBlankStr("t"),
            reviewer_id=NotBlankStr("r"),
            verdict=NotBlankStr("pending"),
        )
        updated = await service.update_review(
            review_id=NotBlankStr(str(created.id)),
            verdict=NotBlankStr("approve"),
            comments="looks good",
            actor_id=NotBlankStr("r"),
        )
        assert updated is not None
        assert updated.verdict == "approve"
        assert updated.comments == "looks good"

    async def test_update_missing_returns_none(self) -> None:
        service = ReviewFacadeService()
        result = await service.update_review(
            review_id=NotBlankStr(str(uuid4())),
            actor_id=NotBlankStr("r"),
        )
        assert result is None

    async def test_update_invalid_uuid_returns_none(self) -> None:
        service = ReviewFacadeService()
        result = await service.update_review(
            review_id=NotBlankStr("bad"),
            actor_id=NotBlankStr("r"),
        )
        assert result is None

    async def test_get_invalid_uuid_returns_none(self) -> None:
        service = ReviewFacadeService()
        assert await service.get_review(NotBlankStr("bad")) is None


# ── EvaluationVersionService ──────────────────────────────────────


class TestEvaluationVersionService:
    async def test_list_versions_capability_gap_when_unwired(self) -> None:
        service = EvaluationVersionService(persistence=None)
        with pytest.raises(CapabilityNotSupportedError):
            await service.list_versions()

    async def test_get_version_capability_gap_when_unwired(self) -> None:
        service = EvaluationVersionService(persistence=None)
        with pytest.raises(CapabilityNotSupportedError):
            await service.get_version(NotBlankStr("v1"))

    async def test_list_versions_capability_gap_without_accessor(self) -> None:
        service = EvaluationVersionService(
            persistence=SimpleNamespace(),
        )
        with pytest.raises(CapabilityNotSupportedError):
            await service.list_versions()

    async def test_get_version_capability_gap_without_accessor(self) -> None:
        service = EvaluationVersionService(
            persistence=SimpleNamespace(),
        )
        with pytest.raises(CapabilityNotSupportedError):
            await service.get_version(NotBlankStr("v1"))

    async def test_list_versions_delegates_when_available(self) -> None:
        class _Repo:
            async def list_versions(self) -> tuple[object, ...]:
                return ("v1", "v2")

        persistence = SimpleNamespace(evaluation_config_versions=_Repo())
        service = EvaluationVersionService(persistence=persistence)
        assert await service.list_versions() == ("v1", "v2")

    async def test_get_version_delegates_when_available(self) -> None:
        class _Repo:
            async def get_version(self, vid: str) -> object | None:
                return {"id": vid}

        persistence = SimpleNamespace(evaluation_config_versions=_Repo())
        service = EvaluationVersionService(persistence=persistence)
        assert await service.get_version(NotBlankStr("v1")) == {"id": "v1"}
