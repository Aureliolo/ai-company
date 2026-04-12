"""Middleware-specific exceptions."""

from synthorg.engine.errors import EngineError


class MiddlewareError(EngineError):
    """Base exception for all middleware-layer errors."""


class MiddlewareConfigError(MiddlewareError):
    """Raised when middleware configuration is invalid."""


class MiddlewareRegistryError(MiddlewareError):
    """Raised when a middleware name cannot be resolved in the registry."""

    def __init__(self, name: str, *, registry_type: str) -> None:
        super().__init__(f"Unknown {registry_type} middleware: {name!r}")
        self.middleware_name = name
        self.registry_type = registry_type


class ClarificationRequiredError(MiddlewareError):
    """Raised when acceptance criteria lack specificity.

    The pre-decomposition clarification gate blocks decomposition
    until the task's acceptance criteria are sufficiently specific.

    Attributes:
        task_id: The task whose criteria failed validation.
        reasons: Human-readable reasons why each criterion failed.
    """

    def __init__(
        self,
        *,
        task_id: str,
        reasons: tuple[str, ...],
    ) -> None:
        summary = "; ".join(reasons[:5])
        overflow = len(reasons) - 5
        more = f" (+{overflow} more)" if overflow > 0 else ""
        super().__init__(
            f"Task {task_id!r} acceptance criteria too vague: {summary}{more}"
        )
        self.task_id = task_id
        self.reasons = reasons
