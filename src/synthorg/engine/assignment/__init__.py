"""Task assignment engine.

Assigns tasks to agents using pluggable strategies: manual
designation, role-based scoring, load-balanced selection,
cost-optimized selection, hierarchical delegation, or auction.
"""

from synthorg.engine.assignment._shared import (
    STRATEGY_NAME_AUCTION,
    STRATEGY_NAME_COST_OPTIMIZED,
    STRATEGY_NAME_HIERARCHICAL,
    STRATEGY_NAME_LOAD_BALANCED,
    STRATEGY_NAME_MANUAL,
    STRATEGY_NAME_ROLE_BASED,
)
from synthorg.engine.assignment.auction import AuctionAssignmentStrategy
from synthorg.engine.assignment.cost_optimized import CostOptimizedAssignmentStrategy
from synthorg.engine.assignment.hierarchical import HierarchicalAssignmentStrategy
from synthorg.engine.assignment.load_balanced import LoadBalancedAssignmentStrategy
from synthorg.engine.assignment.manual import ManualAssignmentStrategy
from synthorg.engine.assignment.models import (
    AgentWorkload,
    AssignmentCandidate,
    AssignmentRequest,
    AssignmentResult,
)
from synthorg.engine.assignment.protocol import TaskAssignmentStrategy
from synthorg.engine.assignment.registry import (
    STRATEGY_MAP,
    build_strategy_map,
)
from synthorg.engine.assignment.role_based import RoleBasedAssignmentStrategy
from synthorg.engine.assignment.service import TaskAssignmentService

__all__ = [
    "STRATEGY_MAP",
    "STRATEGY_NAME_AUCTION",
    "STRATEGY_NAME_COST_OPTIMIZED",
    "STRATEGY_NAME_HIERARCHICAL",
    "STRATEGY_NAME_LOAD_BALANCED",
    "STRATEGY_NAME_MANUAL",
    "STRATEGY_NAME_ROLE_BASED",
    "AgentWorkload",
    "AssignmentCandidate",
    "AssignmentRequest",
    "AssignmentResult",
    "AuctionAssignmentStrategy",
    "CostOptimizedAssignmentStrategy",
    "HierarchicalAssignmentStrategy",
    "LoadBalancedAssignmentStrategy",
    "ManualAssignmentStrategy",
    "RoleBasedAssignmentStrategy",
    "TaskAssignmentService",
    "TaskAssignmentStrategy",
    "build_strategy_map",
]
