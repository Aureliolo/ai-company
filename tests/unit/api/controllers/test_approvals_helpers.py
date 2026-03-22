"""Tests for approvals controller helper functions."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from synthorg.api.controllers.approvals import (
    _log_approval_decision,
    _publish_approval_event,
    _resolve_decision,
    _signal_resume_intent,
)
from synthorg.api.errors import ConflictError, UnauthorizedError
from synthorg.api.state import AppState
from synthorg.core.approval import ApprovalItem
from synthorg.core.enums import ApprovalRiskLevel, ApprovalStatus

pytestmark = pytest.mark.unit


def _make_pending_item(approval_id: str = "approval-1") -> ApprovalItem:
    from datetime import UTC, datetime

    return ApprovalItem(
        id=approval_id,
        action_type="deploy:production",
        title="Deploy to prod",
        description="Deploy v2.0",
        requested_by="agent-1",
        risk_level=ApprovalRiskLevel.HIGH,
        status=ApprovalStatus.PENDING,
        created_at=datetime.now(UTC),
    )


def _make_request(*, user: object = None) -> MagicMock:
    request = MagicMock()
    request.scope = {"user": user}
    request.app.plugins = []
    return request


def _make_auth_user(username: str = "admin") -> MagicMock:
    from synthorg.api.auth.models import AuthenticatedUser

    user = MagicMock(spec=AuthenticatedUser)
    user.username = username
    return user


class TestResolveDecision:
    """_resolve_decision() pre-checks."""

    def test_raises_conflict_when_not_pending(self) -> None:
        request = _make_request(user=_make_auth_user())
        item = _make_pending_item().model_copy(
            update={"status": ApprovalStatus.APPROVED},
        )
        with pytest.raises(ConflictError, match="not pending"):
            _resolve_decision(request, item, "approval-1")

    def test_raises_unauthorized_when_no_user(self) -> None:
        request = _make_request(user=None)
        item = _make_pending_item()
        with pytest.raises(UnauthorizedError, match="Authentication"):
            _resolve_decision(request, item, "approval-1")

    def test_raises_unauthorized_when_wrong_user_type(self) -> None:
        request = _make_request(user="not-an-auth-user")
        item = _make_pending_item()
        with pytest.raises(UnauthorizedError, match="Authentication"):
            _resolve_decision(request, item, "approval-1")

    def test_returns_auth_user_when_valid(self) -> None:
        auth_user = _make_auth_user("ceo")
        request = _make_request(user=auth_user)
        item = _make_pending_item()
        result = _resolve_decision(request, item, "approval-1")
        assert result is auth_user


class TestLogApprovalDecision:
    """_log_approval_decision() logs correctly."""

    def test_logs_approved(self) -> None:
        # Should not raise
        _log_approval_decision(
            "approval-1",
            approved=True,
            decided_by="admin",
        )

    def test_logs_rejected(self) -> None:
        _log_approval_decision(
            "approval-1",
            approved=False,
            decided_by="reviewer",
        )


class TestSignalResumeIntent:
    """_signal_resume_intent() resume + review-gate dispatch."""

    async def test_no_gate_no_review_gate_is_noop(self) -> None:
        """When both gates are None, function is a no-op."""
        app_state = MagicMock(spec=AppState)
        app_state.approval_gate = None
        app_state.review_gate_service = None
        await _signal_resume_intent(
            app_state,
            "approval-1",
            approved=True,
            decided_by="admin",
        )

    async def test_flow1_parked_context_found_returns_early(self) -> None:
        """When resume_context returns a context, Flow 2 is skipped."""
        mock_context = MagicMock()
        mock_gate = MagicMock()
        mock_gate.resume_context = AsyncMock(
            return_value=(mock_context, "parked-1"),
        )
        mock_review = MagicMock()
        mock_review.complete_review = AsyncMock()

        app_state = MagicMock(spec=AppState)
        app_state.approval_gate = mock_gate
        app_state.review_gate_service = mock_review

        await _signal_resume_intent(
            app_state,
            "approval-1",
            approved=True,
            decided_by="admin",
            task_id="task-1",
        )

        mock_gate.resume_context.assert_awaited_once_with("approval-1")
        # Flow 2 should NOT be called
        mock_review.complete_review.assert_not_awaited()

    async def test_flow1_no_parked_context_falls_through(self) -> None:
        """When resume_context returns None, Flow 2 runs."""
        mock_gate = MagicMock()
        mock_gate.resume_context = AsyncMock(return_value=None)
        mock_review = MagicMock()
        mock_review.complete_review = AsyncMock()

        app_state = MagicMock(spec=AppState)
        app_state.approval_gate = mock_gate
        app_state.review_gate_service = mock_review

        await _signal_resume_intent(
            app_state,
            "approval-1",
            approved=True,
            decided_by="admin",
            task_id="task-1",
        )

        mock_review.complete_review.assert_awaited_once_with(
            task_id="task-1",
            requested_by="admin",
            approved=True,
            decided_by="admin",
            reason=None,
        )

    async def test_flow1_exception_returns_early(self) -> None:
        """When resume_context raises, function returns early (no fall-through)."""
        mock_gate = MagicMock()
        mock_gate.resume_context = AsyncMock(
            side_effect=RuntimeError("db error"),
        )
        mock_review = MagicMock()
        mock_review.complete_review = AsyncMock()

        app_state = MagicMock(spec=AppState)
        app_state.approval_gate = mock_gate
        app_state.review_gate_service = mock_review

        await _signal_resume_intent(
            app_state,
            "approval-1",
            approved=True,
            decided_by="admin",
            task_id="task-1",
        )

        # Flow 2 should NOT run -- resume error means parked context
        # may still exist, so review gate transition is unsafe.
        mock_review.complete_review.assert_not_awaited()

    async def test_flow2_review_gate_called_with_task_id(self) -> None:
        """When no approval_gate and task_id provided, review gate runs."""
        mock_review = MagicMock()
        mock_review.complete_review = AsyncMock()

        app_state = MagicMock(spec=AppState)
        app_state.approval_gate = None
        app_state.review_gate_service = mock_review

        await _signal_resume_intent(
            app_state,
            "approval-1",
            approved=False,
            decided_by="reviewer",
            decision_reason="Needs rework",
            task_id="task-42",
        )

        mock_review.complete_review.assert_awaited_once_with(
            task_id="task-42",
            requested_by="reviewer",
            approved=False,
            decided_by="reviewer",
            reason="Needs rework",
        )

    async def test_flow2_skipped_when_no_task_id(self) -> None:
        """When task_id is None, review gate is not called."""
        mock_review = MagicMock()
        mock_review.complete_review = AsyncMock()

        app_state = MagicMock(spec=AppState)
        app_state.approval_gate = None
        app_state.review_gate_service = mock_review

        await _signal_resume_intent(
            app_state,
            "approval-1",
            approved=True,
            decided_by="admin",
            task_id=None,
        )

        mock_review.complete_review.assert_not_awaited()

    async def test_flow2_exception_swallowed(self) -> None:
        """Errors from review gate are logged and swallowed."""
        mock_review = MagicMock()
        mock_review.complete_review = AsyncMock(
            side_effect=RuntimeError("transition failed"),
        )

        app_state = MagicMock(spec=AppState)
        app_state.approval_gate = None
        app_state.review_gate_service = mock_review

        # Should not raise
        await _signal_resume_intent(
            app_state,
            "approval-1",
            approved=True,
            decided_by="admin",
            task_id="task-1",
        )

        mock_review.complete_review.assert_awaited_once()

    @pytest.mark.parametrize(
        "error_cls",
        [MemoryError, RecursionError],
        ids=["MemoryError", "RecursionError"],
    )
    async def test_flow1_memory_error_propagates(
        self, error_cls: type[BaseException]
    ) -> None:
        """MemoryError/RecursionError from resume_context propagates."""
        mock_gate = MagicMock()
        mock_gate.resume_context = AsyncMock(
            side_effect=error_cls("fatal"),
        )

        app_state = MagicMock(spec=AppState)
        app_state.approval_gate = mock_gate
        app_state.review_gate_service = None

        with pytest.raises(error_cls):
            await _signal_resume_intent(
                app_state,
                "approval-1",
                approved=True,
                decided_by="admin",
            )

    @pytest.mark.parametrize(
        "error_cls",
        [MemoryError, RecursionError],
        ids=["MemoryError", "RecursionError"],
    )
    async def test_flow2_memory_error_propagates(
        self, error_cls: type[BaseException]
    ) -> None:
        """MemoryError/RecursionError from review gate propagates."""
        mock_review = MagicMock()
        mock_review.complete_review = AsyncMock(
            side_effect=error_cls("fatal"),
        )

        app_state = MagicMock(spec=AppState)
        app_state.approval_gate = None
        app_state.review_gate_service = mock_review

        with pytest.raises(error_cls):
            await _signal_resume_intent(
                app_state,
                "approval-1",
                approved=True,
                decided_by="admin",
                task_id="task-1",
            )


class TestPublishApprovalEvent:
    """_publish_approval_event() best-effort WebSocket publishing."""

    def test_logs_warning_when_no_channels_plugin(self) -> None:
        from synthorg.api.ws_models import WsEventType

        request = _make_request()
        request.app.plugins = []  # No ChannelsPlugin
        item = _make_pending_item()
        # Should not raise -- best-effort
        _publish_approval_event(
            request,
            WsEventType.APPROVAL_SUBMITTED,
            item,
        )

    def test_publishes_when_plugin_available(self) -> None:
        from litestar.channels import ChannelsPlugin

        from synthorg.api.ws_models import WsEventType

        plugin = MagicMock(spec=ChannelsPlugin)
        request = _make_request()
        request.app.plugins = [plugin]
        item = _make_pending_item()

        _publish_approval_event(
            request,
            WsEventType.APPROVAL_SUBMITTED,
            item,
        )
        plugin.publish.assert_called_once()

    def test_logs_warning_when_publish_fails(self) -> None:
        from litestar.channels import ChannelsPlugin

        from synthorg.api.ws_models import WsEventType

        plugin = MagicMock(spec=ChannelsPlugin)
        plugin.publish.side_effect = RuntimeError("not started")
        request = _make_request()
        request.app.plugins = [plugin]
        item = _make_pending_item()

        # Should not raise -- best-effort
        _publish_approval_event(
            request,
            WsEventType.APPROVAL_SUBMITTED,
            item,
        )
