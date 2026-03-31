"""Request/response DTOs for personality preset endpoints."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from synthorg.core.enums import (
    CollaborationPreference,
    CommunicationVerbosity,
    ConflictApproach,
    CreativityLevel,
    DecisionMakingStyle,
    RiskTolerance,
)
from synthorg.core.types import NotBlankStr  # noqa: TC001


class PresetSource(StrEnum):
    """Origin of a personality preset."""

    BUILTIN = "builtin"
    CUSTOM = "custom"


# ── Responses ────────────────────────────────────────────────


class PresetSummaryResponse(BaseModel):
    """Summary of a personality preset for list endpoints."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    name: NotBlankStr
    description: str = ""
    traits: tuple[str, ...] = ()
    source: PresetSource


class PresetDetailResponse(BaseModel):
    """Full personality preset definition."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    name: NotBlankStr
    source: PresetSource
    description: str = ""
    traits: tuple[str, ...] = ()
    communication_style: str = "neutral"
    risk_tolerance: RiskTolerance = RiskTolerance.MEDIUM
    creativity: CreativityLevel = CreativityLevel.MEDIUM
    openness: float = Field(default=0.5, ge=0.0, le=1.0)
    conscientiousness: float = Field(default=0.5, ge=0.0, le=1.0)
    extraversion: float = Field(default=0.5, ge=0.0, le=1.0)
    agreeableness: float = Field(default=0.5, ge=0.0, le=1.0)
    stress_response: float = Field(default=0.5, ge=0.0, le=1.0)
    decision_making: DecisionMakingStyle = DecisionMakingStyle.CONSULTATIVE
    collaboration: CollaborationPreference = CollaborationPreference.TEAM
    verbosity: CommunicationVerbosity = CommunicationVerbosity.BALANCED
    conflict_approach: ConflictApproach = ConflictApproach.COLLABORATE
    created_at: str | None = None
    updated_at: str | None = None


class PresetSchemaResponse(BaseModel):
    """JSON Schema for PersonalityConfig."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    schema_definition: dict[str, Any] = Field(
        alias="schema",
    )


# ── Requests ─────────────────────────────────────────────────


class CreatePresetRequest(BaseModel):
    """POST body for creating a custom personality preset."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    name: NotBlankStr = Field(max_length=100)
    traits: tuple[NotBlankStr, ...] = ()
    communication_style: NotBlankStr = Field(default="neutral", max_length=100)
    risk_tolerance: RiskTolerance = RiskTolerance.MEDIUM
    creativity: CreativityLevel = CreativityLevel.MEDIUM
    description: str = Field(default="", max_length=500)
    openness: float = Field(default=0.5, ge=0.0, le=1.0)
    conscientiousness: float = Field(default=0.5, ge=0.0, le=1.0)
    extraversion: float = Field(default=0.5, ge=0.0, le=1.0)
    agreeableness: float = Field(default=0.5, ge=0.0, le=1.0)
    stress_response: float = Field(default=0.5, ge=0.0, le=1.0)
    decision_making: DecisionMakingStyle = DecisionMakingStyle.CONSULTATIVE
    collaboration: CollaborationPreference = CollaborationPreference.TEAM
    verbosity: CommunicationVerbosity = CommunicationVerbosity.BALANCED
    conflict_approach: ConflictApproach = ConflictApproach.COLLABORATE

    def to_config_dict(self) -> dict[str, Any]:
        """Convert to a dict suitable for PersonalityConfig validation."""
        return self.model_dump(exclude={"name"})


class UpdatePresetRequest(BaseModel):
    """PUT body for updating a custom personality preset."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    traits: tuple[NotBlankStr, ...] = ()
    communication_style: NotBlankStr = Field(default="neutral", max_length=100)
    risk_tolerance: RiskTolerance = RiskTolerance.MEDIUM
    creativity: CreativityLevel = CreativityLevel.MEDIUM
    description: str = Field(default="", max_length=500)
    openness: float = Field(default=0.5, ge=0.0, le=1.0)
    conscientiousness: float = Field(default=0.5, ge=0.0, le=1.0)
    extraversion: float = Field(default=0.5, ge=0.0, le=1.0)
    agreeableness: float = Field(default=0.5, ge=0.0, le=1.0)
    stress_response: float = Field(default=0.5, ge=0.0, le=1.0)
    decision_making: DecisionMakingStyle = DecisionMakingStyle.CONSULTATIVE
    collaboration: CollaborationPreference = CollaborationPreference.TEAM
    verbosity: CommunicationVerbosity = CommunicationVerbosity.BALANCED
    conflict_approach: ConflictApproach = ConflictApproach.COLLABORATE

    def to_config_dict(self) -> dict[str, Any]:
        """Convert to a dict suitable for PersonalityConfig validation."""
        return self.model_dump()
