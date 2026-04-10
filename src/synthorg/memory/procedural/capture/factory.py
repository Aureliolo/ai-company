"""Factory for building capture strategies.

Constructs the appropriate capture strategy based on configuration,
wiring proposers and backends as needed.
"""

from synthorg.memory.procedural.capture.config import CaptureConfig  # noqa: TC001
from synthorg.memory.procedural.capture.failure_capture import FailureCaptureStrategy
from synthorg.memory.procedural.capture.hybrid_capture import HybridCaptureStrategy
from synthorg.memory.procedural.capture.protocol import CaptureStrategy  # noqa: TC001
from synthorg.memory.procedural.capture.success_capture import SuccessCaptureStrategy
from synthorg.memory.procedural.models import ProceduralMemoryConfig  # noqa: TC001
from synthorg.memory.procedural.proposer import ProceduralMemoryProposer  # noqa: TC001
from synthorg.memory.procedural.success_proposer import (
    SuccessMemoryProposer,  # noqa: TC001
)
from synthorg.observability import get_logger

logger = get_logger(__name__)


def build_capture_strategy(
    config: CaptureConfig,
    *,
    failure_proposer: ProceduralMemoryProposer,
    success_proposer: SuccessMemoryProposer,
    procedural_config: ProceduralMemoryConfig,
) -> CaptureStrategy:
    """Build a capture strategy based on configuration.

    Routes to the appropriate strategy factory based on the configured
    type. All strategies require both proposers to be pre-constructed.

    Args:
        config: Capture strategy configuration.
        failure_proposer: ProceduralMemoryProposer for failure analysis.
        success_proposer: SuccessMemoryProposer for success analysis.
        procedural_config: ProceduralMemoryConfig for general settings.

    Returns:
        A CaptureStrategy instance matching the configured type.

    Raises:
        ValueError: If config.type is not "failure", "success", or "hybrid".
    """
    strategy_type = config.type.lower()

    if strategy_type == "failure":
        logger.debug("capture_strategy.build", type="failure")
        return FailureCaptureStrategy(
            proposer=failure_proposer,
            config=procedural_config,
        )

    if strategy_type == "success":
        logger.debug("capture_strategy.build", type="success")
        return SuccessCaptureStrategy(
            proposer=success_proposer,
            config=procedural_config,
            min_quality_score=config.min_quality_score,
        )

    if strategy_type == "hybrid":
        logger.debug("capture_strategy.build", type="hybrid")
        failure_strategy = FailureCaptureStrategy(
            proposer=failure_proposer,
            config=procedural_config,
        )
        success_strategy = SuccessCaptureStrategy(
            proposer=success_proposer,
            config=procedural_config,
            min_quality_score=config.min_quality_score,
        )
        return HybridCaptureStrategy(
            failure_strategy=failure_strategy,
            success_strategy=success_strategy,
        )

    msg = (
        f"Unknown capture strategy type: {strategy_type}. "
        'Must be "failure", "success", or "hybrid".'
    )
    logger.warning("capture_strategy.unknown_type", type=strategy_type)
    raise ValueError(msg)
