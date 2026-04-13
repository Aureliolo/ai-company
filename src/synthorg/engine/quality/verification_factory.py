"""Factory functions for verification decomposers and graders."""

from types import MappingProxyType

from synthorg.engine.quality.decomposer_protocol import (
    CriteriaDecomposer,  # noqa: TC001
)
from synthorg.engine.quality.decomposers.identity import (
    IdentityCriteriaDecomposer,
)
from synthorg.engine.quality.decomposers.llm import LLMCriteriaDecomposer
from synthorg.engine.quality.grader_protocol import RubricGrader  # noqa: TC001
from synthorg.engine.quality.graders.heuristic import HeuristicRubricGrader
from synthorg.engine.quality.graders.llm import LLMRubricGrader
from synthorg.engine.quality.verification_config import (
    DecomposerVariant,
    GraderVariant,
    VerificationConfig,
)

_DECOMPOSER_FACTORIES: MappingProxyType[DecomposerVariant, type[CriteriaDecomposer]] = (
    MappingProxyType(
        {
            DecomposerVariant.LLM: LLMCriteriaDecomposer,
            DecomposerVariant.IDENTITY: IdentityCriteriaDecomposer,
        }
    )
)

_GRADER_FACTORIES: MappingProxyType[GraderVariant, type[RubricGrader]] = (
    MappingProxyType(
        {
            GraderVariant.LLM: LLMRubricGrader,
            GraderVariant.HEURISTIC: HeuristicRubricGrader,
        }
    )
)


def build_decomposer(config: VerificationConfig) -> CriteriaDecomposer:
    """Build a decomposer from config.

    Args:
        config: Verification configuration.

    Returns:
        A criteria decomposer instance.

    Raises:
        ValueError: If the variant is unknown.
    """
    factory = _DECOMPOSER_FACTORIES.get(config.decomposer)
    if factory is None:
        valid = sorted(v.value for v in DecomposerVariant)
        msg = f"Unknown decomposer variant {config.decomposer!r}, valid: {valid}"
        raise ValueError(msg)
    return factory()


def build_grader(config: VerificationConfig) -> RubricGrader:
    """Build a grader from config.

    Args:
        config: Verification configuration.

    Returns:
        A rubric grader instance.

    Raises:
        ValueError: If the variant is unknown.
    """
    factory = _GRADER_FACTORIES.get(config.grader)
    if factory is None:
        valid = sorted(v.value for v in GraderVariant)
        msg = f"Unknown grader variant {config.grader!r}, valid: {valid}"
        raise ValueError(msg)
    return factory()
