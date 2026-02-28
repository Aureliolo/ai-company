"""Artifact domain models for task outputs and expected deliverables."""

from datetime import datetime  # noqa: TC003 — required at runtime by Pydantic
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ai_company.core.enums import (
    ArtifactType,  # noqa: TC001 — required at runtime by Pydantic
)


class ExpectedArtifact(BaseModel):
    """An artifact expected to be produced by a task.

    Used within task definitions to declare what outputs are expected.

    Attributes:
        type: The type of artifact expected.
        path: File or directory path where the artifact should be produced.
    """

    model_config = ConfigDict(frozen=True)

    type: ArtifactType = Field(description="Type of artifact expected")
    path: str = Field(
        min_length=1,
        description="File or directory path for the artifact",
    )

    @model_validator(mode="after")
    def _validate_path_not_blank(self) -> Self:
        """Ensure path is not whitespace-only."""
        if not self.path.strip():
            msg = "path must not be whitespace-only"
            raise ValueError(msg)
        return self


class Artifact(BaseModel):
    """A concrete artifact produced by an agent during task execution.

    Artifacts track the actual work output, linking it back to the
    originating task and the agent who produced it.

    Attributes:
        id: Unique artifact identifier (e.g. ``"artifact-abc123"``).
        type: The type of artifact.
        path: File or directory path of the artifact.
        task_id: ID of the task that produced this artifact.
        created_by: Agent ID of the creator.
        description: Human-readable description of the artifact.
        created_at: Timestamp when the artifact was created.
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1, description="Unique artifact identifier")
    type: ArtifactType = Field(description="Artifact type")
    path: str = Field(
        min_length=1,
        description="File or directory path of the artifact",
    )
    task_id: str = Field(
        min_length=1,
        description="ID of the task that produced this artifact",
    )
    created_by: str = Field(
        min_length=1,
        description="Agent ID of the creator",
    )
    description: str = Field(
        default="",
        description="Human-readable description of the artifact",
    )
    created_at: datetime | None = Field(
        default=None,
        description="Timestamp when the artifact was created",
    )

    @model_validator(mode="after")
    def _validate_non_blank_strings(self) -> Self:
        """Ensure string identifier fields are not whitespace-only."""
        for field_name in ("id", "path", "task_id", "created_by"):
            if not getattr(self, field_name).strip():
                msg = f"{field_name} must not be whitespace-only"
                raise ValueError(msg)
        return self
