"""Unicode-safe normalization helpers.

Uses :py:meth:`str.casefold` (not :py:meth:`str.lower`) so
case-insensitive comparisons behave correctly across Latin, German
sharp-s, Greek, and Turkish dotted-I pairs.
"""

from typing import TYPE_CHECKING

from synthorg.observability import get_logger

if TYPE_CHECKING:
    from collections.abc import Iterable

logger = get_logger(__name__)


def casefold_equals(a: str, b: str) -> bool:
    """Return ``True`` when ``a`` and ``b`` compare equal after casefolding.

    Leading and trailing whitespace is stripped before comparison so
    ``"Alice "`` matches ``"alice"``. Callers that need the exact
    whitespace-sensitive form should do the comparison themselves.
    """
    return a.strip().casefold() == b.strip().casefold()


def find_by_name_ci[T](
    items: Iterable[T],
    target: str,
    *,
    name_attr: str = "name",
) -> T | None:
    """Return the first item whose ``name_attr`` casefolds to ``target``.

    Works on any iterable of objects that expose a string attribute
    named ``name_attr`` (default ``"name"``). Returns ``None`` when
    no match is found.

    Args:
        items: Iterable to scan linearly.
        target: Value to match (case- and whitespace-insensitive).
        name_attr: Attribute name holding the comparable string.

    Returns:
        The first matching item, or ``None``.
    """
    target_normalised = target.strip().casefold()
    for item in items:
        value = getattr(item, name_attr, None)
        if isinstance(value, str) and value.strip().casefold() == target_normalised:
            return item
    return None
