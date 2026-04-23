# ruff: noqa: D102, EM101, PLR0913
"""Quality facades for the MCP handler layer.

Three facades: QualityFacadeService wraps the performance tracker's
scoring surface; ReviewFacadeService is an in-process review queue;
EvaluationVersionService surfaces evaluation-config version history.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID, uuid4

from synthorg.communication.mcp_errors import CapabilityNotSupportedError
from synthorg.observability import get_logger

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from synthorg.core.types import NotBlankStr
    from synthorg.hr.performance.tracker import PerformanceTracker

logger = get_logger(__name__)


def _capability(cap: str, detail: str) -> CapabilityNotSupportedError:
    return CapabilityNotSupportedError(cap, detail)


# ── QualityFacadeService ──────────────────────────────────────────


class QualityFacadeService:
    """Wraps :class:`PerformanceTracker`'s scoring surface."""

    def __init__(self, *, tracker: PerformanceTracker) -> None:
        self._tracker = cast("Any", tracker)

    async def get_summary(self) -> Mapping[str, object]:
        fn = getattr(self._tracker, "get_quality_summary", None)
        if callable(fn):
            result = fn()
            if hasattr(result, "__await__"):
                result = await result
            return dict(result)
        raise _capability(
            "quality_summary",
            "PerformanceTracker does not expose get_quality_summary",
        )

    async def get_agent_quality(
        self,
        agent_id: NotBlankStr,
    ) -> Mapping[str, object]:
        fn = getattr(self._tracker, "get_snapshot", None)
        if callable(fn):
            snapshot = fn(agent_id)
            dump_fn = getattr(snapshot, "model_dump", None)
            if callable(dump_fn):
                return cast("Mapping[str, object]", dump_fn(mode="json"))
            return dict(snapshot.__dict__) if snapshot else {}
        raise _capability(
            "quality_agent",
            "PerformanceTracker does not expose get_snapshot",
        )

    async def list_scores(
        self,
        *,
        agent_id: NotBlankStr | None = None,
    ) -> Sequence[object]:
        fn = getattr(self._tracker, "list_quality_scores", None)
        if callable(fn):
            result = fn(agent_id) if agent_id else fn()
            if hasattr(result, "__await__"):
                result = await result
            return tuple(result)
        return ()


# ── ReviewFacadeService ───────────────────────────────────────────


class _ReviewRecord:
    __slots__ = (
        "comments",
        "created_at",
        "id",
        "reviewer_id",
        "task_id",
        "updated_at",
        "verdict",
    )

    def __init__(
        self,
        *,
        id: UUID,  # noqa: A002
        task_id: str,
        reviewer_id: str,
        verdict: str,
        comments: str | None,
        created_at: datetime,
    ) -> None:
        self.id = id
        self.task_id = task_id
        self.reviewer_id = reviewer_id
        self.verdict = verdict
        self.comments = comments
        self.created_at = created_at
        self.updated_at = created_at

    def to_dict(self) -> dict[str, object]:
        return {
            "id": str(self.id),
            "task_id": self.task_id,
            "reviewer_id": self.reviewer_id,
            "verdict": self.verdict,
            "comments": self.comments,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class ReviewFacadeService:
    """In-process review-queue facade."""

    def __init__(self) -> None:
        self._reviews: dict[UUID, _ReviewRecord] = {}

    async def list_reviews(self) -> Sequence[_ReviewRecord]:
        return tuple(
            sorted(self._reviews.values(), key=lambda r: r.created_at, reverse=True),
        )

    async def get_review(self, review_id: NotBlankStr) -> _ReviewRecord | None:
        try:
            key = UUID(review_id)
        except ValueError:
            return None
        return self._reviews.get(key)

    async def create_review(
        self,
        *,
        task_id: NotBlankStr,
        reviewer_id: NotBlankStr,
        verdict: NotBlankStr,
        comments: str | None = None,
    ) -> _ReviewRecord:
        record = _ReviewRecord(
            id=uuid4(),
            task_id=task_id,
            reviewer_id=reviewer_id,
            verdict=verdict,
            comments=comments,
            created_at=datetime.now(UTC),
        )
        self._reviews[record.id] = record
        logger.info(
            "quality.review_created_via_mcp",
            review_id=str(record.id),
            task_id=task_id,
            verdict=verdict,
        )
        return record

    async def update_review(
        self,
        *,
        review_id: NotBlankStr,
        verdict: NotBlankStr | None = None,
        comments: str | None = None,
        actor_id: NotBlankStr,
    ) -> _ReviewRecord | None:
        try:
            key = UUID(review_id)
        except ValueError:
            return None
        record = self._reviews.get(key)
        if record is None:
            return None
        if verdict is not None:
            record.verdict = verdict
        if comments is not None:
            record.comments = comments
        record.updated_at = datetime.now(UTC)
        logger.info(
            "quality.review_updated_via_mcp",
            review_id=review_id,
            actor_id=actor_id,
        )
        return record


# ── EvaluationVersionService ─────────────────────────────────────


class EvaluationVersionService:
    """Evaluation-config version history facade.

    Wraps :class:`PersistenceBackend.evaluation_config_versions` when
    available; returns ``()`` / ``None`` otherwise.
    """

    def __init__(self, *, persistence: Any) -> None:
        self._persistence = cast("Any", persistence)

    async def list_versions(self) -> Sequence[object]:
        repo = getattr(self._persistence, "evaluation_config_versions", None)
        if repo is None:
            return ()
        fn = getattr(repo, "list_versions", None)
        if not callable(fn):
            return ()
        return tuple(await fn())

    async def get_version(
        self,
        version_id: NotBlankStr,
    ) -> object | None:
        repo = getattr(self._persistence, "evaluation_config_versions", None)
        if repo is None:
            return None
        fn = getattr(repo, "get_version", None)
        if not callable(fn):
            return None
        return cast("object | None", await fn(version_id))


__all__ = [
    "EvaluationVersionService",
    "QualityFacadeService",
    "ReviewFacadeService",
]
