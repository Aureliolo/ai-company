"""Immutability helpers for frozen Pydantic models.

These utilities support the project's immutability convention
documented in CLAUDE.md: mutable ``dict`` fields are deep-copied at
the model construction boundary so that a caller cannot mutate a
frozen model through a retained reference.

``deep_copy_mapping`` handles ``dict`` inputs only.  Frozen Pydantic
models with ``list`` / ``tuple`` / ``set`` fields should prefer the
immutable tuple form (``tuple[...]``) over runtime wrapping -- tuples
need no deep-copy protection because they are already immutable at
the Python level.

Pydantic ``field_validator(mode="before")`` runs before field type
coercion, which is exactly where we want to intercept dict inputs.
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
