"""Message sanitization helpers for engine subsystems.

Provides pattern-based redaction of file paths and URLs, stripping
of non-printable characters, and length limiting for messages
before they are injected into LLM context.
"""

import re

_PATH_PATTERN = re.compile(
    # Quoted Windows paths (handles spaces in paths like Program Files)
    r'"[A-Za-z]:\\[^"]*"'
    r"|'[A-Za-z]:\\[^']*'"
    # Windows drive-letter paths (unquoted)
    r"|[A-Za-z]:\\[^\s,;)\"']+"
    # UNC backslash paths
    r"|\\\\[^\s,;)\"']+"
    # UNC forward-slash paths
    r"|//[^\s,;)\"']{2,}"
    # Unix absolute paths (not preceded by a word character to avoid
    # false positives on ratios like 100/min or content-type headers)
    r"|(?<!\w)/[^\s,;)\"']{2,}"
    # Relative paths
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
        max_length: Upper bound on raw input length in characters.
            Applied before path/URL redaction and non-printable
            stripping. Redaction tokens may cause the output to
            slightly exceed this limit.

    Returns:
        Sanitized message safe for inclusion in LLM context.
        If the result contains no alphanumeric characters after
        processing, returns ``"details redacted"`` as a safe fallback.

    Raises:
        ValueError: If ``max_length`` is negative.
    """
    if max_length < 0:
        msg = f"max_length must be >= 0, got {max_length}"
        raise ValueError(msg)
    capped = raw[:max_length]
    sanitized = _URL_PATTERN.sub("[REDACTED_URL]", capped)
    sanitized = _PATH_PATTERN.sub("[REDACTED_PATH]", sanitized)
    sanitized = "".join(c for c in sanitized if c.isprintable())
    if not any(c.isalnum() for c in sanitized):
        return "details redacted"
    return sanitized
