"""Budget-layer error hierarchy.

Defines budget-specific exceptions in a leaf module with minimal
intra-project imports, preventing circular dependency chains when
these exceptions are needed by both the budget enforcer and the
engine layer.
"""

from typing import TYPE_CHECKING

from synthorg.core.types import NotBlankStr  # noqa: TC001

if TYPE_CHECKING:
    from synthorg.budget.quota import DegradationAction


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


class RiskBudgetExhaustedError(BudgetExhaustedError):
    """Raised when cumulative risk budget is exhausted.

    Subclass of ``BudgetExhaustedError`` so existing engine-level
    catch handlers cover it transparently.

    Attributes:
        agent_id: The agent that exceeded the limit, or ``None``.
        task_id: The task during which the limit was exceeded, or ``None``.
        risk_units_used: Cumulative risk units consumed.
        risk_limit: The limit that was exceeded.
    """

    def __init__(
        self,
        msg: str,
        *,
        agent_id: NotBlankStr | None = None,
        task_id: NotBlankStr | None = None,
        risk_units_used: float = 0.0,
        risk_limit: float = 0.0,
    ) -> None:
        super().__init__(msg)
        self.agent_id = agent_id
        self.task_id = task_id
        self.risk_units_used = risk_units_used
        self.risk_limit = risk_limit


class ProjectBudgetExhaustedError(BudgetExhaustedError):
    """Project-level budget limit exceeded.

    Attributes:
        project_id: The project whose budget was exceeded.
        project_budget: The project's total budget.
        project_spent: Amount already spent on the project.
    """

    def __init__(
        self,
        msg: str,
        *,
        project_id: NotBlankStr,
        project_budget: float = 0.0,
        project_spent: float = 0.0,
    ) -> None:
        super().__init__(msg)
        self.project_id = project_id
        self.project_budget = project_budget
        self.project_spent = project_spent


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
