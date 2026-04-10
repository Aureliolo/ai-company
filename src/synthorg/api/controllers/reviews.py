"""Read-only review pipeline endpoints at /reviews."""

from litestar import Controller, get
from litestar.datastructures import State  # noqa: TC002

from synthorg.api.dto import ApiResponse
from synthorg.api.errors import NotFoundError, ServiceUnavailableError
from synthorg.api.guards import require_read_access
from synthorg.api.state import AppState  # noqa: TC001
from synthorg.engine.review.models import PipelineResult  # noqa: TC001
from synthorg.observability import get_logger

logger = get_logger(__name__)


class ReviewController(Controller):
    """Review pipeline visibility endpoints."""

    path = "/reviews"
    tags = ("reviews",)
    guards = [require_read_access]  # noqa: RUF012

    @get("/{task_id:str}/pipeline")
    async def get_pipeline(
        self,
        state: State,
        task_id: str,
    ) -> ApiResponse[PipelineResult]:
        """Run the configured review pipeline against a task.

        The pipeline is fetched from ``AppState`` and invoked
        synchronously so the caller immediately sees the per-stage
        breakdown. Falls back to ``NotFoundError`` if the task
        cannot be resolved and ``ServiceUnavailableError`` if no
        pipeline is configured.
        """
        app_state: AppState = state.app_state
        sim_state = app_state.client_simulation_state
        pipeline = sim_state.review_pipeline
        if pipeline is None:
            msg = "Review pipeline not configured"
            raise ServiceUnavailableError(msg)
        try:
            task = await app_state.task_engine.get_task(task_id)
        except Exception as exc:
            logger.warning("review.task_lookup_failed", task_id=task_id)
            msg = f"Task {task_id!r} not found"
            raise NotFoundError(msg) from exc
        if task is None:
            msg = f"Task {task_id!r} not found"
            raise NotFoundError(msg)
        result = await pipeline.run(task)
        return ApiResponse(data=result)
