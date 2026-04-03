"""Optimistic concurrency via ETag / If-Match.

Provides utilities for computing weak ETags from resource state
and validating ``If-Match`` request headers to detect concurrent
modification conflicts.
"""

import hashlib

from synthorg.api.errors import VersionConflictError
from synthorg.observability import get_logger
from synthorg.observability.events.api import (
    API_CONCURRENCY_CONFLICT,
)

logger = get_logger(__name__)


def compute_etag(value: str, updated_at: str) -> str:
    """Compute a weak ETag from value and timestamp.

    Uses SHA-256 truncated to 16 hex characters, prefixed with
    ``W/`` per RFC 7232 (weak validator -- the representation
    may vary by encoding).

    Args:
        value: Resource value (e.g. setting value, config JSON).
        updated_at: Last-modified timestamp string.

    Returns:
        Weak ETag string like ``W/"a1b2c3d4e5f6g7h8"``.
    """
    digest = hashlib.sha256(
        f"{value}:{updated_at}".encode(),
    ).hexdigest()[:16]
    return f'W/"{digest}"'


def check_if_match(
    request_etag: str | None,
    current_etag: str,
    resource_name: str,
) -> None:
    """Raise ``VersionConflictError`` if If-Match doesn't match.

    When ``request_etag`` is ``None`` or empty, the check is
    skipped (backward compatible -- clients not sending
    ``If-Match`` bypass optimistic concurrency).

    Args:
        request_etag: Value from the ``If-Match`` request header.
        current_etag: Current ETag of the resource.
        resource_name: For error messages and logging.

    Raises:
        VersionConflictError: On ETag mismatch (HTTP 409).
    """
    if not request_etag:
        return

    if request_etag != current_etag:
        logger.info(
            API_CONCURRENCY_CONFLICT,
            resource=resource_name,
            request_etag=request_etag,
            current_etag=current_etag,
        )
        msg = (
            f"Version conflict on {resource_name}: "
            f"expected {current_etag}, got {request_etag}"
        )
        raise VersionConflictError(msg)
