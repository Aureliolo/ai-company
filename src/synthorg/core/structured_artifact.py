"""Base model for structured single-consumption artifacts."""

from datetime import datetime  # noqa: TC003

from pydantic import BaseModel, ConfigDict, Field


class StructuredArtifact(BaseModel):
    """Base for structured single-consumption artifacts.

    Subclasses:
    - HandoffArtifact (agent role transitions, R2 #1262)
    - EvidencePackage (HITL approval, R4 -- future)
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    created_at: datetime = Field(description="Artifact creation timestamp")
