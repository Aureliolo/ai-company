"""Correlation ID management for structured logging.

Uses structlog's contextvars integration for async-safe context
propagation across agent actions, tasks, and API requests.

.. note::

    All binding functions are safe to call from both sync and async
    code because Python's :mod:`contextvars` is natively async-aware.
"""

# TODO: Add with_correlation_async() for async functions (engine/API)

import functools
import uuid
from typing import TYPE_CHECKING, ParamSpec, TypeVar

import structlog

if TYPE_CHECKING:
    from collections.abc import Callable

_P = ParamSpec("_P")
_T = TypeVar("_T")


def generate_correlation_id() -> str:
    """Generate a new correlation ID.

    Returns:
        A UUID4 string suitable for use as a correlation identifier.
    """
    return str(uuid.uuid4())


def bind_correlation_id(
    *,
    request_id: str | None = None,
    task_id: str | None = None,
    agent_id: str | None = None,
) -> None:
    """Bind correlation IDs to the current context.

    Only non-``None`` values are bound.  Existing bindings for
    unspecified keys are left unchanged.

    Args:
        request_id: Request correlation identifier.
        task_id: Task correlation identifier.
        agent_id: Agent correlation identifier.
    """
    bindings: dict[str, str] = {}
    if request_id is not None:
        bindings["request_id"] = request_id
    if task_id is not None:
        bindings["task_id"] = task_id
    if agent_id is not None:
        bindings["agent_id"] = agent_id
    if bindings:
        structlog.contextvars.bind_contextvars(**bindings)


def unbind_correlation_id(
    *,
    request_id: bool = False,
    task_id: bool = False,
    agent_id: bool = False,
) -> None:
    """Remove specific correlation IDs from the current context.

    Args:
        request_id: Whether to unbind the ``request_id`` key.
        task_id: Whether to unbind the ``task_id`` key.
        agent_id: Whether to unbind the ``agent_id`` key.
    """
    keys: list[str] = []
    if request_id:
        keys.append("request_id")
    if task_id:
        keys.append("task_id")
    if agent_id:
        keys.append("agent_id")
    if keys:
        structlog.contextvars.unbind_contextvars(*keys)


def clear_correlation_ids() -> None:
    """Clear all correlation IDs from the current context."""
    structlog.contextvars.clear_contextvars()


def with_correlation(
    *,
    request_id: str | None = None,
    task_id: str | None = None,
    agent_id: str | None = None,
) -> Callable[[Callable[_P, _T]], Callable[_P, _T]]:
    """Decorator that binds correlation IDs for a function's duration.

    Correlation IDs are bound before the function executes and unbound
    after it returns or raises.  Only non-``None`` IDs are managed.

    Args:
        request_id: Request correlation identifier to bind.
        task_id: Task correlation identifier to bind.
        agent_id: Agent correlation identifier to bind.

    Returns:
        A decorator that manages correlation ID lifecycle.
    """

    def decorator(func: Callable[_P, _T]) -> Callable[_P, _T]:
        @functools.wraps(func)
        def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _T:
            bind_correlation_id(
                request_id=request_id,
                task_id=task_id,
                agent_id=agent_id,
            )
            try:
                return func(*args, **kwargs)
            finally:
                unbind_correlation_id(
                    request_id=request_id is not None,
                    task_id=task_id is not None,
                    agent_id=agent_id is not None,
                )

        return wrapper

    return decorator
