"""Tests for CollaborationOverrideStore."""

from datetime import UTC, datetime, timedelta

import pytest

from synthorg.core.types import NotBlankStr
from synthorg.hr.performance.collaboration_override_store import (
    CollaborationOverrideStore,
)
from synthorg.hr.performance.models import CollaborationOverride

NOW = datetime(2026, 3, 15, 12, 0, 0, tzinfo=UTC)


def _make_override(  # noqa: PLR0913
    *,
    agent_id: str = "agent-001",
    score: float = 8.0,
    reason: str = "Exceptional mentoring",
    applied_by: str = "manager-alice",
    applied_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> CollaborationOverride:
    return CollaborationOverride(
        agent_id=NotBlankStr(agent_id),
        score=score,
        reason=NotBlankStr(reason),
        applied_by=NotBlankStr(applied_by),
        applied_at=applied_at or NOW,
        expires_at=expires_at,
    )


@pytest.mark.unit
class TestSetOverride:
    """Setting overrides in the store."""

    def test_set_and_retrieve(self) -> None:
        """Setting an override makes it retrievable."""
        store = CollaborationOverrideStore()
        override = _make_override()

        store.set_override(override)
        result = store.get_active_override(
            NotBlankStr("agent-001"),
            now=NOW,
        )

        assert result is not None
        assert result.score == 8.0
        assert result.agent_id == "agent-001"

    def test_replace_existing(self) -> None:
        """Setting a new override replaces the previous one."""
        store = CollaborationOverrideStore()
        store.set_override(_make_override(score=7.0))
        store.set_override(_make_override(score=9.0))

        result = store.get_active_override(
            NotBlankStr("agent-001"),
            now=NOW,
        )

        assert result is not None
        assert result.score == 9.0

    def test_different_agents_independent(self) -> None:
        """Overrides for different agents are independent."""
        store = CollaborationOverrideStore()
        store.set_override(_make_override(agent_id="agent-001", score=7.0))
        store.set_override(_make_override(agent_id="agent-002", score=9.0))

        r1 = store.get_active_override(NotBlankStr("agent-001"), now=NOW)
        r2 = store.get_active_override(NotBlankStr("agent-002"), now=NOW)

        assert r1 is not None
        assert r1.score == 7.0
        assert r2 is not None
        assert r2.score == 9.0


@pytest.mark.unit
class TestGetActiveOverride:
    """Retrieving active overrides with expiration handling."""

    def test_no_override_returns_none(self) -> None:
        """Missing override returns None."""
        store = CollaborationOverrideStore()

        result = store.get_active_override(
            NotBlankStr("agent-001"),
            now=NOW,
        )

        assert result is None

    def test_expired_override_returns_none(self) -> None:
        """Expired override is treated as inactive."""
        store = CollaborationOverrideStore()
        # Override was applied 2 hours ago, expired 1 hour ago.
        expired = _make_override(
            applied_at=NOW - timedelta(hours=2),
            expires_at=NOW - timedelta(hours=1),
        )
        store.set_override(expired)

        result = store.get_active_override(
            NotBlankStr("agent-001"),
            now=NOW,
        )

        assert result is None

    def test_not_yet_expired_returns_override(self) -> None:
        """Override with future expiration is active."""
        store = CollaborationOverrideStore()
        future = _make_override(
            expires_at=NOW + timedelta(days=7),
        )
        store.set_override(future)

        result = store.get_active_override(
            NotBlankStr("agent-001"),
            now=NOW,
        )

        assert result is not None
        assert result.score == 8.0

    def test_no_expiration_always_active(self) -> None:
        """Override without expires_at is always active."""
        store = CollaborationOverrideStore()
        store.set_override(_make_override(expires_at=None))

        result = store.get_active_override(
            NotBlankStr("agent-001"),
            now=NOW,
        )

        assert result is not None

    def test_default_now_uses_current_time(self) -> None:
        """Omitting now= uses the current time."""
        store = CollaborationOverrideStore()
        store.set_override(
            _make_override(expires_at=NOW + timedelta(days=365)),
        )

        result = store.get_active_override(NotBlankStr("agent-001"))

        assert result is not None


@pytest.mark.unit
class TestClearOverride:
    """Clearing overrides."""

    def test_clear_existing(self) -> None:
        """Clearing an existing override returns True and removes it."""
        store = CollaborationOverrideStore()
        store.set_override(_make_override())

        removed = store.clear_override(NotBlankStr("agent-001"))

        assert removed is True
        assert (
            store.get_active_override(
                NotBlankStr("agent-001"),
                now=NOW,
            )
            is None
        )

    def test_clear_nonexistent(self) -> None:
        """Clearing a non-existent override returns False."""
        store = CollaborationOverrideStore()

        removed = store.clear_override(NotBlankStr("agent-001"))

        assert removed is False


@pytest.mark.unit
class TestListOverrides:
    """Listing overrides."""

    def test_empty_store(self) -> None:
        """Empty store returns empty tuple."""
        store = CollaborationOverrideStore()

        result = store.list_overrides(now=NOW)

        assert result == ()

    def test_excludes_expired_by_default(self) -> None:
        """Expired overrides are excluded by default."""
        store = CollaborationOverrideStore()
        store.set_override(
            _make_override(
                agent_id="agent-001",
                applied_at=NOW - timedelta(hours=2),
                expires_at=NOW - timedelta(hours=1),
            ),
        )
        store.set_override(
            _make_override(agent_id="agent-002", expires_at=None),
        )

        result = store.list_overrides(now=NOW)

        assert len(result) == 1
        assert result[0].agent_id == "agent-002"

    def test_includes_expired_when_requested(self) -> None:
        """include_expired=True returns all overrides."""
        store = CollaborationOverrideStore()
        store.set_override(
            _make_override(
                agent_id="agent-001",
                applied_at=NOW - timedelta(hours=2),
                expires_at=NOW - timedelta(hours=1),
            ),
        )
        store.set_override(
            _make_override(agent_id="agent-002", expires_at=None),
        )

        result = store.list_overrides(include_expired=True, now=NOW)

        assert len(result) == 2
