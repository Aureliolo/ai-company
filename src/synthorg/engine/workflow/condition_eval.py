"""Safe condition expression evaluator for workflow conditional nodes.

Supports a minimal expression language without ``eval()`` or
``exec()``.  Designed to be replaceable with a richer evaluator
in a future iteration.

Supported expressions:

- Boolean literals: ``"true"``, ``"false"`` (case-insensitive)
- Key lookup (truthy): ``"has_budget"`` -- returns ``bool(context[key])``
  Key lookup on a missing key returns ``False``
  (``context.get(key)`` is ``None``, which is falsy).
- Equality: ``"priority == high"`` -- returns ``context[key] == value``
- Inequality: ``"env != prod"`` -- returns ``context[key] != value``
- Missing keys return ``False`` (equality) or ``True`` (inequality)
- Empty or whitespace-only expressions evaluate to ``False``

This function does not raise -- all edge cases (empty expressions,
missing keys, malformed comparisons) resolve to a boolean.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping


def _eval_comparison(
    expr: str,
    context: Mapping[str, object],
) -> bool | None:
    """Evaluate equality/inequality comparisons.

    Returns the boolean result, or ``None`` if *expr* contains
    neither ``==`` nor ``!=``.
    """
    for op in ("!=", "=="):
        if op not in expr:
            continue
        key, _, value = expr.partition(op)
        key = key.strip()
        value = value.strip()
        if not key or not value:
            return False
        ctx_value = context.get(key)
        missing = key not in context
        if op == "!=":
            return True if missing else str(ctx_value) != value
        return False if missing else str(ctx_value) == value
    return None


def evaluate_condition(
    expression: str,
    context: Mapping[str, object],
) -> bool:
    """Evaluate a condition expression against a context dict.

    This function does not raise -- all edge cases (empty
    expressions, missing keys, malformed comparisons) resolve
    to a boolean.  Callers should not rely on exceptions for
    control flow from this function.

    Args:
        expression: The condition expression string.
        context: Runtime context values for evaluation.

    Returns:
        Boolean result of the expression evaluation.
    """
    expr = expression.strip()
    if not expr:
        return False

    # Boolean literals
    lower = expr.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False

    # Equality / inequality comparison
    result = _eval_comparison(expr, context)
    if result is not None:
        return result

    # Key lookup (truthy)
    return bool(context.get(expr))
