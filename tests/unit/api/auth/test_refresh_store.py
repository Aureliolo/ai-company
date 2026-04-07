"""Tests for the refresh token store."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import aiosqlite
import pytest

from synthorg.api.auth.refresh_store import RefreshStore
from synthorg.persistence.sqlite.migrations import apply_schema

pytestmark = pytest.mark.unit

_NOW = datetime.now(UTC)
_PAST = _NOW - timedelta(days=1)
_FUTURE = _NOW + timedelta(days=7)


@pytest.fixture
async def db() -> AsyncGenerator[aiosqlite.Connection]:
    conn = await aiosqlite.connect(":memory:")
    try:
        conn.row_factory = aiosqlite.Row
        await apply_schema(conn)
        yield conn
    finally:
        await conn.close()


@pytest.fixture
async def store(db: aiosqlite.Connection) -> RefreshStore:
    return RefreshStore(db)


class TestRefreshCreate:
    async def test_create_stores_token(self, store: RefreshStore) -> None:
        await store.create(
            token_hash="hash-1",
            session_id="sess-1",
            user_id="user-1",
            expires_at=_FUTURE,
        )
        # Verify via consume
        record = await store.consume("hash-1")
        assert record is not None
        assert record.session_id == "sess-1"
        assert record.user_id == "user-1"
        assert record.used is True


class TestRefreshConsume:
    async def test_consume_marks_used(self, store: RefreshStore) -> None:
        await store.create(
            token_hash="hash-c1",
            session_id="sess-1",
            user_id="user-1",
            expires_at=_FUTURE,
        )
        record = await store.consume("hash-c1")
        assert record is not None
        assert record.used is True

    async def test_consume_single_use(self, store: RefreshStore) -> None:
        """Second consume of the same token returns None (replay)."""
        await store.create(
            token_hash="hash-c2",
            session_id="sess-1",
            user_id="user-1",
            expires_at=_FUTURE,
        )
        first = await store.consume("hash-c2")
        assert first is not None
        second = await store.consume("hash-c2")
        assert second is None

    async def test_consume_nonexistent_returns_none(self, store: RefreshStore) -> None:
        result = await store.consume("nonexistent-hash")
        assert result is None

    async def test_consume_expired_returns_none(self, store: RefreshStore) -> None:
        await store.create(
            token_hash="hash-expired",
            session_id="sess-1",
            user_id="user-1",
            expires_at=_PAST,
        )
        result = await store.consume("hash-expired")
        assert result is None

    async def test_consume_rejects_revoked_session(self, store: RefreshStore) -> None:
        """Token belonging to a revoked session is rejected."""
        await store.create(
            token_hash="hash-revoked-sess",
            session_id="revoked-sess",
            user_id="user-1",
            expires_at=_FUTURE,
        )
        result = await store.consume(
            "hash-revoked-sess",
            is_session_revoked=lambda sid: sid == "revoked-sess",
        )
        assert result is None

    async def test_consume_allows_non_revoked_session(
        self, store: RefreshStore
    ) -> None:
        """Token with a valid session passes the revocation check."""
        await store.create(
            token_hash="hash-valid-sess",
            session_id="valid-sess",
            user_id="user-1",
            expires_at=_FUTURE,
        )
        result = await store.consume(
            "hash-valid-sess",
            is_session_revoked=lambda sid: False,
        )
        assert result is not None
        assert result.session_id == "valid-sess"


class TestRefreshRevoke:
    async def test_revoke_by_session(self, store: RefreshStore) -> None:
        await store.create(
            token_hash="h1",
            session_id="sess-1",
            user_id="user-1",
            expires_at=_FUTURE,
        )
        await store.create(
            token_hash="h2",
            session_id="sess-1",
            user_id="user-1",
            expires_at=_FUTURE,
        )
        await store.create(
            token_hash="h3",
            session_id="sess-2",
            user_id="user-1",
            expires_at=_FUTURE,
        )

        revoked = await store.revoke_by_session("sess-1")
        assert revoked == 2

        # h1 and h2 should be unusable
        assert await store.consume("h1") is None
        assert await store.consume("h2") is None
        # h3 should still work
        assert await store.consume("h3") is not None

    async def test_revoke_by_user(self, store: RefreshStore) -> None:
        await store.create(
            token_hash="u1-h1",
            session_id="sess-1",
            user_id="user-1",
            expires_at=_FUTURE,
        )
        await store.create(
            token_hash="u2-h1",
            session_id="sess-2",
            user_id="user-2",
            expires_at=_FUTURE,
        )

        revoked = await store.revoke_by_user("user-1")
        assert revoked == 1
        assert await store.consume("u1-h1") is None
        assert await store.consume("u2-h1") is not None


class TestRefreshCleanup:
    async def test_cleanup_removes_only_expired(
        self,
        db: aiosqlite.Connection,
    ) -> None:
        store = RefreshStore(db)
        # Expired token -- will be removed
        await store.create(
            token_hash="expired",
            session_id="s1",
            user_id="u1",
            expires_at=_PAST,
        )
        # Used but not expired -- retained for replay detection
        await store.create(
            token_hash="used",
            session_id="s2",
            user_id="u1",
            expires_at=_FUTURE,
        )
        await store.consume("used")
        # Active token
        await store.create(
            token_hash="active",
            session_id="s3",
            user_id="u1",
            expires_at=_FUTURE,
        )

        removed = await store.cleanup_expired()
        assert removed == 1  # only the expired row
        # Used token still in DB (replay detection works)
        assert await store.consume("used") is None  # already consumed
        # Active token still consumable
        assert await store.consume("active") is not None
