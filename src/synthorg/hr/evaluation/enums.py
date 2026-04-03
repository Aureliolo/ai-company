"""Evaluation framework enumerations."""

from enum import StrEnum


class EvaluationPillar(StrEnum):
    """The five evaluation pillars for agent performance assessment.

    Based on the InfoQ five-pillar evaluation framework for AI agents.
    Each pillar can be independently enabled/disabled via configuration.
    """

    INTELLIGENCE = "intelligence"
    EFFICIENCY = "efficiency"
    RESILIENCE = "resilience"
    GOVERNANCE = "governance"
    EXPERIENCE = "experience"
