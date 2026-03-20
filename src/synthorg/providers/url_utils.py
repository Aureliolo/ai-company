"""Shared URL utilities for the providers package."""

from urllib.parse import urlparse, urlunparse


def redact_url(url: str) -> str:
    """Strip userinfo and query parameters from a URL for safe logging.

    Handles IPv6 literal hosts (brackets preserved) and malformed
    ports (silently ignored) so this never raises during logging.

    Args:
        url: URL to redact.

    Returns:
        URL with userinfo stripped and query replaced with
        ``<redacted>`` (if present).
    """
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    # Bracket IPv6 literals so the netloc is unambiguous.
    if ":" in hostname:
        hostname = f"[{hostname}]"
    # parsed.port raises ValueError on malformed ports -- treat as absent.
    try:
        port = parsed.port
    except ValueError:
        port = None
    safe_netloc = f"{hostname}:{port}" if port else hostname
    redacted_query = "<redacted>" if parsed.query else ""
    return urlunparse(parsed._replace(netloc=safe_netloc, query=redacted_query))
