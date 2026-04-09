"""Consensus velocity detection for trendslop mitigation.

Detects when a group of agents reaches consensus too quickly (premature
consensus, "trendslop"). Uses text similarity analysis to identify when
diverse positions are collapsing into unanimity, triggering mitigation
actions like devil's advocate or escalation.
"""

import difflib

from pydantic import BaseModel, ConfigDict, Field

from synthorg.engine.strategy.models import (  # noqa: TC001
    ConsensusAction,
    ConsensusVelocityConfig,
)
from synthorg.observability import get_logger

logger = get_logger(__name__)


class ConsensusVelocityResult(BaseModel):
    """Result of consensus velocity analysis.

    Attributes:
        detected: Whether premature consensus was detected.
        action: Action to take (None if not detected).
        mean_similarity: Mean pairwise text similarity (0.0-1.0).
        disagreement_count: Number of substantially different position pairs.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    detected: bool = Field(description="Whether premature consensus was detected")
    action: ConsensusAction | None = Field(
        default=None,
        description="Action to take (None if not detected)",
    )
    mean_similarity: float = Field(
        ge=0.0,
        le=1.0,
        description="Mean pairwise text similarity",
    )
    disagreement_count: int = Field(
        ge=0,
        description="Number of substantially different position pairs",
    )


_MIN_POSITION_PAIRS: int = 2
_SUBSTANTIAL_DIFF_THRESHOLD: float = 0.5


class ConsensusVelocityDetector:
    """Detect premature consensus using text similarity.

    Uses difflib.SequenceMatcher for pure-Python string similarity
    analysis. Detects consensus as "premature" when:
    - Mean pairwise similarity exceeds threshold, AND
    - Disagreement count falls below minimum threshold

    This catches situations where agents are using different words to
    express the same idea, or have converged too quickly on similar
    recommendations.
    """

    def __init__(self, *, min_disagreements: int = 2) -> None:
        """Initialize detector.

        Args:
            min_disagreements: Minimum number of substantially different
                position pairs to consider consensus as non-premature.
                Default is 2 (at least one pair of significantly different
                positions keeps consensus from being "too fast").
        """
        self._min_disagreements = min_disagreements

    def detect(
        self,
        positions: tuple[str, ...],
        config: ConsensusVelocityConfig,
    ) -> ConsensusVelocityResult:
        """Analyze positions for premature consensus.

        Args:
            positions: Text positions from agents (e.g., recommendations).
            config: Configuration including similarity threshold and action.

        Returns:
            ConsensusVelocityResult with detection status and metrics.
        """
        if len(positions) < _MIN_POSITION_PAIRS:
            return ConsensusVelocityResult(
                detected=False,
                mean_similarity=1.0,
                disagreement_count=0,
            )

        # Compute pairwise similarity across all position pairs
        similarities: list[float] = []
        disagreements = 0

        for i in range(len(positions)):
            for j in range(i + 1, len(positions)):
                # Use SequenceMatcher for pure-Python text similarity
                ratio = difflib.SequenceMatcher(
                    None, positions[i], positions[j]
                ).ratio()
                similarities.append(ratio)

                # Positions with < threshold are "substantially different"
                if ratio < _SUBSTANTIAL_DIFF_THRESHOLD:
                    disagreements += 1

        # Calculate mean similarity
        mean_sim = sum(similarities) / len(similarities)

        # Detect premature consensus: high similarity + few disagreements
        is_premature = (
            mean_sim > config.threshold and disagreements < self._min_disagreements
        )

        return ConsensusVelocityResult(
            detected=is_premature,
            action=config.action if is_premature else None,
            mean_similarity=round(mean_sim, 4),
            disagreement_count=disagreements,
        )
