"""Tests for the session store."""

from collections.abc import AsyncGenerator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

if TYPE_CHECKING:
    from collections.abc import Iterator

import aiosqlite
import pytest

from synthorg.api.auth.session import Session
from synthorg.api.auth.session_store import SessionStore
from synthorg.api.guards import HumanRole
from synthorg.persistence.sqlite.migrations import apply_schema

pytestmark = pytest.mark.unit

# Use a fixed "now" and patch datetime.now in the store module
# so tests are deterministic regardless of wall clock time.
_NOW = datetime(2026, 4, 3, 12, 0, 0, tzinfo=UTC)
_FROZEN_NOW = _NOW + timedelta(minutes=5)


@contextmanager
def _patch_now() -> Iterator[None]:
    """Patch datetime.now in the session store module."""
    mock_dt = MagicMock(wraps=datetime)
    mock_dt.now.return_value = _FROZEN_NOW
    with patch("synthorg.api.auth.session_store.datetime", mock_dt):
        yield


def _make_session(  # noqa: PLR0913
    *,
    session_id: str = "sess-1",
    user_id: str = "user-1",
    username: str = "alice",
    role: HumanRole = HumanRole.CEO,
    ip_address: str = "127.0.0.1",
    user_agent: str = "test-agent",
    created_at: datetime = _NOW,
    expires_at: datetime | None = None,
    revoked: bool = False,
) -> Session:
    if expires_at is None:
        expires_at = _NOW + timedelta(hours=24)
    return Session(
        session_id=session_id,
        user_id=user_id,
        username=username,
        role=role,
        ip_address=ip_address,
        user_agent=user_agent,
        created_at=created_at,
        last_active_at=created_at,
        expires_at=expires_at,
        revoked=revoked,
    )


@pytest.fixture
async def db() -> AsyncGenerator[aiosqlite.Connection]:
    conn = await aiosqlite.connect(":memory:")
    try:
        conn.row_factory = aiosqlite.Row
        await apply_schema(conn)
        # Insert a user so FK constraints pass.
        await conn.execute(
            "INSERT INTO users "
            "(id, username, password_hash, role, "
            "must_change_password, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "user-1",
                "alice",
                "hash",
                "ceo",
                0,
                _NOW.isoformat(),
                _NOW.isoformat(),
            ),
        )
        await conn.execute(
            "INSERT INTO users "
            "(id, username, password_hash, role, "
            "must_change_password, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "user-2",
                "bob",
                "hash",
                "manager",
                0,
                _NOW.isoformat(),
                _NOW.isoformat(),
            ),
        )
        await conn.commit()
        yield conn
    finally:
        await conn.close()


@pytest.fixture
async def store(db: aiosqlite.Connection) -> SessionStore:
    s = SessionStore(db)
    await s.load_revoked()
    return s


class TestSessionStoreCreate:
    async def test_create_and_get(
        self,
        store: SessionStore,
    ) -> None:
        session = _make_session()
        await store.create(session)
        result = await store.get("sess-1")
        assert result is not None
        assert result.session_id == "sess-1"
        assert result.user_id == "user-1"
        assert result.username == "alice"
        assert result.role == HumanRole.CEO
        assert result.revoked is False

    async def test_get_nonexistent_returns_none(
        self,
        store: SessionStore,
    ) -> None:
        assert await store.get("nonexistent") is None


class TestSessionStoreList:
    async def test_list_by_user(self, store: SessionStore) -> None:
        await store.create(_make_session(session_id="s1"))
        await store.create(
            _make_session(
                session_id="s2",
                user_id="user-2",
                username="bob",
                role=HumanRole.MANAGER,
            ),
        )
        await store.create(_make_session(session_id="s3"))

        result = await store.list_by_user("user-1")
        assert len(result) == 2
        ids = {s.session_id for s in result}
        assert ids == {"s1", "s3"}

    async def test_list_by_user_excludes_revoked(
        self,
        store: SessionStore,
    ) -> None:
        await store.create(_make_session(session_id="s1"))
        await store.create(_make_session(session_id="s2"))
        await store.revoke("s1")

        result = await store.list_by_user("user-1")
        assert len(result) == 1
        assert result[0].session_id == "s2"

    async def test_list_by_user_excludes_expired(
        self,
        store: SessionStore,
    ) -> None:
        await store.create(_make_session(session_id="s1"))
        await store.create(
            _make_session(
                session_id="s2",
                created_at=_NOW - timedelta(hours=2),
                expires_at=_NOW - timedelta(hours=1),
            ),
        )

        with _patch_now():
            result = await store.list_by_user("user-1")
        assert len(result) == 1
        assert result[0].session_id == "s1"

    async def test_list_all(self, store: SessionStore) -> None:
        await store.create(_make_session(session_id="s1"))
        await store.create(
            _make_session(
                session_id="s2",
                user_id="user-2",
                username="bob",
                role=HumanRole.MANAGER,
            ),
        )

        result = await store.list_all()
        assert len(result) == 2


class TestSessionStoreRevoke:
    async def test_revoke_marks_session(
        self,
        store: SessionStore,
    ) -> None:
        await store.create(_make_session())
        assert store.is_revoked("sess-1") is False

        result = await store.revoke("sess-1")
        assert result is True
        assert store.is_revoked("sess-1") is True

    async def test_revoke_nonexistent_returns_false(
        self,
        store: SessionStore,
    ) -> None:
        result = await store.revoke("nonexistent")
        assert result is False

    async def test_revoke_already_revoked_returns_false(
        self,
        store: SessionStore,
    ) -> None:
        await store.create(_make_session())
        await store.revoke("sess-1")
        result = await store.revoke("sess-1")
        assert result is False

    async def test_revoke_all_for_user(
        self,
        store: SessionStore,
    ) -> None:
        await store.create(_make_session(session_id="s1"))
        await store.create(_make_session(session_id="s2"))
        await store.create(
            _make_session(
                session_id="s3",
                user_id="user-2",
                username="bob",
                role=HumanRole.MANAGER,
            ),
        )

        count = await store.revoke_all_for_user("user-1")
        assert count == 2
        assert store.is_revoked("s1") is True
        assert store.is_revoked("s2") is True
        assert store.is_revoked("s3") is False

    async def test_revoke_all_for_user_with_no_sessions(
        self,
        store: SessionStore,
    ) -> None:
        count = await store.revoke_all_for_user("user-1")
        assert count == 0

    async def test_is_revoked_sync(
        self,
        store: SessionStore,
    ) -> None:
        """is_revoked is sync and O(1) for the middleware hot path."""
        await store.create(_make_session())
        assert store.is_revoked("sess-1") is False
        await store.revoke("sess-1")
        assert store.is_revoked("sess-1") is True


class TestSessionStoreCleanup:
    async def test_cleanup_expired(
        self,
        store: SessionStore,
    ) -> None:
        await store.create(
            _make_session(
                session_id="expired",
                created_at=_NOW - timedelta(hours=2),
                expires_at=_NOW - timedelta(hours=1),
            ),
        )
        await store.create(_make_session(session_id="active"))

        with _patch_now():
            removed = await store.cleanup_expired()
        assert removed == 1
        assert await store.get("expired") is None
        assert await store.get("active") is not None

    async def test_cleanup_clears_revocation_set(
        self,
        store: SessionStore,
    ) -> None:
        await store.create(
            _make_session(
                session_id="expired",
                created_at=_NOW - timedelta(hours=2),
                expires_at=_NOW - timedelta(hours=1),
            ),
        )
        await store.revoke("expired")
        assert store.is_revoked("expired") is True

        with _patch_now():
            await store.cleanup_expired()
        # Revocation entry cleared since JWT is past expiry.
        assert store.is_revoked("expired") is False


class TestSessionStoreLoadRevoked:
    async def test_load_revoked_restores_state(
        self,
        db: aiosqlite.Connection,
    ) -> None:
        """Revocations survive store recreation (simulates restart)."""
        store1 = SessionStore(db)
        await store1.load_revoked()
        await store1.create(_make_session())
        await store1.revoke("sess-1")

        # Create a new store (simulates restart).
        store2 = SessionStore(db)
        assert store2.is_revoked("sess-1") is False
        await store2.load_revoked()
        assert store2.is_revoked("sess-1") is True
