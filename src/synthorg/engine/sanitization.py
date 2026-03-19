"""Message sanitization helpers for engine subsystems.

Provides pattern-based redaction of file paths, URLs, and
non-printable characters from messages before they are injected
into LLM context.
"""

import re

_PATH_PATTERN = re.compile(
    r"[A-Za-z]:\\[^\s,;)\"']+"
    r"|/(?:home|usr|var|tmp|etc|opt|root|srv|app|data)[^\s,;)\"']+"
    r"|\.\.?/[^\s,;)\"']+"
)
_URL_PATTERN = re.compile(r"https?://[^\s,;)\"']+")


def sanitize_message(raw: str, *, max_length: int = 200) -> str:
    """Redact paths/URLs, strip non-printable chars, and limit length.

    Args:
        raw: The raw message to sanitize.
        max_length: Maximum character length of the returned string.

    Returns:
        Sanitized message safe for inclusion in LLM context.
    """
    sanitized = _PATH_PATTERN.sub("[REDACTED_PATH]", raw)
    sanitized = _URL_PATTERN.sub("[REDACTED_URL]", sanitized)
    sanitized = "".join(c for c in sanitized[:max_length] if c.isprintable())
    if not any(c.isalnum() for c in sanitized):
        return "details redacted"
    return sanitized
