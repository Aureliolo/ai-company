"""Stagnation detection models.

Frozen Pydantic models for stagnation detection configuration,
verdicts, and results.  Used by the ``StagnationDetector`` protocol
and its implementations.
"""

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StagnationVerdict(StrEnum):
    """Verdict from a stagnation check."""

    NO_STAGNATION = "no_stagnation"
    INJECT_PROMPT = "inject_prompt"
    TERMINATE = "terminate"


class StagnationConfig(BaseModel):
    """Configuration for stagnation detection.

    Attributes:
        enabled: Whether stagnation detection is active.
        window_size: Number of recent tool-bearing turns to analyze.
        repetition_threshold: Fraction of duplicate fingerprints
            that triggers detection (0.0 = any duplicate, 1.0 = all).
        cycle_detection: Whether to detect repeating A->B->A->B patterns.
        max_corrections: Number of corrective prompt injections before
            terminating.  ``0`` means skip injection and terminate
            immediately.
        min_tool_turns: Minimum tool-bearing turns in the window
            before any check fires.
    """

    model_config = ConfigDict(frozen=True)

    enabled: bool = Field(
        default=True,
        description="Whether stagnation detection is active",
    )
    window_size: int = Field(
        default=5,
        ge=2,
        le=50,
        description="Number of recent tool-bearing turns to analyze",
    )
    repetition_threshold: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Fraction of duplicate fingerprints that triggers detection",
    )
    cycle_detection: bool = Field(
        default=True,
        description="Whether to detect repeating A->B->A->B patterns",
    )
    max_corrections: int = Field(
        default=1,
        ge=0,
        description="Number of corrective prompt injections before terminating",
    )
    min_tool_turns: int = Field(
        default=2,
        ge=1,
        description="Minimum tool-bearing turns before any check fires",
    )


class StagnationResult(BaseModel):
    """Result of a stagnation check.

    Attributes:
        verdict: What action to take.
        corrective_message: Corrective prompt to inject (required when
            verdict is ``INJECT_PROMPT``, ``None`` otherwise).
        repetition_ratio: Fraction of duplicate fingerprints in the
            analysis window.
        cycle_length: Length of detected repeating cycle, or ``None``.
        details: Forward-compatible metadata dict.
    """

    model_config = ConfigDict(frozen=True)

    verdict: StagnationVerdict = Field(
        description="What action to take",
    )
    corrective_message: str | None = Field(
        default=None,
        description="Corrective prompt to inject (INJECT_PROMPT only)",
    )
    repetition_ratio: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Fraction of duplicate fingerprints in the window",
    )
    cycle_length: int | None = Field(
        default=None,
        description="Length of detected repeating cycle",
    )
    details: dict[str, object] = Field(
        default_factory=dict,
        description="Forward-compatible metadata",
    )

    @model_validator(mode="after")
    def _validate_corrective_message(self) -> Self:
        if self.verdict == StagnationVerdict.INJECT_PROMPT:
            if self.corrective_message is None:
                msg = "corrective_message is required when verdict is INJECT_PROMPT"
                raise ValueError(msg)
        elif self.corrective_message is not None:
            msg = "corrective_message must be None when verdict is not INJECT_PROMPT"
            raise ValueError(msg)
        return self


NO_STAGNATION_RESULT = StagnationResult(
    verdict=StagnationVerdict.NO_STAGNATION,
)
"""Reusable result for the common no-stagnation case."""
