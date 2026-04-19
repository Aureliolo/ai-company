"""Multi-agent coordination engine.

Connects decomposition, routing, workspace isolation, and parallel
execution into an end-to-end pipeline orchestrated by topology-driven
dispatchers.
"""

from synthorg.engine.coordination.attribution import (
    AgentContribution,
    CoordinationResultWithAttribution,
    FailureAttribution,
    build_agent_contributions,
)
from synthorg.engine.coordination.centralized_dispatcher import CentralizedDispatcher
from synthorg.engine.coordination.config import CoordinationConfig
from synthorg.engine.coordination.context_dependent_dispatcher import (
    ContextDependentDispatcher,
)
from synthorg.engine.coordination.decentralized_dispatcher import (
    DecentralizedDispatcher,
)
from synthorg.engine.coordination.dispatcher_factory import select_dispatcher
from synthorg.engine.coordination.dispatcher_types import (
    DispatchResult,
    TopologyDispatcher,
)
from synthorg.engine.coordination.factory import build_coordinator
from synthorg.engine.coordination.group_builder import build_execution_waves
from synthorg.engine.coordination.models import (
    CoordinationContext,
    CoordinationPhaseResult,
    CoordinationResult,
    CoordinationWave,
)
from synthorg.engine.coordination.sas_dispatcher import SasDispatcher
from synthorg.engine.coordination.section_config import CoordinationSectionConfig
from synthorg.engine.coordination.service import MultiAgentCoordinator

__all__ = [
    "AgentContribution",
    "CentralizedDispatcher",
    "ContextDependentDispatcher",
    "CoordinationConfig",
    "CoordinationContext",
    "CoordinationPhaseResult",
    "CoordinationResult",
    "CoordinationResultWithAttribution",
    "CoordinationSectionConfig",
    "CoordinationWave",
    "DecentralizedDispatcher",
    "DispatchResult",
    "FailureAttribution",
    "MultiAgentCoordinator",
    "SasDispatcher",
    "TopologyDispatcher",
    "build_agent_contributions",
    "build_coordinator",
    "build_execution_waves",
    "select_dispatcher",
]
