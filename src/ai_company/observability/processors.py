"""Custom structlog processors for the observability pipeline."""

import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping, MutableMapping

_SENSITIVE_PATTERN: re.Pattern[str] = re.compile(
    r"(password|secret|token|api_key|api_secret|authorization"
    r"|credential|private_key|bearer|session)",
    re.IGNORECASE,
)

_REDACTED = "**REDACTED**"


def sanitize_sensitive_fields(
    logger: Any,  # noqa: ARG001
    method_name: str,  # noqa: ARG001
    event_dict: MutableMapping[str, Any],
) -> Mapping[str, Any]:
    """Redact values of keys matching sensitive patterns.

    Returns a new dict rather than mutating the original event dict,
    following the project's immutability convention.

    Args:
        logger: The wrapped logger object (unused, required by structlog).
        method_name: The name of the log method called (unused).
        event_dict: The event dictionary to process.

    Returns:
        A new event dict with sensitive values replaced by
        ``**REDACTED**``.
    """
    return {
        key: (
            _REDACTED
            if isinstance(key, str) and _SENSITIVE_PATTERN.search(key)
            else value
        )
        for key, value in event_dict.items()
    }
