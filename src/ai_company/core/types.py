"""Reusable Pydantic type annotations."""

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
