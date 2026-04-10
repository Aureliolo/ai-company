"""Factory for building propagation strategies from configuration."""

from typing import TYPE_CHECKING

from synthorg.memory.procedural.propagation.department_scoped import (
    DepartmentScopedPropagation,
)
from synthorg.memory.procedural.propagation.no_propagation import (
    NoPropagation,
)
from synthorg.memory.procedural.propagation.role_scoped import (
    RoleScopedPropagation,
)
from synthorg.observability import get_logger

if TYPE_CHECKING:
    from synthorg.memory.procedural.propagation.config import PropagationConfig
    from synthorg.memory.procedural.propagation.protocol import PropagationStrategy

logger = get_logger(__name__)


def build_propagation_strategy(
    config: PropagationConfig,
) -> PropagationStrategy:
    """Build a propagation strategy from configuration.

    Args:
        config: Propagation strategy configuration.

    Returns:
        Configured propagation strategy instance.

    Raises:
        ValueError: If strategy type is unknown.
    """
    if config.type == "none":
        return NoPropagation()
    if config.type == "role_scoped":
        return RoleScopedPropagation(max_targets=config.max_propagation_targets)
    if config.type == "department_scoped":
        return DepartmentScopedPropagation(
            max_targets=config.max_propagation_targets,
        )
    msg = f"Unknown propagation strategy type: {config.type}"  # type: ignore[unreachable]
    logger.warning("propagation_strategy.unknown_type", type=config.type)
    raise ValueError(msg)
