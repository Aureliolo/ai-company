"""Cursor-based pagination helpers.

In-memory helper :func:`paginate_cursor` slices a tuple and produces a
signed cursor so controllers backed by in-memory collections (config
lists, bus channel names, approval-store filtered views) can return
the same envelope shape as repo-backed endpoints.

The cursor layer is opaque offset encoding today. Repositories that
need seek-based paging (append-only tables) decode the opaque cursor
into a composite ``(created_at, id)`` seek tuple internally -- the
wire format stays the same.
"""

from typing import Annotated

from litestar.params import Parameter

from synthorg.api.cursor import (
    CursorSecret,
    InvalidCursorError,
    decode_cursor,
    encode_cursor,
)
from synthorg.api.dto import DEFAULT_LIMIT, MAX_LIMIT, PaginationMeta

CursorLimit = Annotated[
    int,
    Parameter(
        ge=1,
        le=MAX_LIMIT,
        description=f"Page size (default {DEFAULT_LIMIT}, max {MAX_LIMIT})",
    ),
]
"""Query-parameter type for the page size (1-MAX_LIMIT)."""

CursorParam = Annotated[
    str | None,
    Parameter(
        max_length=512,
        description="Opaque pagination cursor returned by the previous page",
    ),
]
"""Query-parameter type for the opaque cursor (max 512 chars)."""


def paginate_cursor[T](
    items: tuple[T, ...],
    *,
    limit: int,
    cursor: str | None,
    secret: CursorSecret,
) -> tuple[tuple[T, ...], PaginationMeta]:
    """Slice a tuple and produce cursor-based pagination metadata.

    Clamps ``limit`` to ``[1, MAX_LIMIT]``. A missing cursor starts at
    offset 0. Invalid / tampered cursors raise :class:`InvalidCursorError`
    which controllers should surface as HTTP 400.

    Args:
        items: Full collection to paginate (must be already ordered).
        limit: Maximum items to return on this page.
        cursor: Opaque cursor from the previous page, or ``None`` for
            the first page.
        secret: HMAC secret used to sign / verify cursors.

    Returns:
        Tuple of (page_items, pagination_meta).

    Raises:
        InvalidCursorError: If ``cursor`` is malformed, tampered, or
            signed by a different secret.
    """
    offset = 0 if cursor is None else decode_cursor(cursor, secret=secret)
    effective_limit = max(1, min(limit, MAX_LIMIT))
    # Out-of-bounds cursors are rejected explicitly.  The cursor is
    # HMAC-signed so a client cannot forge one past the true end;
    # reaching this branch means the collection shrunk between
    # issuing the cursor and walking it (e.g. deletions) -- returning
    # an empty page would silently hide the truncation from callers
    # that rely on ``has_more`` progressing consistently.
    if offset > len(items):
        msg = "cursor points past the end of the collection"
        raise InvalidCursorError(msg)
    page = items[offset : offset + effective_limit]
    next_offset = offset + effective_limit
    has_more = next_offset < len(items)
    next_cursor = encode_cursor(next_offset, secret=secret) if has_more else None
    meta = PaginationMeta(
        limit=effective_limit,
        next_cursor=next_cursor,
        has_more=has_more,
        total=len(items),
        offset=offset,
    )
    return page, meta


__all__ = (
    "CursorLimit",
    "CursorParam",
    "InvalidCursorError",
    "paginate_cursor",
)
