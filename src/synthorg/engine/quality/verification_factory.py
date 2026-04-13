"""Factory functions for verification decomposers and graders."""

from types import MappingProxyType

from synthorg.engine.quality.decomposer_protocol import (
    CriteriaDecomposer,  # noqa: TC001
)
from synthorg.engine.quality.decomposers.identity import (
    IdentityCriteriaDecomposer,
)
from synthorg.engine.quality.grader_protocol import RubricGrader  # noqa: TC001
from synthorg.engine.quality.graders.heuristic import HeuristicRubricGrader
from synthorg.engine.quality.verification_config import (
    DecomposerVariant,
    GraderVariant,
    VerificationConfig,
)
from synthorg.observability import get_logger
from synthorg.observability.events.verification import (
    VERIFICATION_FACTORY_UNKNOWN_DECOMPOSER,
    VERIFICATION_FACTORY_UNKNOWN_GRADER,
)

logger = get_logger(__name__)

_DECOMPOSER_FACTORIES: MappingProxyType[DecomposerVariant, type[CriteriaDecomposer]] = (
    MappingProxyType(
        {
            DecomposerVariant.IDENTITY: IdentityCriteriaDecomposer,
        }
    )
)

_GRADER_FACTORIES: MappingProxyType[GraderVariant, type[RubricGrader]] = (
    MappingProxyType(
        {
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
        valid = sorted(v.value for v in _DECOMPOSER_FACTORIES)
        msg = f"Unknown decomposer variant {config.decomposer!r}, valid: {valid}"
        logger.error(
            VERIFICATION_FACTORY_UNKNOWN_DECOMPOSER,
            variant=str(config.decomposer),
            valid=valid,
        )
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
        valid = sorted(v.value for v in _GRADER_FACTORIES)
        msg = f"Unknown grader variant {config.grader!r}, valid: {valid}"
        logger.error(
            VERIFICATION_FACTORY_UNKNOWN_GRADER,
            variant=str(config.grader),
            valid=valid,
        )
        raise ValueError(msg)
    return factory()
