"""Scaling domain exceptions."""


class ScalingError(Exception):
    """Base exception for scaling operations."""


class ScalingStrategyError(ScalingError):
    """A strategy evaluation failed."""


class ScalingGuardError(ScalingError):
    """A guard evaluation failed."""


class ScalingExecutionError(ScalingError):
    """Executing a scaling decision (hire/prune) failed."""


class ScalingCooldownActiveError(ScalingError):
    """Action blocked by an active cooldown window."""
