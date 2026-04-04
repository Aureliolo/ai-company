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
- Compound operators: ``AND``, ``OR``, ``NOT`` (case-insensitive)
- Parenthesized groups: ``(expr1 AND expr2) OR expr3``

Operator precedence (highest to lowest): NOT, AND, OR.

This function does not raise -- all edge cases (empty expressions,
missing keys, malformed comparisons) resolve to a boolean.
"""

import re
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


def _eval_atom(
    expr: str,
    context: Mapping[str, object],
) -> bool:
    """Evaluate a single atomic expression (no compound operators).

    Handles boolean literals, comparisons, and key lookups.
    """
    expr = expr.strip()
    if not expr:
        return False

    lower = expr.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False

    result = _eval_comparison(expr, context)
    if result is not None:
        return result

    return bool(context.get(expr))


# ── Tokenizer ────────────────────────────────────────────────────

# Match standalone AND/OR/NOT keywords (word boundaries) and parens.
_KEYWORD_RE = re.compile(
    r"""
    (?P<paren>[()]) |
    \b(?P<keyword>AND|OR|NOT)\b
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _tokenize(expression: str) -> list[str]:
    """Tokenize a condition expression into operators, parens, and atoms.

    Keywords (AND/OR/NOT) are only recognized at word boundaries,
    so ``ORLANDO`` or ``NOTICE`` are not split.
    """
    tokens: list[str] = []
    pos = 0
    for match in _KEYWORD_RE.finditer(expression):
        start = match.start()
        # Collect any atom text before this token
        if start > pos:
            atom = expression[pos:start].strip()
            if atom:
                tokens.append(atom)
        paren = match.group("paren")
        keyword = match.group("keyword")
        if paren:
            tokens.append(paren)
        elif keyword:
            tokens.append(keyword.upper())
        pos = match.end()
    # Trailing atom text
    if pos < len(expression):
        atom = expression[pos:].strip()
        if atom:
            tokens.append(atom)
    return tokens


# ── Recursive descent parser ─────────────────────────────────────


def _parse_or(
    tokens: list[str],
    pos: int,
    context: Mapping[str, object],
) -> tuple[bool, int]:
    """Parse OR-level (lowest precedence)."""
    left, pos = _parse_and(tokens, pos, context)
    while pos < len(tokens) and tokens[pos] == "OR":
        pos += 1  # consume OR
        right, pos = _parse_and(tokens, pos, context)
        left = left or right
    return left, pos


def _parse_and(
    tokens: list[str],
    pos: int,
    context: Mapping[str, object],
) -> tuple[bool, int]:
    """Parse AND-level (higher precedence than OR)."""
    left, pos = _parse_not(tokens, pos, context)
    while pos < len(tokens) and tokens[pos] == "AND":
        pos += 1  # consume AND
        right, pos = _parse_not(tokens, pos, context)
        left = left and right
    return left, pos


def _parse_not(
    tokens: list[str],
    pos: int,
    context: Mapping[str, object],
) -> tuple[bool, int]:
    """Parse NOT-level (highest precedence)."""
    if pos < len(tokens) and tokens[pos] == "NOT":
        pos += 1  # consume NOT
        value, pos = _parse_not(tokens, pos, context)
        return not value, pos
    return _parse_atom_token(tokens, pos, context)


def _parse_atom_token(
    tokens: list[str],
    pos: int,
    context: Mapping[str, object],
) -> tuple[bool, int]:
    """Parse an atom: parenthesized group or single comparison."""
    if pos >= len(tokens):
        return False, pos

    if tokens[pos] == "(":
        pos += 1  # consume '('
        value, pos = _parse_or(tokens, pos, context)
        if pos < len(tokens) and tokens[pos] == ")":
            pos += 1  # consume ')'
        return value, pos

    # Anything else is an atom (comparison or key lookup)
    token = tokens[pos]
    # Guard: skip bare operators that ended up as atoms
    if token in ("AND", "OR", "NOT", ")"):
        return False, pos + 1
    return _eval_atom(token, context), pos + 1


# ── Compound detection heuristic ──────────────────────────────────

_COMPOUND_RE = re.compile(r"\b(?:AND|OR|NOT)\b|[()]", re.IGNORECASE)


def _has_compound_operators(expression: str) -> bool:
    """Check if expression contains compound operators or parens."""
    return _COMPOUND_RE.search(expression) is not None


# ── Public API ────────────────────────────────────────────────────


def evaluate_condition(
    expression: str,
    context: Mapping[str, object],
) -> bool:
    """Evaluate a condition expression against a context dict.

    This function does not raise -- all edge cases (empty
    expressions, missing keys, malformed comparisons) resolve
    to a boolean.  Callers should not rely on exceptions for
    control flow from this function.

    Supports compound expressions with AND, OR, NOT operators
    and parenthesized groups.  Operator precedence: NOT > AND > OR.

    Args:
        expression: The condition expression string.
        context: Runtime context values for evaluation.

    Returns:
        Boolean result of the expression evaluation.
    """
    expr = expression.strip()
    if not expr:
        return False

    # Quick path: if no compound operators, use simple evaluation
    # for zero-overhead backward compatibility.
    if not _has_compound_operators(expr):
        return _eval_atom(expr, context)

    # Compound path: tokenize and parse.
    try:
        tokens = _tokenize(expr)
        if not tokens:
            return False
        result, _ = _parse_or(tokens, 0, context)
    except Exception:
        return False
    return result
