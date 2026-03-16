"""Tests for CollaborationOverrideStore."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from synthorg.core.types import NotBlankStr
from synthorg.hr.performance.collaboration_override_store import (
    CollaborationOverrideStore,
)
from synthorg.hr.performance.models import CollaborationOverride

from .conftest import make_collaboration_override

NOW = datetime(2026, 3, 15, 12, 0, 0, tzinfo=UTC)


@pytest.mark.unit
class TestSetOverride:
    """Setting overrides in the store."""

    def test_set_and_retrieve(self) -> None:
        """Setting an override makes it retrievable."""
        store = CollaborationOverrideStore()
        override = make_collaboration_override(applied_at=NOW)

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
        store.set_override(make_collaboration_override(score=7.0, applied_at=NOW))
        store.set_override(make_collaboration_override(score=9.0, applied_at=NOW))

        result = store.get_active_override(
            NotBlankStr("agent-001"),
            now=NOW,
        )

        assert result is not None
        assert result.score == 9.0

    def test_different_agents_independent(self) -> None:
        """Overrides for different agents are independent."""
        store = CollaborationOverrideStore()
        store.set_override(
            make_collaboration_override(
                agent_id="agent-001",
                score=7.0,
                applied_at=NOW,
            ),
        )
        store.set_override(
            make_collaboration_override(
                agent_id="agent-002",
                score=9.0,
                applied_at=NOW,
            ),
        )

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
        expired = make_collaboration_override(
            applied_at=NOW - timedelta(hours=2),
            expires_at=NOW - timedelta(hours=1),
        )
        store.set_override(expired)

        result = store.get_active_override(
            NotBlankStr("agent-001"),
            now=NOW,
        )

        assert result is None

    def test_expired_override_evicted_from_store(self) -> None:
        """Expired overrides are removed from the internal dict."""
        store = CollaborationOverrideStore()
        expired = make_collaboration_override(
            applied_at=NOW - timedelta(hours=2),
            expires_at=NOW - timedelta(hours=1),
        )
        store.set_override(expired)

        # Query triggers eviction.
        store.get_active_override(NotBlankStr("agent-001"), now=NOW)

        # Verify the override is no longer in the store.
        assert store.list_overrides(include_expired=True) == ()

    def test_not_yet_expired_returns_override(self) -> None:
        """Override with future expiration is active."""
        store = CollaborationOverrideStore()
        future = make_collaboration_override(
            applied_at=NOW,
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
        store.set_override(
            make_collaboration_override(applied_at=NOW, expires_at=None),
        )

        result = store.get_active_override(
            NotBlankStr("agent-001"),
            now=NOW,
        )

        assert result is not None

    def test_default_now_uses_current_time(self) -> None:
        """Omitting now= uses the current time."""
        store = CollaborationOverrideStore()
        current_time = datetime.now(UTC)
        store.set_override(
            make_collaboration_override(
                applied_at=current_time,
                expires_at=current_time + timedelta(days=1),
            ),
        )

        result = store.get_active_override(NotBlankStr("agent-001"))

        assert result is not None


@pytest.mark.unit
class TestClearOverride:
    """Clearing overrides."""

    def test_clear_existing(self) -> None:
        """Clearing an active override returns True and removes it."""
        store = CollaborationOverrideStore()
        store.set_override(make_collaboration_override(applied_at=NOW))

        removed = store.clear_override(NotBlankStr("agent-001"), now=NOW)

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

        removed = store.clear_override(NotBlankStr("agent-001"), now=NOW)

        assert removed is False

    def test_clear_expired_returns_false(self) -> None:
        """Clearing an expired override returns False and evicts it."""
        store = CollaborationOverrideStore()
        store.set_override(
            make_collaboration_override(
                applied_at=NOW - timedelta(hours=2),
                expires_at=NOW - timedelta(hours=1),
            ),
        )

        removed = store.clear_override(NotBlankStr("agent-001"), now=NOW)

        assert removed is False
        # The expired entry should have been evicted.
        assert store.list_overrides(include_expired=True) == ()


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
            make_collaboration_override(
                agent_id="agent-001",
                applied_at=NOW - timedelta(hours=2),
                expires_at=NOW - timedelta(hours=1),
            ),
        )
        store.set_override(
            make_collaboration_override(
                agent_id="agent-002",
                applied_at=NOW,
                expires_at=None,
            ),
        )

        result = store.list_overrides(now=NOW)

        assert len(result) == 1
        assert result[0].agent_id == "agent-002"

    def test_includes_expired_when_requested(self) -> None:
        """include_expired=True returns all overrides."""
        store = CollaborationOverrideStore()
        store.set_override(
            make_collaboration_override(
                agent_id="agent-001",
                applied_at=NOW - timedelta(hours=2),
                expires_at=NOW - timedelta(hours=1),
            ),
        )
        store.set_override(
            make_collaboration_override(
                agent_id="agent-002",
                applied_at=NOW,
                expires_at=None,
            ),
        )

        result = store.list_overrides(include_expired=True, now=NOW)

        assert len(result) == 2


@pytest.mark.unit
class TestCollaborationOverrideModel:
    """Model-level tests for CollaborationOverride."""

    def test_expiration_before_applied_rejected(self) -> None:
        """Expires_at before applied_at raises ValidationError."""
        with pytest.raises(ValidationError, match=r"expires_at.*must be after"):
            CollaborationOverride(
                agent_id=NotBlankStr("agent-001"),
                score=5.0,
                reason=NotBlankStr("Test"),
                applied_by=NotBlankStr("manager"),
                applied_at=NOW,
                expires_at=NOW - timedelta(hours=1),
            )

    def test_expiration_equal_to_applied_rejected(self) -> None:
        """Expires_at equal to applied_at raises ValidationError."""
        with pytest.raises(ValidationError, match=r"expires_at.*must be after"):
            CollaborationOverride(
                agent_id=NotBlankStr("agent-001"),
                score=5.0,
                reason=NotBlankStr("Test"),
                applied_by=NotBlankStr("manager"),
                applied_at=NOW,
                expires_at=NOW,
            )

    def test_frozen_model(self) -> None:
        """CollaborationOverride is immutable."""
        override = make_collaboration_override(applied_at=NOW)
        with pytest.raises(ValidationError):
            override.score = 9.0  # type: ignore[misc]

    def test_score_range_enforced(self) -> None:
        """Score outside [0.0, 10.0] is rejected."""
        with pytest.raises(ValidationError):
            make_collaboration_override(score=11.0, applied_at=NOW)
        with pytest.raises(ValidationError):
            make_collaboration_override(score=-1.0, applied_at=NOW)
