"""Supersession rule classification for procedural memory proposals.

Compares a candidate proposal against an existing org-scope entry
to determine if the candidate supersedes, conflicts with, or
partially overlaps the existing one.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.memory.procedural.models import ProceduralMemoryProposal  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.skill_evolver import (
    SUPERSESSION_CONFLICT,
    SUPERSESSION_FULL,
    SUPERSESSION_PARTIAL,
)

logger = get_logger(__name__)

# Minimum word overlap ratio to consider conditions as overlapping.
_OVERLAP_THRESHOLD: float = 0.5

# Minimum word overlap ratio for conditions to be a "superset".
_SUPERSET_THRESHOLD: float = 0.8


class SupersessionVerdict(StrEnum):
    """Classification of how one proposal relates to another.

    Members:
        FULL: Candidate fully supersedes existing.
        PARTIAL: Conditions overlap but neither is a superset.
        CONFLICT: Same condition, contradictory actions.
    """

    FULL = "full"
    PARTIAL = "partial"
    CONFLICT = "conflict"


class SupersessionResult(BaseModel):
    """Result of supersession evaluation between two proposals.

    Attributes:
        verdict: Classification of the relationship.
        candidate_id: ID of the new proposal.
        existing_id: ID of the existing proposal.
        reason: Human-readable explanation.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    verdict: SupersessionVerdict = Field(
        description="Supersession classification",
    )
    candidate_id: NotBlankStr = Field(
        description="ID of the candidate proposal",
    )
    existing_id: NotBlankStr = Field(
        description="ID of the existing proposal",
    )
    reason: NotBlankStr = Field(
        description="Explanation of the verdict",
    )


_MIN_TOKEN_LENGTH: int = 2


def _tokenize(text: str) -> set[str]:
    """Extract lowercase word tokens from text."""
    return {w.lower() for w in text.split() if len(w) > _MIN_TOKEN_LENGTH}


def _overlap_ratio(a: set[str], b: set[str]) -> float:
    """Fraction of b's tokens present in a (0.0-1.0)."""
    if not b:
        return 1.0
    return len(a & b) / len(b)


def _similarity(a: set[str], b: set[str]) -> float:
    """Jaccard similarity between two token sets."""
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def evaluate_supersession(
    candidate: ProceduralMemoryProposal,
    existing: ProceduralMemoryProposal,
    candidate_id: NotBlankStr,
    existing_id: NotBlankStr,
) -> SupersessionResult:
    """Classify the relationship between candidate and existing.

    Rules (evaluated in this order):
        - **CONFLICT**: high condition overlap but low action
          similarity (contradictory approaches).
        - **FULL**: candidate.condition is a superset of
          existing.condition, actions are compatible, AND
          candidate.confidence > existing.confidence.
        - **PARTIAL**: everything else (insufficient overlap,
          confidence not strictly higher, or empty conditions).

    Args:
        candidate: The new proposal.
        existing: The existing org-scope proposal.
        candidate_id: ID of the candidate.
        existing_id: ID of the existing entry.

    Returns:
        Classified ``SupersessionResult``.
    """
    cond_candidate = _tokenize(candidate.condition)
    cond_existing = _tokenize(existing.condition)

    # Short-circuit when either condition yields no tokens --
    # ratios are meaningless with empty token sets.
    if not cond_candidate or not cond_existing:
        logger.debug(
            SUPERSESSION_PARTIAL,
            candidate_id=candidate_id,
            existing_id=existing_id,
            condition_similarity="n/a",
            action_similarity="n/a",
        )
        return SupersessionResult(
            verdict=SupersessionVerdict.PARTIAL,
            candidate_id=candidate_id,
            existing_id=existing_id,
            reason="Insufficient condition tokens for comparison",
        )

    act_candidate = _tokenize(candidate.action)
    act_existing = _tokenize(existing.action)

    # How much of existing's condition is covered by candidate?
    condition_coverage = _overlap_ratio(cond_candidate, cond_existing)
    condition_similarity = _similarity(cond_candidate, cond_existing)
    action_similarity = _similarity(act_candidate, act_existing)

    # CONFLICT: high condition overlap + low action similarity
    # (checked BEFORE FULL to prevent contradictory supersession)
    if (
        condition_similarity >= _OVERLAP_THRESHOLD
        and action_similarity < _OVERLAP_THRESHOLD
    ):
        logger.info(
            SUPERSESSION_CONFLICT,
            candidate_id=candidate_id,
            existing_id=existing_id,
            condition_similarity=f"{condition_similarity:.0%}",
            action_similarity=f"{action_similarity:.0%}",
        )
        return SupersessionResult(
            verdict=SupersessionVerdict.CONFLICT,
            candidate_id=candidate_id,
            existing_id=existing_id,
            reason=(
                f"Condition similarity {condition_similarity:.0%} "
                f"but action similarity only "
                f"{action_similarity:.0%} "
                f"(contradictory approaches)"
            ),
        )

    # FULL: condition superset + compatible actions + higher confidence
    if (
        condition_coverage >= _SUPERSET_THRESHOLD
        and action_similarity >= _OVERLAP_THRESHOLD
        and candidate.confidence > existing.confidence
    ):
        logger.info(
            SUPERSESSION_FULL,
            candidate_id=candidate_id,
            existing_id=existing_id,
            condition_coverage=f"{condition_coverage:.0%}",
        )
        return SupersessionResult(
            verdict=SupersessionVerdict.FULL,
            candidate_id=candidate_id,
            existing_id=existing_id,
            reason=(
                f"Candidate covers {condition_coverage:.0%} of "
                f"existing condition with higher confidence "
                f"({candidate.confidence:.2f} > "
                f"{existing.confidence:.2f})"
            ),
        )

    # PARTIAL: everything else
    logger.debug(
        SUPERSESSION_PARTIAL,
        candidate_id=candidate_id,
        existing_id=existing_id,
        condition_similarity=f"{condition_similarity:.0%}",
        action_similarity=f"{action_similarity:.0%}",
    )
    return SupersessionResult(
        verdict=SupersessionVerdict.PARTIAL,
        candidate_id=candidate_id,
        existing_id=existing_id,
        reason=(
            f"Partial overlap: condition similarity "
            f"{condition_similarity:.0%}, action similarity "
            f"{action_similarity:.0%}"
        ),
    )
