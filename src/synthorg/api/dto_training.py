"""Request/response DTOs for the training API endpoints."""

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.hr.training.models import TrainingPlanStatus  # noqa: TC001


class CreateTrainingPlanRequest(BaseModel):
    """Request body for creating a training plan."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    override_sources: tuple[str, ...] = Field(
        default=(),
        description="Explicit source agent IDs",
    )
    content_types: tuple[str, ...] | None = Field(
        default=None,
        description="Enable specific content types",
    )
    custom_caps: dict[str, int] | None = Field(
        default=None,
        description="Per-content-type cap overrides",
    )
    skip_training: bool = Field(
        default=False,
        description="Skip training entirely",
    )
    require_review: bool = Field(
        default=True,
        description="Require human review",
    )


class UpdateTrainingOverridesRequest(BaseModel):
    """Request body for updating training plan overrides."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    override_sources: tuple[str, ...] | None = Field(
        default=None,
        description="Updated source agent IDs",
    )
    custom_caps: dict[str, int] | None = Field(
        default=None,
        description="Updated per-content-type caps",
    )


class TrainingPlanResponse(BaseModel):
    """Response body for a training plan."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    id: NotBlankStr
    new_agent_id: NotBlankStr
    new_agent_role: NotBlankStr
    source_selector_type: NotBlankStr
    enabled_content_types: tuple[str, ...]
    curation_strategy_type: NotBlankStr
    volume_caps: tuple[tuple[str, int], ...]
    override_sources: tuple[str, ...]
    skip_training: bool
    require_review: bool
    status: TrainingPlanStatus
    created_at: AwareDatetime
    executed_at: AwareDatetime | None = None


class TrainingResultResponse(BaseModel):
    """Response body for a training result."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    id: NotBlankStr
    plan_id: NotBlankStr
    new_agent_id: NotBlankStr
    source_agents_used: tuple[str, ...]
    items_extracted: tuple[tuple[str, int], ...]
    items_after_curation: tuple[tuple[str, int], ...]
    items_after_guards: tuple[tuple[str, int], ...]
    items_stored: tuple[tuple[str, int], ...]
    approval_item_id: str | None = None
    errors: tuple[str, ...]
    started_at: AwareDatetime
    completed_at: AwareDatetime
