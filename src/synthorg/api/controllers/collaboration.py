"""Collaboration scoring controller — overrides and calibration data."""

from datetime import UTC, datetime, timedelta

from litestar import Controller, delete, get, post
from litestar.datastructures import State  # noqa: TC002
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from synthorg.api.dto import ApiResponse
from synthorg.api.errors import NotFoundError
from synthorg.api.guards import require_read_access, require_write_access
from synthorg.api.state import AppState  # noqa: TC001
from synthorg.core.types import NotBlankStr
from synthorg.hr.performance.models import (
    CollaborationOverride,
    CollaborationScoreResult,
    LlmCalibrationRecord,
)
from synthorg.observability import get_logger

logger = get_logger(__name__)


# ── Request/Response DTOs ────────────────────────────────────


class SetOverrideRequest(BaseModel):
    """Request body for setting a collaboration score override.

    Attributes:
        score: Override score (0.0-10.0).
        reason: Why the override is being applied.
        expires_in_days: Optional expiration in days (None = indefinite).
    """

    model_config = ConfigDict(frozen=True)

    score: float = Field(ge=0.0, le=10.0, description="Override score")
    reason: NotBlankStr = Field(
        max_length=4096,
        description="Reason for the override",
    )
    expires_in_days: int | None = Field(
        default=None,
        ge=1,
        le=365,
        description="Expiration in days (None = indefinite)",
    )


class OverrideResponse(BaseModel):
    """Response body with override details.

    Attributes:
        agent_id: Agent whose score is overridden.
        score: Override score.
        reason: Why the override was applied.
        applied_by: Who applied the override.
        applied_at: When the override was applied.
        expires_at: When the override expires.
    """

    model_config = ConfigDict(frozen=True)

    agent_id: NotBlankStr
    score: float = Field(ge=0.0, le=10.0)
    reason: NotBlankStr
    applied_by: NotBlankStr
    applied_at: AwareDatetime
    expires_at: AwareDatetime | None


class CalibrationSummaryResponse(BaseModel):
    """Response body with LLM calibration data.

    Attributes:
        agent_id: Agent being calibrated.
        record_count: Number of calibration records.
        average_drift: Average score drift (None if no records).
        records: Calibration records.
    """

    model_config = ConfigDict(frozen=True)

    agent_id: NotBlankStr
    record_count: int = Field(ge=0)
    average_drift: float | None = Field(default=None, ge=0.0)
    records: tuple[LlmCalibrationRecord, ...] = ()


# ── Controller ───────────────────────────────────────────────


class CollaborationController(Controller):
    """Collaboration scoring overrides and calibration data."""

    path = "/agents/{agent_id:str}/collaboration"
    tags = ("collaboration",)

    @get("/score", guards=[require_read_access])
    async def get_score(
        self,
        state: State,
        agent_id: str,
    ) -> ApiResponse[CollaborationScoreResult]:
        """Get current collaboration score (with override if active).

        Args:
            state: Application state.
            agent_id: Agent identifier.

        Returns:
            Collaboration score result.
        """
        app_state: AppState = state.app_state
        tracker = app_state.performance_tracker
        return ApiResponse(
            data=await tracker.get_collaboration_score(
                NotBlankStr(agent_id),
            ),
        )

    @get("/override", guards=[require_read_access])
    async def get_override(
        self,
        state: State,
        agent_id: str,
    ) -> ApiResponse[OverrideResponse]:
        """Get the active override for an agent.

        Args:
            state: Application state.
            agent_id: Agent identifier.

        Returns:
            Override details.

        Raises:
            NotFoundError: If no active override exists.
        """
        app_state: AppState = state.app_state
        tracker = app_state.performance_tracker
        store = tracker.override_store
        if store is None:
            msg = f"No override found for agent {agent_id!r}"
            raise NotFoundError(msg)

        override = store.get_active_override(NotBlankStr(agent_id))
        if override is None:
            msg = f"No active override for agent {agent_id!r}"
            raise NotFoundError(msg)

        return ApiResponse(
            data=OverrideResponse(
                agent_id=override.agent_id,
                score=override.score,
                reason=override.reason,
                applied_by=override.applied_by,
                applied_at=override.applied_at,
                expires_at=override.expires_at,
            ),
        )

    @post("/override", guards=[require_write_access], status_code=200)
    async def set_override(
        self,
        state: State,
        agent_id: str,
        data: SetOverrideRequest,
    ) -> ApiResponse[OverrideResponse]:
        """Set a collaboration score override for an agent.

        Args:
            state: Application state.
            agent_id: Agent identifier.
            data: Override request body.

        Returns:
            The created override.
        """
        app_state: AppState = state.app_state
        tracker = app_state.performance_tracker

        store = tracker.override_store
        if store is None:
            msg = "Override store not configured on tracker"
            raise NotFoundError(msg)

        now = datetime.now(UTC)
        expires_at = (
            now + timedelta(days=data.expires_in_days)
            if data.expires_in_days is not None
            else None
        )

        # Extract user identity from connection scope.
        applied_by = "unknown"
        scope = state._connection.scope if hasattr(state, "_connection") else {}  # noqa: SLF001
        user = scope.get("user")
        if user is not None and hasattr(user, "sub"):
            applied_by = str(user.sub)

        override = CollaborationOverride(
            agent_id=NotBlankStr(agent_id),
            score=data.score,
            reason=data.reason,
            applied_by=NotBlankStr(applied_by),
            applied_at=now,
            expires_at=expires_at,
        )
        store.set_override(override)

        return ApiResponse(
            data=OverrideResponse(
                agent_id=override.agent_id,
                score=override.score,
                reason=override.reason,
                applied_by=override.applied_by,
                applied_at=override.applied_at,
                expires_at=override.expires_at,
            ),
        )

    @delete("/override", guards=[require_write_access], status_code=200)
    async def clear_override(
        self,
        state: State,
        agent_id: str,
    ) -> ApiResponse[None]:
        """Clear the active override for an agent.

        Args:
            state: Application state.
            agent_id: Agent identifier.

        Returns:
            Empty success response.

        Raises:
            NotFoundError: If no override exists to clear.
        """
        app_state: AppState = state.app_state
        tracker = app_state.performance_tracker
        store = tracker.override_store
        if store is None:
            msg = f"No override found for agent {agent_id!r}"
            raise NotFoundError(msg)

        removed = store.clear_override(NotBlankStr(agent_id))
        if not removed:
            msg = f"No override to clear for agent {agent_id!r}"
            raise NotFoundError(msg)

        return ApiResponse(data=None)

    @get("/calibration", guards=[require_read_access])
    async def get_calibration(
        self,
        state: State,
        agent_id: str,
    ) -> ApiResponse[CalibrationSummaryResponse]:
        """Get LLM calibration records and drift summary.

        Args:
            state: Application state.
            agent_id: Agent identifier.

        Returns:
            Calibration summary with records and drift.
        """
        app_state: AppState = state.app_state
        tracker = app_state.performance_tracker
        agent_nb = NotBlankStr(agent_id)

        records: tuple[LlmCalibrationRecord, ...] = ()
        average_drift: float | None = None

        if tracker.sampler is not None:
            records = tracker.sampler.get_calibration_records(
                agent_id=agent_nb,
            )
            average_drift = tracker.sampler.get_drift_summary(agent_nb)

        return ApiResponse(
            data=CalibrationSummaryResponse(
                agent_id=agent_nb,
                record_count=len(records),
                average_drift=average_drift,
                records=records,
            ),
        )
