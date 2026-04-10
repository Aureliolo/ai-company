"""Telemetry collector -- gathers curated metrics from runtime."""

import asyncio
import contextlib
import os
import platform
import sys
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from synthorg.observability import get_logger
from synthorg.observability.events.telemetry import (
    TELEMETRY_DISABLED,
    TELEMETRY_ENABLED,
    TELEMETRY_EVENT_DEPLOYMENT_HEARTBEAT,
    TELEMETRY_EVENT_DEPLOYMENT_SESSION_SUMMARY,
    TELEMETRY_EVENT_DEPLOYMENT_SHUTDOWN,
    TELEMETRY_EVENT_DEPLOYMENT_STARTUP,
    TELEMETRY_HEARTBEAT_SENT,
    TELEMETRY_REPORT_FAILED,
    TELEMETRY_SESSION_SUMMARY_SENT,
)
from synthorg.telemetry.privacy import PrivacyScrubber, PrivacyViolationError
from synthorg.telemetry.protocol import TelemetryEvent, TelemetryReporter
from synthorg.telemetry.reporters import create_reporter

if TYPE_CHECKING:
    from pathlib import Path

    from synthorg.telemetry.config import TelemetryConfig

logger = get_logger(__name__)


@dataclass(frozen=True)
class _HeartbeatParams:
    """Parameter bundle for heartbeat events."""

    agent_count: int = 0
    department_count: int = 0
    team_count: int = 0
    template_name: str = ""
    persistence_backend: str = "sqlite"
    memory_backend: str = "mem0"
    features_enabled: str = ""


@dataclass(frozen=True)
class _SessionSummaryParams:
    """Parameter bundle for session summary events."""

    tasks_created: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    error_rate_limit: int = 0
    error_timeout: int = 0
    error_connection: int = 0
    error_internal: int = 0
    error_validation: int = 0
    error_other: int = 0
    provider_count: int = 0
    topology_hierarchical: int = 0
    topology_parallel: int = 0
    topology_sequential: int = 0
    topology_auto: int = 0
    meetings_held: int = 0
    delegations_executed: int = 0


HeartbeatSnapshotProvider = Callable[[], _HeartbeatParams]
SessionSummarySnapshotProvider = Callable[[], _SessionSummaryParams]


class TelemetryCollector:
    """Gathers curated metrics and sends via the reporter.

    The collector is the single entry point for all telemetry.  It:

    1. Reads opt-in config (env var > config file).
    2. Creates the appropriate reporter (noop when disabled).
    3. Validates every event through ``PrivacyScrubber``.
    4. Manages the heartbeat schedule.
    5. Sends a session summary on shutdown.

    Args:
        config: Telemetry configuration.
        data_dir: Directory to persist the anonymous deployment ID.
        heartbeat_snapshot_provider: Optional callable returning the
            current ``_HeartbeatParams`` snapshot.  Used by the
            internal heartbeat loop so emitted events contain real
            runtime metrics instead of zero defaults.
        session_summary_snapshot_provider: Optional callable returning
            the current ``_SessionSummaryParams`` snapshot.  Used by
            ``shutdown()`` to emit aggregated session metrics.
    """

    def __init__(
        self,
        config: TelemetryConfig,
        data_dir: Path,
        heartbeat_snapshot_provider: HeartbeatSnapshotProvider | None = None,
        session_summary_snapshot_provider: SessionSummarySnapshotProvider | None = None,
    ) -> None:
        # Env var overrides config file (documented priority).
        env_val = os.environ.get("SYNTHORG_TELEMETRY", "").strip().lower()
        if env_val in ("true", "1", "yes"):
            config = config.model_copy(update={"enabled": True})
        elif env_val in ("false", "0", "no"):
            config = config.model_copy(update={"enabled": False})
        elif env_val:
            logger.warning(
                TELEMETRY_REPORT_FAILED,
                detail="invalid_env_value",
                error_code="SYNTHORG_TELEMETRY_INVALID",
            )

        self._config = config
        self._data_dir = data_dir
        self._scrubber = PrivacyScrubber()
        self._reporter: TelemetryReporter = create_reporter(config)
        self._deployment_id: str | None = None
        self._started_at = datetime.now(UTC)
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._heartbeat_snapshot_provider = heartbeat_snapshot_provider
        self._session_summary_snapshot_provider = session_summary_snapshot_provider
        self._lifecycle_lock = asyncio.Lock()

        if config.enabled:
            # Persist deployment ID only after consent is given.
            self._deployment_id = self._load_or_create_deployment_id()
            logger.info(
                TELEMETRY_ENABLED,
                backend=config.backend.value,
                deployment_id=self._deployment_id,
            )
        else:
            logger.debug(TELEMETRY_DISABLED)

    @property
    def deployment_id(self) -> str | None:
        """The anonymous deployment UUID, or ``None`` when disabled."""
        return self._deployment_id

    @property
    def enabled(self) -> bool:
        """Whether telemetry is enabled."""
        return self._config.enabled

    async def start(self) -> None:
        """Start the periodic heartbeat if telemetry is enabled.

        Idempotent and safe under concurrent callers: serialised by
        a lifecycle lock so the guard check, startup event, and
        heartbeat task creation happen atomically.
        """
        async with self._lifecycle_lock:
            if not self._config.enabled:
                return
            if self._heartbeat_task is not None and not self._heartbeat_task.done():
                return
            await self._send_startup_event()
            self._heartbeat_task = asyncio.create_task(
                self._heartbeat_loop(),
                name="telemetry-heartbeat",
            )

    async def shutdown(self) -> None:
        """Cancel heartbeat, send session summary, shut down reporter.

        Each step is wrapped in its own try/except so a failure in
        one stage never aborts the rest of the cleanup sequence.
        Serialised with ``start()`` via the lifecycle lock.
        """
        async with self._lifecycle_lock:
            if self._heartbeat_task is not None:
                self._heartbeat_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._heartbeat_task
                self._heartbeat_task = None

            if self._config.enabled:
                params: _SessionSummaryParams | None = None
                if self._session_summary_snapshot_provider is not None:
                    try:
                        params = self._session_summary_snapshot_provider()
                    except Exception as exc:
                        logger.warning(
                            TELEMETRY_REPORT_FAILED,
                            detail="session_summary_snapshot_failed",
                            error_type=type(exc).__name__,
                        )

                try:
                    await self.send_session_summary(params)
                except Exception as exc:
                    logger.warning(
                        TELEMETRY_REPORT_FAILED,
                        detail="send_session_summary_failed",
                        error_type=type(exc).__name__,
                    )

                try:
                    await self._send_shutdown_event()
                except Exception as exc:
                    logger.warning(
                        TELEMETRY_REPORT_FAILED,
                        detail="send_shutdown_event_failed",
                        error_type=type(exc).__name__,
                    )

            try:
                await self._reporter.shutdown()
            except Exception as exc:
                logger.warning(
                    TELEMETRY_REPORT_FAILED,
                    detail="reporter_shutdown_failed",
                    error_type=type(exc).__name__,
                )

    async def send_heartbeat(
        self,
        params: _HeartbeatParams | None = None,
    ) -> None:
        """Send a heartbeat event with current deployment metrics."""
        if not self._config.enabled:
            return
        p = params or _HeartbeatParams()
        uptime = self._uptime_hours()

        event = self._build_event(
            TELEMETRY_EVENT_DEPLOYMENT_HEARTBEAT,
            agent_count=p.agent_count,
            department_count=p.department_count,
            team_count=p.team_count,
            template_name=p.template_name,
            persistence_backend=p.persistence_backend,
            memory_backend=p.memory_backend,
            features_enabled=p.features_enabled,
            uptime_hours=round(uptime, 2),
        )
        if await self._send(event):
            logger.debug(TELEMETRY_HEARTBEAT_SENT)

    async def send_session_summary(
        self,
        params: _SessionSummaryParams | None = None,
    ) -> None:
        """Send a session summary event with aggregate metrics."""
        if not self._config.enabled:
            return
        p = params or _SessionSummaryParams()
        uptime = self._uptime_hours()

        event = self._build_event(
            TELEMETRY_EVENT_DEPLOYMENT_SESSION_SUMMARY,
            tasks_created=p.tasks_created,
            tasks_completed=p.tasks_completed,
            tasks_failed=p.tasks_failed,
            error_rate_limit=p.error_rate_limit,
            error_timeout=p.error_timeout,
            error_connection=p.error_connection,
            error_internal=p.error_internal,
            error_validation=p.error_validation,
            error_other=p.error_other,
            provider_count=p.provider_count,
            topology_hierarchical=p.topology_hierarchical,
            topology_parallel=p.topology_parallel,
            topology_sequential=p.topology_sequential,
            topology_auto=p.topology_auto,
            meetings_held=p.meetings_held,
            delegations_executed=p.delegations_executed,
            uptime_hours=round(uptime, 2),
        )
        if await self._send(event):
            logger.debug(TELEMETRY_SESSION_SUMMARY_SENT)

    def _uptime_hours(self) -> float:
        """Return elapsed hours since collector was initialised."""
        delta = datetime.now(UTC) - self._started_at
        return delta.total_seconds() / 3600

    def _build_event(
        self,
        event_type: str,
        **properties: int | float | str | bool,
    ) -> TelemetryEvent:
        """Construct a ``TelemetryEvent`` with runtime metadata.

        Only called when telemetry is enabled (deployment ID is set).
        """
        assert self._deployment_id is not None  # noqa: S101
        vi = sys.version_info
        return TelemetryEvent(
            event_type=event_type,
            deployment_id=self._deployment_id,
            synthorg_version=_get_version(),
            python_version=f"{vi.major}.{vi.minor}.{vi.micro}",
            os_platform=platform.system(),
            timestamp=datetime.now(UTC),
            properties=properties,
        )

    async def _send(self, event: TelemetryEvent) -> bool:
        """Validate and send a telemetry event.

        Logs and drops events that fail privacy validation.
        Logs and suppresses reporter errors (telemetry must not
        affect the main application).

        Returns:
            ``True`` if the event was delivered, ``False`` otherwise.
        """
        try:
            self._scrubber.validate(event)
        except PrivacyViolationError as exc:
            logger.warning(
                TELEMETRY_REPORT_FAILED,
                event_type=event.event_type,
                detail="privacy_violation",
                error_type=type(exc).__name__,
                error_code="PRIVACY_VIOLATION",
            )
            return False

        try:
            await self._reporter.report(event)
        except Exception as exc:
            logger.warning(
                TELEMETRY_REPORT_FAILED,
                event_type=event.event_type,
                error_type=type(exc).__name__,
                error_code="REPORTER_BACKEND_FAILURE",
            )
            return False

        return True

    async def _send_startup_event(self) -> None:
        """Send an initial deployment.startup event."""
        event = self._build_event(
            TELEMETRY_EVENT_DEPLOYMENT_STARTUP,
            agent_count=0,
            department_count=0,
            template_name="",
            persistence_backend="sqlite",
            memory_backend="mem0",
        )
        await self._send(event)

    async def _send_shutdown_event(self) -> None:
        """Send a deployment.shutdown event with uptime."""
        event = self._build_event(
            TELEMETRY_EVENT_DEPLOYMENT_SHUTDOWN,
            uptime_hours=round(self._uptime_hours(), 2),
            graceful=True,
        )
        await self._send(event)

    async def _heartbeat_loop(self) -> None:
        """Periodically send heartbeat events until cancelled.

        Catches and logs non-cancellation exceptions so the loop
        continues on transient failures.  ``CancelledError`` is
        re-raised for graceful shutdown.
        """
        interval = self._config.heartbeat_interval_hours * 3600
        while True:
            try:
                await asyncio.sleep(interval)
                params = (
                    self._heartbeat_snapshot_provider()
                    if self._heartbeat_snapshot_provider is not None
                    else None
                )
                await self.send_heartbeat(params)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(
                    TELEMETRY_REPORT_FAILED,
                    detail="heartbeat_loop",
                    error_type=type(exc).__name__,
                )

    def _load_or_create_deployment_id(self) -> str:
        """Load deployment ID from file or create a new UUID.

        Returns a valid UUID string in all cases (never raises).
        Logs warnings on I/O errors.
        """
        id_file = self._data_dir / "telemetry_id"
        try:
            if id_file.exists():
                stored = id_file.read_text(encoding="utf-8").strip()
                if stored:
                    try:
                        uuid.UUID(stored)
                    except ValueError:
                        logger.warning(
                            TELEMETRY_REPORT_FAILED,
                            detail="deployment_id_invalid",
                            error_type="ValueError",
                        )
                    else:
                        return stored
        except OSError as exc:
            logger.warning(
                TELEMETRY_REPORT_FAILED,
                detail="deployment_id_read",
                error_type=type(exc).__name__,
            )

        new_id = str(uuid.uuid4())
        try:
            id_file.parent.mkdir(parents=True, exist_ok=True)
            id_file.write_text(new_id, encoding="utf-8")
            id_file.chmod(0o600)
        except OSError as exc:
            logger.warning(
                TELEMETRY_REPORT_FAILED,
                detail="deployment_id_write",
                error_type=type(exc).__name__,
            )
        return new_id


def _get_version() -> str:
    try:
        import synthorg  # noqa: PLC0415
    except ImportError:
        return "unknown"

    try:
        return synthorg.__version__
    except AttributeError:
        logger.warning(
            TELEMETRY_REPORT_FAILED,
            detail="version_attribute_missing",
        )
        return "unknown"
