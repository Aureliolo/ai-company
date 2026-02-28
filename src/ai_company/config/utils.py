"""Shared configuration utilities."""

import copy
from typing import Any


def deep_merge(
    base: dict[str, Any],
    override: dict[str, Any],
) -> dict[str, Any]:
    """Recursively merge *override* into *base*, returning a new dict.

    Nested dicts are merged recursively.  Lists, scalars, and all other
    types in *override* replace the corresponding value in *base*
    entirely.  Keys present only in *base* are preserved unchanged in
    the result.  Neither input dict is mutated.

    Args:
        base: Base configuration dict.
        override: Override values to layer on top.

    Returns:
        A new merged dict.
    """
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result
