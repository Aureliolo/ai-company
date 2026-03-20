"""Budget-layer error hierarchy.

Defines budget-specific exceptions in a leaf module with minimal
intra-project imports, preventing circular dependency chains when
these exceptions are needed by both the budget enforcer and the
engine layer.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from synthorg.budget.quota import DegradationAction
    from synthorg.core.types import NotBlankStr


class BudgetExhaustedError(Exception):
    """Budget exhaustion signal.

    Used in two contexts:

    1. Raised directly by :meth:`BudgetEnforcer.check_can_execute`
       when pre-flight budget checks fail (e.g., monthly hard stop,
       daily limit, or provider quota exceeded).
    2. Caught by the engine layer (``AgentEngine.run``) and used to
       build an ``AgentRunResult`` with
       ``TerminationReason.BUDGET_EXHAUSTED``.
    """


class DailyLimitExceededError(BudgetExhaustedError):
    """Per-agent daily spending limit exceeded."""


class QuotaExhaustedError(BudgetExhaustedError):
    """Raised when provider quota is exhausted and unresolvable.

    Covers all terminal degradation outcomes: ALERT strategy
    (intentional immediate raise), failed FALLBACK (no providers
    available or all exhausted), and failed QUEUE (wait exceeded
    or still exhausted after waiting).

    Attributes:
        provider_name: The provider whose quota was exhausted,
            or ``None`` when not available.
        degradation_action: The degradation strategy that was
            attempted, or ``None`` when not available.
    """

    def __init__(
        self,
        msg: str,
        *,
        provider_name: NotBlankStr | None = None,
        degradation_action: DegradationAction | None = None,
    ) -> None:
        super().__init__(msg)
        self.provider_name = provider_name
        self.degradation_action = degradation_action
