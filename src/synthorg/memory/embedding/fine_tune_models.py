"""Request and response models for the fine-tuning API."""

from pydantic import BaseModel, ConfigDict, Field

from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.memory.embedding.fine_tune import FineTuneStage


class FineTuneRequest(BaseModel):
    """Request to start a fine-tuning pipeline run.

    Attributes:
        source_dir: Directory containing org documents for training.
        base_model: Base embedding model to fine-tune (``None`` = use
            current active model).
        output_dir: Directory to save checkpoints (``None`` = default).
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    source_dir: NotBlankStr = Field(
        description="Directory containing org documents",
    )
    base_model: NotBlankStr | None = Field(
        default=None,
        description="Base model to fine-tune (None = active model)",
    )
    output_dir: NotBlankStr | None = Field(
        default=None,
        description="Checkpoint output directory (None = default)",
    )


class FineTuneStatus(BaseModel):
    """Status of the fine-tuning pipeline.

    Attributes:
        stage: Current pipeline stage.
        progress: Progress fraction (0.0-1.0), ``None`` when idle.
        error: Error message if the pipeline failed.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    stage: FineTuneStage = Field(
        default=FineTuneStage.IDLE,
        description="Current pipeline stage",
    )
    progress: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Progress fraction (0.0-1.0)",
    )
    error: str | None = Field(
        default=None,
        description="Error message if failed",
    )
