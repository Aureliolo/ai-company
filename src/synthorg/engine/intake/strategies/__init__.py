"""Built-in intake strategies."""

from synthorg.engine.intake.strategies.agent_intake import AgentIntake
from synthorg.engine.intake.strategies.direct import DirectIntake

__all__ = [
    "AgentIntake",
    "DirectIntake",
]
