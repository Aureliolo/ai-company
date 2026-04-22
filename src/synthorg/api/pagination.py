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
from synthorg.observability import get_logger
from synthorg.observability.events.api import API_CURSOR_INVALID

logger = get_logger(__name__)

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
    if cursor is None:
        offset = 0
    else:
        try:
            offset = decode_cursor(cursor, secret=secret)
        except InvalidCursorError:
            # Malformed / tampered / foreign-secret cursors raise here;
            # log before re-raising so 400s from decode failures are
            # observable in production alongside the truncation branch
            # below.  The cursor itself is NOT logged -- it's attacker-
            # controlled input and may carry secret fragments from
            # tampering attempts.
            logger.warning(
                API_CURSOR_INVALID,
                reason="cursor_decode_failed",
            )
            raise
    effective_limit = max(1, min(limit, MAX_LIMIT))
    # Out-of-bounds cursors are rejected explicitly.  The cursor is
    # HMAC-signed so a client cannot forge one past the true end;
    # reaching this branch means the collection shrunk between
    # issuing the cursor and walking it (e.g. deletions) -- returning
    # an empty page would silently hide the truncation from callers
    # that rely on ``has_more`` progressing consistently.  The
    # comparison is ``>=`` because ``has_more`` is False whenever
    # ``next_offset == len(items)``, so no valid cursor is ever issued
    # pointing exactly at the collection end -- reaching that position
    # is the unambiguous truncation signal.
    if offset and offset >= len(items):
        # Truncation is an operator-visible event: the collection
        # shrank between cursor issuance and replay, and silently
        # returning an empty page would hide that from monitoring.
        logger.warning(
            API_CURSOR_INVALID,
            reason="cursor_past_end",
            offset=offset,
            collection_length=len(items),
        )
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


def encode_repo_seek_meta(  # noqa: PLR0913 -- every arg tracks a distinct pagination input
    *,
    offset: int,
    page_len: int,
    total: int,
    limit: int,
    secret: CursorSecret,
    display_total: int | None = None,
    reject_stale_cursor: bool = True,
) -> PaginationMeta:
    """Build ``PaginationMeta`` for controllers that push limit+offset into the repo.

    Centralizes the ``has_more`` snapshot-drift guard so the next
    pagination bug cannot regress across every version-history
    controller one at a time.  An empty or short page (``page_len ==
    0`` or ``offset + page_len == offset``) cannot advance the cursor
    past the current offset, so the guard refuses to emit a cursor
    that would loop the client on the same page when
    ``count_versions`` disagrees with ``list_versions``.

    ``display_total`` is an override for ``PaginationMeta.total`` that
    stays independent of the ``total`` used for the ``has_more``
    check.  Controllers that filter out forged / cross-wired rows
    after the repo read (``agent_identity_versions``) need to report
    a lower ``total`` to clients while still letting ``has_more``
    see the full repo row count, so later pages containing only
    legitimate rows stay reachable.

    Args:
        offset: The decoded cursor offset the current page started at.
        page_len: The number of repo rows consumed (``len(repo_rows)``,
            *not* the filtered slice) -- the cursor must advance by
            consumed rows so filtered pages do not replay already-read
            rows on the next request.
        total: The repo's reported total row count.  Drives the
            ``has_more`` check.
        limit: The page size requested.
        secret: HMAC secret used to sign the ``next_cursor``.
        display_total: Optional override for ``PaginationMeta.total``.
            Defaults to ``total``.  Pass a lower value when the
            controller drops rows between the repo read and the
            client-facing slice (e.g. owner-mismatch forgeries) so
            ``pagination.total`` stays consistent with ``data``.
        reject_stale_cursor: When ``True`` (the default), a decoded
            ``offset == total`` raises :class:`InvalidCursorError`
            (mirrors the ``paginate_cursor`` helper).  Set to
            ``False`` only when the caller genuinely tolerates a
            cursor landing exactly on the current end of an
            append-only repo.  ``offset > total`` is ALWAYS rejected
            regardless of this flag -- a cursor past the repo end is
            never legitimate (the HMAC signature would have come from
            a larger snapshot) and silently returning a terminal
            page would hide the truncation from monitoring.

    Returns:
        ``PaginationMeta`` with the ``has_more`` / ``next_cursor``
        fields filled in, safe to wrap in ``PaginatedResponse``.

    Raises:
        InvalidCursorError: When the cursor's decoded offset is past
            the repo end.  ``offset > total`` always raises;
            ``offset == total`` (with offset > 0) raises unless
            ``reject_stale_cursor=False``.
    """
    # Out-of-bounds cursors signal the repo shrank between cursor
    # issuance and replay (deletions, filters).  Silently reporting
    # ``has_more=False`` would hide the truncation from monitoring
    # and strand clients on an empty page they cannot recover from;
    # raise so callers surface the state change as HTTP 400.  Split
    # the boundary (``offset == total``) from the past-end case
    # (``offset > total``) so ``reject_stale_cursor=False`` can relax
    # the boundary alone without opening a loophole for clearly
    # invalid cursors.
    if offset and offset > total:
        logger.warning(
            API_CURSOR_INVALID,
            reason="cursor_past_end",
            offset=offset,
            total=total,
        )
        msg = "cursor points past the end of the collection"
        raise InvalidCursorError(msg)
    if reject_stale_cursor and offset and offset == total:
        logger.warning(
            API_CURSOR_INVALID,
            reason="cursor_at_end",
            offset=offset,
            total=total,
        )
        msg = "cursor points past the end of the collection"
        raise InvalidCursorError(msg)
    next_offset = offset + page_len
    has_more = page_len > 0 and next_offset > offset and next_offset < total
    next_cursor = encode_cursor(next_offset, secret=secret) if has_more else None
    return PaginationMeta(
        limit=limit,
        next_cursor=next_cursor,
        has_more=has_more,
        total=display_total if display_total is not None else total,
        offset=offset,
    )


__all__ = (
    "CursorLimit",
    "CursorParam",
    "InvalidCursorError",
    "encode_repo_seek_meta",
    "paginate_cursor",
)
