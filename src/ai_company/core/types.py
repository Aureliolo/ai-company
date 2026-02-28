"""Reusable Pydantic type annotations and validators."""

from collections import Counter
from typing import Annotated

from pydantic import AfterValidator, StringConstraints


def _check_not_whitespace(value: str) -> str:
    """Reject whitespace-only strings."""
    if not value.strip():
        msg = "must not be whitespace-only"
        raise ValueError(msg)
    return value


NotBlankStr = Annotated[
    str,
    StringConstraints(min_length=1),
    AfterValidator(_check_not_whitespace),
]
"""A string that must be non-empty and not consist solely of whitespace."""


def validate_non_blank_unique_strings(
    values: tuple[str, ...],
    field_name: str,
) -> None:
    """Validate that every string in *values* is non-blank and unique.

    Raises:
        ValueError: If any entry is empty/whitespace-only or if duplicates
            are present.
    """
    for entry in values:
        if not entry.strip():
            msg = f"Empty or whitespace-only entry in {field_name}"
            raise ValueError(msg)
    if len(values) != len(set(values)):
        dupes = sorted(v for v, c in Counter(values).items() if c > 1)
        msg = f"Duplicate entries in {field_name}: {dupes}"
        raise ValueError(msg)
