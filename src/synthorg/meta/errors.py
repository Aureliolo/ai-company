"""Domain errors for the self-improving meta-loop.

Errors here are raised by the service layer and translated to MCP /
REST envelopes by the handler layer. They carry enough context for
operators to disambiguate why a cycle could not run without leaking
internal config state.
"""


class SelfImprovementError(Exception):
    """Base class for self-improvement service domain errors."""


class SelfImprovementTriggerError(SelfImprovementError):
    """Raised when ``SelfImprovementService.trigger_cycle`` cannot run.

    Triggers fail when prerequisites are missing -- for example, no
    snapshot builder is wired -- rather than running with degraded
    inputs that would produce misleading proposals.
    """
