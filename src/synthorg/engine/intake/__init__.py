"""Intake engine for processing client requests."""

from synthorg.engine.intake.models import IntakeResult
from synthorg.engine.intake.protocol import IntakeStrategy

__all__ = [
    "IntakeResult",
    "IntakeStrategy",
]
