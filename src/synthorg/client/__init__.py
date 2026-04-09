"""Client simulation module for SynthOrg.

Provides the contracts (models, protocols, configs) for simulating
external clients that submit requirements and review deliverables.
"""

from synthorg.client.config import (
    ClientPoolConfig,
    ClientSimulationConfig,
    ContinuousModeConfig,
    FeedbackConfig,
    RequirementGeneratorConfig,
    SimulationRunnerConfig,
)
from synthorg.client.models import (
    ClientFeedback,
    ClientProfile,
    ClientRequest,
    GenerationContext,
    PoolConstraints,
    RequestStatus,
    ReviewContext,
    SimulationConfig,
    SimulationMetrics,
    TaskRequirement,
    validate_request_transition,
)
from synthorg.client.protocols import (
    ClientInterface,
    ClientPoolStrategy,
    EntryPointStrategy,
    FeedbackStrategy,
    ReportStrategy,
    RequirementGenerator,
)

__all__ = [
    "ClientFeedback",
    "ClientInterface",
    "ClientPoolConfig",
    "ClientPoolStrategy",
    "ClientProfile",
    "ClientRequest",
    "ClientSimulationConfig",
    "ContinuousModeConfig",
    "EntryPointStrategy",
    "FeedbackConfig",
    "FeedbackStrategy",
    "GenerationContext",
    "PoolConstraints",
    "ReportStrategy",
    "RequestStatus",
    "RequirementGenerator",
    "RequirementGeneratorConfig",
    "ReviewContext",
    "SimulationConfig",
    "SimulationMetrics",
    "SimulationRunnerConfig",
    "TaskRequirement",
    "validate_request_transition",
]
