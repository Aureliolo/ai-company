"""Request and response models for the fine-tuning API."""

from pathlib import PurePosixPath, PureWindowsPath
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

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

    @model_validator(mode="after")
    def _reject_path_traversal(self) -> Self:
        """Reject parent-directory traversal and Windows paths."""
        for field_name in ("source_dir", "output_dir"):
            val = getattr(self, field_name)
            if val is None:
                continue
            parts = PureWindowsPath(val).parts + PurePosixPath(val).parts
            if ".." in parts:
                msg = f"{field_name} must not contain parent-directory traversal (..)"
                raise ValueError(msg)
            if "\\" in val or (
                len(val) >= 2 and val[1] == ":"  # noqa: PLR2004
            ):
                msg = (
                    f"{field_name} must be a POSIX path (no backslashes "
                    "or drive letters)"
                )
                raise ValueError(msg)
        return self


_ACTIVE_STAGES: frozenset[FineTuneStage] = frozenset(
    {
        FineTuneStage.GENERATING_DATA,
        FineTuneStage.MINING_NEGATIVES,
        FineTuneStage.TRAINING,
        FineTuneStage.DEPLOYING,
    }
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
    error: NotBlankStr | None = Field(
        default=None,
        description="Error message if failed",
    )

    @model_validator(mode="after")
    def _validate_stage_invariants(self) -> Self:
        """Enforce valid (stage, progress, error) combinations."""
        if self.stage == FineTuneStage.IDLE:
            if self.progress is not None:
                msg = "progress must be None when stage is IDLE"
                raise ValueError(msg)
            if self.error is not None:
                msg = "error must be None when stage is IDLE"
                raise ValueError(msg)
        if self.stage == FineTuneStage.FAILED and self.error is None:
            msg = "error is required when stage is FAILED"
            raise ValueError(msg)
        if self.stage in _ACTIVE_STAGES and self.error is not None:
            msg = "error must be None during active pipeline stages"
            raise ValueError(msg)
        return self
