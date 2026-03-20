"""Shared URL utilities for the providers package."""

from urllib.parse import urlparse, urlunparse


def redact_url(url: str) -> str:
    """Strip userinfo and query parameters from a URL for safe logging.

    Args:
        url: URL to redact.

    Returns:
        URL with userinfo stripped and query replaced with
        ``<redacted>`` (if present).
    """
    parsed = urlparse(url)
    safe_netloc = parsed.hostname or ""
    if parsed.port:
        safe_netloc = f"{safe_netloc}:{parsed.port}"
    redacted_query = "<redacted>" if parsed.query else ""
    return urlunparse(parsed._replace(netloc=safe_netloc, query=redacted_query))
