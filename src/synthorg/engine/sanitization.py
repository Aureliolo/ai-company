"""Message sanitization helpers for engine subsystems.

Provides pattern-based redaction of file paths and URLs, stripping
of non-printable characters, and length limiting for messages
before they are injected into LLM context.
"""

import re

_PATH_PATTERN = re.compile(
    r"[A-Za-z]:\\[^\s,;)\"']+"
    r"|\\\\[^\s,;)\"']+"
    r"|//[^\s,;)\"']{2,}"
    r"|/[^\s,;)\"']{2,}"
    r"|\.\.?/[^\s,;)\"']+"
)
_URL_PATTERN = re.compile(
    r"(?:https?|postgresql|postgres|mysql|redis|mongodb|amqp|ftp|sftp|file)"
    r"://[^\s,;)\"']+"
)


def sanitize_message(raw: str, *, max_length: int = 200) -> str:
    """Redact paths/URLs, strip non-printable chars, and limit length.

    Args:
        raw: The raw message to sanitize.
        max_length: Upper bound on character length (applied before
            non-printable stripping, so the result may be shorter).

    Returns:
        Sanitized message safe for inclusion in LLM context.
        If the result contains no alphanumeric characters after
        processing, returns ``"details redacted"`` as a safe fallback.
    """
    sanitized = _URL_PATTERN.sub("[REDACTED_URL]", raw)
    sanitized = _PATH_PATTERN.sub("[REDACTED_PATH]", sanitized)
    sanitized = "".join(c for c in sanitized[:max_length] if c.isprintable())
    if not any(c.isalnum() for c in sanitized):
        return "details redacted"
    return sanitized
