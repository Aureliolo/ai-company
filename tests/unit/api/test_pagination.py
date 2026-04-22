"""Unit tests for the cursor-based pagination helper."""

import pytest

from synthorg.api.cursor import CursorSecret, InvalidCursorError
from synthorg.api.pagination import paginate_cursor

pytestmark = pytest.mark.unit


@pytest.fixture
def secret() -> CursorSecret:
    return CursorSecret.from_key("paginate-test-key-32-bytes-pad0000")


class TestHappyPath:
    """Walk through the full collection page by page."""

    def test_empty_collection(self, secret: CursorSecret) -> None:
        empty: tuple[int, ...] = ()
        page, meta = paginate_cursor(empty, limit=10, cursor=None, secret=secret)
        assert page == ()
        assert meta.limit == 10
        assert meta.next_cursor is None
        assert meta.has_more is False

    def test_single_page(self, secret: CursorSecret) -> None:
        items = tuple(range(5))
        page, meta = paginate_cursor(items, limit=10, cursor=None, secret=secret)
        assert page == items
        assert meta.has_more is False
        assert meta.next_cursor is None

    def test_three_page_walk(self, secret: CursorSecret) -> None:
        items = tuple(range(130))
        collected: list[int] = []
        cursor: str | None = None
        pages = 0
        while True:
            page, meta = paginate_cursor(
                items,
                limit=50,
                cursor=cursor,
                secret=secret,
            )
            collected.extend(page)
            pages += 1
            if not meta.has_more:
                assert meta.next_cursor is None
                break
            assert meta.next_cursor is not None
            cursor = meta.next_cursor
            assert pages <= 10, "Walk exceeded expected page budget"
        assert pages == 3
        assert collected == list(items)

    def test_exact_page_boundary_has_no_next_cursor(
        self,
        secret: CursorSecret,
    ) -> None:
        items = tuple(range(50))
        page, meta = paginate_cursor(items, limit=50, cursor=None, secret=secret)
        assert len(page) == 50
        # 50 items, page of 50 -> no more.
        assert meta.has_more is False
        assert meta.next_cursor is None


class TestLimitClamping:
    """Limit must be clamped to [1, MAX_LIMIT]."""

    def test_limit_clamped_to_max(self, secret: CursorSecret) -> None:
        items = tuple(range(500))
        _, meta = paginate_cursor(items, limit=10_000, cursor=None, secret=secret)
        # MAX_LIMIT is 200 today; clamped to it.
        assert meta.limit == 200


class TestInvalidCursor:
    """Tampered / malformed cursors surface as InvalidCursorError."""

    def test_tampered_cursor_rejected(self, secret: CursorSecret) -> None:
        with pytest.raises(InvalidCursorError):
            paginate_cursor(
                (1, 2, 3),
                limit=10,
                cursor="not-a-valid-token",
                secret=secret,
            )

    def test_cursor_signed_by_other_secret_rejected(
        self,
        secret: CursorSecret,
    ) -> None:
        other = CursorSecret.from_key("other-secret-unit-test-key-pad0000")
        _, meta = paginate_cursor(
            tuple(range(100)),
            limit=10,
            cursor=None,
            secret=other,
        )
        assert meta.next_cursor is not None
        with pytest.raises(InvalidCursorError):
            paginate_cursor(
                tuple(range(100)),
                limit=10,
                cursor=meta.next_cursor,
                secret=secret,
            )


class TestCursorStability:
    """Same input -> same cursor (deterministic for a fixed secret)."""

    def test_cursor_is_deterministic(self, secret: CursorSecret) -> None:
        items = tuple(range(20))
        _, meta_a = paginate_cursor(items, limit=5, cursor=None, secret=secret)
        _, meta_b = paginate_cursor(items, limit=5, cursor=None, secret=secret)
        assert meta_a.next_cursor == meta_b.next_cursor
