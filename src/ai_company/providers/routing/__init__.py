"""Model routing engine — strategy-based LLM model selection.

Exports the router, resolver, domain models, errors, strategies,
and the ``RoutingStrategy`` protocol.
"""

from .errors import (
    ModelResolutionError,
    NoAvailableModelError,
    RoutingError,
    UnknownStrategyError,
)
from .models import ResolvedModel, RoutingDecision, RoutingRequest
from .resolver import ModelResolver
from .router import ModelRouter
from .strategies import (
    CostAwareStrategy,
    ManualStrategy,
    RoleBasedStrategy,
    RoutingStrategy,
    SmartStrategy,
)

__all__ = [
    "CostAwareStrategy",
    "ManualStrategy",
    "ModelResolutionError",
    "ModelResolver",
    "ModelRouter",
    "NoAvailableModelError",
    "ResolvedModel",
    "RoleBasedStrategy",
    "RoutingDecision",
    "RoutingError",
    "RoutingRequest",
    "RoutingStrategy",
    "SmartStrategy",
    "UnknownStrategyError",
]
