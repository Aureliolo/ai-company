"""Coordination metrics for multi-agent system tuning.

Pure computation functions for five coordination metrics defined in
DESIGN_SPEC Section 10.3: efficiency, overhead, error amplification,
message density, and redundancy rate.
"""

import statistics
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from collections.abc import Sequence


class CoordinationEfficiency(BaseModel):
    """Coordination efficiency: success rate adjusted for turn overhead.

    ``Ec = success_rate / (turns_mas / turns_sas)``

    Attributes:
        value: Computed efficiency (higher is better).
        success_rate: Multi-agent task success rate.
        turns_mas: Average turns for multi-agent tasks.
        turns_sas: Average turns for single-agent tasks.
    """

    model_config = ConfigDict(frozen=True)

    value: float = Field(description="Coordination efficiency")
    success_rate: float = Field(description="Multi-agent success rate")
    turns_mas: float = Field(description="Avg turns (multi-agent)")
    turns_sas: float = Field(description="Avg turns (single-agent)")


class CoordinationOverhead(BaseModel):
    """Coordination overhead: percentage of extra turns for multi-agent.

    ``O% = (turns_mas - turns_sas) / turns_sas * 100``

    Attributes:
        value_percent: Overhead percentage.
        turns_mas: Average turns for multi-agent tasks.
        turns_sas: Average turns for single-agent tasks.
    """

    model_config = ConfigDict(frozen=True)

    value_percent: float = Field(description="Overhead percentage")
    turns_mas: float = Field(description="Avg turns (multi-agent)")
    turns_sas: float = Field(description="Avg turns (single-agent)")


class ErrorAmplification(BaseModel):
    """Error amplification: ratio of multi-agent to single-agent error rates.

    ``Ae = error_rate_mas / error_rate_sas``

    Attributes:
        value: Amplification factor (>1 means more errors in MAS).
        error_rate_mas: Multi-agent error rate.
        error_rate_sas: Single-agent error rate.
    """

    model_config = ConfigDict(frozen=True)

    value: float = Field(description="Error amplification factor")
    error_rate_mas: float = Field(description="Multi-agent error rate")
    error_rate_sas: float = Field(description="Single-agent error rate")


class MessageDensity(BaseModel):
    """Message density: inter-agent messages per reasoning turn.

    ``c = inter_agent_messages / reasoning_turns``

    Attributes:
        value: Messages per turn.
        inter_agent_messages: Number of inter-agent messages.
        reasoning_turns: Number of reasoning turns.
    """

    model_config = ConfigDict(frozen=True)

    value: float = Field(description="Messages per reasoning turn")
    inter_agent_messages: int = Field(
        ge=0,
        description="Inter-agent message count",
    )
    reasoning_turns: int = Field(
        gt=0,
        description="Reasoning turn count",
    )


class RedundancyRate(BaseModel):
    """Redundancy rate: mean similarity across output pairs.

    ``R = mean(similarities)``

    Attributes:
        value: Mean redundancy (0.0-1.0).
        sample_count: Number of similarity samples.
    """

    model_config = ConfigDict(frozen=True)

    value: float = Field(
        ge=0.0,
        le=1.0,
        description="Mean redundancy",
    )
    sample_count: int = Field(
        ge=0,
        description="Number of similarity samples",
    )


class CoordinationMetrics(BaseModel):
    """Container for all five coordination metrics.

    All fields are optional (``None`` when not collected).

    Attributes:
        efficiency: Coordination efficiency metric.
        overhead: Coordination overhead metric.
        error_amplification: Error amplification metric.
        message_density: Message density metric.
        redundancy_rate: Redundancy rate metric.
    """

    model_config = ConfigDict(frozen=True)

    efficiency: CoordinationEfficiency | None = Field(
        default=None,
        description="Coordination efficiency",
    )
    overhead: CoordinationOverhead | None = Field(
        default=None,
        description="Coordination overhead",
    )
    error_amplification: ErrorAmplification | None = Field(
        default=None,
        description="Error amplification",
    )
    message_density: MessageDensity | None = Field(
        default=None,
        description="Message density",
    )
    redundancy_rate: RedundancyRate | None = Field(
        default=None,
        description="Redundancy rate",
    )


# ── Pure computation functions ──────────────────────────────────────


def compute_efficiency(
    *,
    success_rate: float,
    turns_mas: float,
    turns_sas: float,
) -> CoordinationEfficiency:
    """Compute coordination efficiency.

    Args:
        success_rate: Multi-agent task success rate (0.0-1.0).
        turns_mas: Average turns for multi-agent tasks.
        turns_sas: Average turns for single-agent tasks.

    Returns:
        Coordination efficiency model.

    Raises:
        ValueError: If ``turns_sas`` is zero.
    """
    if turns_sas == 0:
        msg = "turns_sas must be positive (cannot divide by zero)"
        raise ValueError(msg)
    value = success_rate / (turns_mas / turns_sas)
    return CoordinationEfficiency(
        value=value,
        success_rate=success_rate,
        turns_mas=turns_mas,
        turns_sas=turns_sas,
    )


def compute_overhead(
    *,
    turns_mas: float,
    turns_sas: float,
) -> CoordinationOverhead:
    """Compute coordination overhead percentage.

    Args:
        turns_mas: Average turns for multi-agent tasks.
        turns_sas: Average turns for single-agent tasks.

    Returns:
        Coordination overhead model.

    Raises:
        ValueError: If ``turns_sas`` is zero.
    """
    if turns_sas == 0:
        msg = "turns_sas must be positive (cannot divide by zero)"
        raise ValueError(msg)
    value_percent = (turns_mas - turns_sas) / turns_sas * 100
    return CoordinationOverhead(
        value_percent=value_percent,
        turns_mas=turns_mas,
        turns_sas=turns_sas,
    )


def compute_error_amplification(
    *,
    error_rate_mas: float,
    error_rate_sas: float,
) -> ErrorAmplification:
    """Compute error amplification factor.

    Args:
        error_rate_mas: Multi-agent error rate.
        error_rate_sas: Single-agent error rate.

    Returns:
        Error amplification model.

    Raises:
        ValueError: If ``error_rate_sas`` is zero.
    """
    if error_rate_sas == 0:
        msg = "error_rate_sas must be positive (cannot divide by zero)"
        raise ValueError(msg)
    value = error_rate_mas / error_rate_sas
    return ErrorAmplification(
        value=value,
        error_rate_mas=error_rate_mas,
        error_rate_sas=error_rate_sas,
    )


def compute_message_density(
    *,
    inter_agent_messages: int,
    reasoning_turns: int,
) -> MessageDensity:
    """Compute message density.

    Args:
        inter_agent_messages: Number of inter-agent messages.
        reasoning_turns: Number of reasoning turns.

    Returns:
        Message density model.

    Raises:
        ValueError: If ``reasoning_turns`` is zero.
    """
    if reasoning_turns == 0:
        msg = "reasoning_turns must be positive (cannot divide by zero)"
        raise ValueError(msg)
    value = inter_agent_messages / reasoning_turns
    return MessageDensity(
        value=value,
        inter_agent_messages=inter_agent_messages,
        reasoning_turns=reasoning_turns,
    )


def compute_redundancy_rate(
    *,
    similarities: Sequence[float],
) -> RedundancyRate:
    """Compute redundancy rate from pairwise similarity scores.

    Args:
        similarities: Sequence of similarity scores (each 0.0-1.0).

    Returns:
        Redundancy rate model.

    Raises:
        ValueError: If any similarity value is outside [0, 1].
        ValueError: If the sequence is empty.
    """
    if not similarities:
        msg = "similarities must not be empty"
        raise ValueError(msg)
    for val in similarities:
        if not 0.0 <= val <= 1.0:
            msg = f"Similarity value {val} is outside [0, 1]"
            raise ValueError(msg)
    value = statistics.mean(similarities)
    return RedundancyRate(
        value=value,
        sample_count=len(similarities),
    )
