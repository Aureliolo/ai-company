"""Immutability helpers for frozen Pydantic models.

These utilities support the project's immutability convention
documented in CLAUDE.md: mutable collection fields (``dict``, nested
lists) are deep-copied at the model construction boundary so that a
caller cannot mutate a frozen model through a retained reference.

Pydantic ``field_validator(mode="before")`` runs before field type
coercion, which is exactly where we want to intercept dict/list inputs.
"""

import copy
from typing import Any


def deep_copy_mapping(value: Any) -> Any:
    """Deep-copy a mapping value, leaving non-mappings untouched.

    Used as a ``field_validator(mode="before")`` body to isolate frozen
    Pydantic models from caller mutation of ``dict`` fields.

    Args:
        value: The raw field value before Pydantic type coercion.

    Returns:
        A deep copy of ``value`` when it is a ``dict``; otherwise the
        original value unchanged (Pydantic's type validation will
        reject bad types downstream).
    """
    if isinstance(value, dict):
        return copy.deepcopy(value)
    return value
