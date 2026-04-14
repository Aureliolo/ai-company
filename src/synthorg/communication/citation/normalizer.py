"""URL normalization for citation deduplication.

Normalizes URLs to a canonical form so that different URL strings
resolving to the same resource share a single citation number.
"""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from synthorg.observability import get_logger

logger = get_logger(__name__)

_DEFAULT_PORTS: dict[str, int] = {"http": 80, "https": 443}


def normalize_url(raw: str) -> str:
    """Normalize a URL to its canonical form.

    Steps:
        1. Lowercase scheme and host.
        2. Strip default ports (80 for http, 443 for https).
        3. Remove fragment.
        4. Sort query parameters alphabetically.
        5. Strip trailing slash from path.

    Args:
        raw: The URL string to normalize.

    Returns:
        Canonical normalized URL string.
    """
    parts = urlsplit(raw)

    scheme = parts.scheme.lower()
    hostname = (parts.hostname or "").lower()

    # Reconstruct netloc: strip default port
    port = parts.port
    if port is not None and _DEFAULT_PORTS.get(scheme) == port:
        port = None

    # Wrap IPv6 addresses in brackets for valid netloc
    if ":" in hostname and not hostname.startswith("["):
        netloc = f"[{hostname}]"
    else:
        netloc = hostname
    # Strip userinfo (credentials) -- security risk and dedup noise
    if port is not None:
        netloc = f"{netloc}:{port}"

    # Strip trailing slash from path
    path = parts.path.rstrip("/") if parts.path != "/" else ""

    # Sort query params, drop empty query
    query = ""
    if parts.query:
        params = parse_qsl(parts.query, keep_blank_values=True)
        params.sort(key=lambda kv: kv[0])
        query = urlencode(params)

    # Fragment is dropped (empty string)
    return urlunsplit((scheme, netloc, path, query, ""))
