"""Memory admin controller -- fine-tuning and embedder endpoints.

All endpoints require CEO or the internal SYSTEM role
(used by the CLI for admin operations).
"""

from litestar import Controller, get, post
from litestar.datastructures import State  # noqa: TC002
from pydantic import BaseModel, ConfigDict, Field

from synthorg.api.dto import ApiResponse
from synthorg.api.guards import HumanRole, require_roles
from synthorg.api.state import AppState  # noqa: TC001
from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.memory.embedding.fine_tune import FineTuneStage
from synthorg.memory.embedding.fine_tune_models import (
    FineTuneRequest,
    FineTuneStatus,
)
from synthorg.observability import get_logger
from synthorg.observability.events.memory import (
    MEMORY_EMBEDDER_SETTINGS_READ_FAILED,
    MEMORY_FINE_TUNE_REQUESTED,
)

logger = get_logger(__name__)


class ActiveEmbedderResponse(BaseModel):
    """Active embedder configuration read from settings."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    provider: NotBlankStr | None = Field(
        default=None,
        description="Embedding provider name",
    )
    model: NotBlankStr | None = Field(
        default=None,
        description="Embedding model identifier",
    )
    dims: int | None = Field(
        default=None,
        ge=1,
        description="Embedding vector dimensions",
    )


class MemoryAdminController(Controller):
    """Admin endpoints for memory management.

    Provides fine-tuning pipeline control and embedder configuration
    queries.  All endpoints require CEO or SYSTEM role.
    """

    path = "/admin/memory"
    tags = ("admin", "memory")
    guards = [require_roles(HumanRole.CEO, HumanRole.SYSTEM)]  # noqa: RUF012

    @post("/fine-tune")
    async def start_fine_tune(
        self,
        state: State,  # noqa: ARG002
        data: FineTuneRequest,
    ) -> ApiResponse[FineTuneStatus]:
        """Trigger a fine-tuning pipeline run.

        Args:
            state: Application state.
            data: Fine-tuning request parameters.

        Returns:
            Current pipeline status.
        """
        logger.info(
            MEMORY_FINE_TUNE_REQUESTED,
            source_dir=data.source_dir,
            base_model=data.base_model,
        )
        # Pipeline stages are not yet implemented -- return status
        # indicating the pipeline is idle with a descriptive error.
        # See issue #1001 for the implementation roadmap.
        return ApiResponse(
            data=FineTuneStatus(
                stage=FineTuneStage.FAILED,
                error=(
                    "Fine-tuning pipeline stages are not yet "
                    "implemented. Install synthorg[fine-tune] "
                    "and check back in a future release."
                ),
            ),
        )

    @get("/fine-tune/status")
    async def get_fine_tune_status(
        self,
        state: State,  # noqa: ARG002
    ) -> ApiResponse[FineTuneStatus]:
        """Get the current fine-tuning pipeline status.

        Args:
            state: Application state.

        Returns:
            Current pipeline status.
        """
        return ApiResponse(
            data=FineTuneStatus(stage=FineTuneStage.IDLE),
        )

    @get("/embedder")
    async def get_active_embedder(
        self,
        state: State,
    ) -> ApiResponse[ActiveEmbedderResponse]:
        """Get the active embedder configuration.

        Args:
            state: Application state.

        Returns:
            Active embedder provider, model, and dims.
        """
        app_state: AppState = state.app_state
        result = ActiveEmbedderResponse()
        if app_state.has_settings_service:
            svc = app_state.settings_service
            try:
                provider_sv = await svc.get("memory", "embedder_provider")
                model_sv = await svc.get("memory", "embedder_model")
                dims_sv = await svc.get("memory", "embedder_dims")
                dims_value: int | None = None
                if dims_sv.value:
                    try:
                        dims_value = int(dims_sv.value)
                    except ValueError, TypeError:
                        logger.warning(
                            MEMORY_EMBEDDER_SETTINGS_READ_FAILED,
                            setting="embedder_dims",
                            value=dims_sv.value,
                            reason="invalid integer value",
                        )
                result = ActiveEmbedderResponse(
                    provider=provider_sv.value or None,
                    model=model_sv.value or None,
                    dims=dims_value,
                )
            except MemoryError, RecursionError:
                raise
            except Exception:
                logger.warning(
                    MEMORY_EMBEDDER_SETTINGS_READ_FAILED,
                    exc_info=True,
                )
        return ApiResponse(data=result)
