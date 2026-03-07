"""Canonical agent-pair key utility.

Both ``DelegationCircuitBreaker`` and ``DelegationRateLimiter`` track
state per *undirected* agent pair.  This helper normalises the key so
that ``(a, b)`` and ``(b, a)`` map to the same entry.
"""


def pair_key(a: str, b: str) -> tuple[str, str]:
    """Create a canonical sorted key for an agent pair.

    The key is direction-agnostic: ``pair_key("x", "y")`` equals
    ``pair_key("y", "x")``.

    Args:
        a: First agent ID.
        b: Second agent ID.

    Returns:
        Lexicographically sorted ``(min, max)`` tuple.
    """
    return (min(a, b), max(a, b))
