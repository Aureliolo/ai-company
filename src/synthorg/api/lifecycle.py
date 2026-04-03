"""Lifecycle helpers for service startup and shutdown.

Contains ``_safe_startup`` (ordered startup with reverse cleanup on
failure), ``_safe_shutdown`` (graceful ordered teardown), and their
supporting helpers.
"""

from typing import TYPE_CHECKING

from synthorg.api.auth.secret import resolve_jwt_secret
from synthorg.api.auth.service import AuthService
from synthorg.api.auth.session_store import SessionStore
from synthorg.api.auth.system_user import ensure_system_user
from synthorg.backup.models import BackupTrigger
from synthorg.observability import get_logger
from synthorg.observability.events.api import API_APP_SHUTDOWN, API_APP_STARTUP
from synthorg.providers.health_prober import ProviderHealthProber

if TYPE_CHECKING:
    from collections.abc import Awaitable

    from synthorg.api.bus_bridge import MessageBusBridge
    from synthorg.api.state import AppState
    from synthorg.backup.service import BackupService
    from synthorg.communication.bus_protocol import MessageBus
    from synthorg.communication.meeting.scheduler import MeetingScheduler
    from synthorg.engine.task_engine import TaskEngine
    from synthorg.persistence.protocol import PersistenceBackend
    from synthorg.security.timeout.scheduler import ApprovalTimeoutScheduler
    from synthorg.settings.dispatcher import SettingsChangeDispatcher

logger = get_logger(__name__)


async def _try_stop(
    coro: Awaitable[None],
    event: str,
    error_msg: str,
) -> None:
    """Await *coro* inside a safe try/except, logging failures.

    ``MemoryError`` and ``RecursionError`` are re-raised immediately;
    all other exceptions are logged and swallowed so that sibling
    shutdown steps can still run.
    """
    try:
        await coro
    except MemoryError, RecursionError:
        raise
    except Exception:
        logger.exception(event, error=error_msg)


async def _cleanup_on_failure(  # noqa: PLR0913
    *,
    persistence: PersistenceBackend | None,
    started_persistence: bool,
    message_bus: MessageBus | None,
    started_bus: bool,
    bridge: MessageBusBridge | None = None,
    started_bridge: bool = False,
    settings_dispatcher: SettingsChangeDispatcher | None = None,
    started_settings_dispatcher: bool = False,
    task_engine: TaskEngine | None = None,
    started_task_engine: bool = False,
    meeting_scheduler: MeetingScheduler | None = None,
    started_meeting_scheduler: bool = False,
    backup_service: BackupService | None = None,
    started_backup_service: bool = False,
    approval_timeout_scheduler: ApprovalTimeoutScheduler | None = None,
    started_approval_timeout_scheduler: bool = False,
) -> None:
    """Reverse cleanup on startup failure."""
    if started_approval_timeout_scheduler and approval_timeout_scheduler is not None:
        await _try_stop(
            approval_timeout_scheduler.stop(),
            API_APP_STARTUP,
            "Cleanup: failed to stop approval timeout scheduler",
        )
    if started_backup_service and backup_service is not None:
        await _try_stop(
            backup_service.stop(),
            API_APP_STARTUP,
            "Cleanup: failed to stop backup service",
        )
    if started_meeting_scheduler and meeting_scheduler is not None:
        await _try_stop(
            meeting_scheduler.stop(),
            API_APP_STARTUP,
            "Cleanup: failed to stop meeting scheduler",
        )
    if started_task_engine and task_engine is not None:
        await _try_stop(
            task_engine.stop(),
            API_APP_STARTUP,
            "Cleanup: failed to stop task engine",
        )
    if started_settings_dispatcher and settings_dispatcher is not None:
        await _try_stop(
            settings_dispatcher.stop(),
            API_APP_STARTUP,
            "Cleanup: failed to stop settings dispatcher",
        )
    if started_bridge and bridge is not None:
        await _try_stop(
            bridge.stop(),
            API_APP_STARTUP,
            "Cleanup: failed to stop message bus bridge",
        )
    if started_bus and message_bus is not None:
        await _try_stop(
            message_bus.stop(),
            API_APP_STARTUP,
            "Cleanup: failed to stop message bus",
        )
    if started_persistence and persistence is not None:
        await _try_stop(
            persistence.disconnect(),
            API_APP_STARTUP,
            "Cleanup: failed to disconnect persistence",
        )


async def _init_persistence(
    persistence: PersistenceBackend,
    app_state: AppState,
) -> None:
    """Run migrations and resolve JWT secret on an already-connected backend.

    Must only be called after ``persistence.connect()`` has succeeded.

    Args:
        persistence: Connected persistence backend.
        app_state: Application state for auth service injection.
    """
    # Resolve JWT secret before migrations so missing env vars fail fast
    # (no point running migrations if startup will abort anyway).
    if app_state.has_auth_service:
        logger.info(
            API_APP_STARTUP,
            note="Auth service already configured, skipping JWT secret resolution",
        )
    else:
        try:
            secret = resolve_jwt_secret()
            auth_config = app_state.config.api.auth.with_secret(
                secret,
            )
            app_state.set_auth_service(AuthService(auth_config))
        except Exception:
            logger.exception(
                API_APP_STARTUP,
                error="Failed to resolve JWT secret",
            )
            raise

    try:
        await persistence.migrate()
    except Exception:
        logger.exception(
            API_APP_STARTUP,
            error="Failed to run persistence migrations",
        )
        raise


async def _safe_startup(  # noqa: PLR0913, PLR0912, PLR0915, C901
    persistence: PersistenceBackend | None,
    message_bus: MessageBus | None,
    bridge: MessageBusBridge | None,
    settings_dispatcher: SettingsChangeDispatcher | None,
    task_engine: TaskEngine | None,
    meeting_scheduler: MeetingScheduler | None,
    backup_service: BackupService | None,
    approval_timeout_scheduler: ApprovalTimeoutScheduler | None,
    app_state: AppState,
) -> None:
    """Start all services in order, with reverse cleanup on failure.

    Executes in order; on failure, cleans up already-started
    components in reverse order before re-raising.
    """
    started_bus = False
    started_bridge = False
    started_persistence = False
    started_settings_dispatcher = False
    started_task_engine = False
    started_meeting_scheduler = False
    started_backup_service = False
    started_approval_timeout_scheduler = False
    try:
        if persistence is not None:
            try:
                await persistence.connect()
            except Exception:
                logger.exception(
                    API_APP_STARTUP,
                    error="Failed to connect persistence",
                )
                raise
            # Mark connected immediately so cleanup can disconnect
            # if migrate() or JWT resolution fails below.
            started_persistence = True
            await _init_persistence(persistence, app_state)
            try:
                await ensure_system_user(persistence, app_state.auth_service)
            except Exception:
                logger.exception(
                    API_APP_STARTUP,
                    error="Failed to bootstrap system user",
                )
                raise

            # Session store shares the persistence db connection.
            try:
                db = persistence.get_db()
            except NotImplementedError:
                logger.info(
                    API_APP_STARTUP,
                    note="Persistence backend does not expose raw DB; "
                    "session store disabled",
                )
            else:
                session_store = SessionStore(db)
                await session_store.load_revoked()
                app_state.set_session_store(session_store)
                logger.info(
                    API_APP_STARTUP,
                    note="Session store initialized",
                )

        if message_bus is not None:
            try:
                await message_bus.start()
            except Exception:
                logger.exception(
                    API_APP_STARTUP,
                    error="Failed to start message bus",
                )
                raise
            started_bus = True
        if bridge is not None:
            try:
                await bridge.start()
            except Exception:
                logger.exception(
                    API_APP_STARTUP,
                    error="Failed to start message bus bridge",
                )
                raise
            started_bridge = True
        if settings_dispatcher is not None:
            try:
                await settings_dispatcher.start()
            except Exception:
                logger.exception(
                    API_APP_STARTUP,
                    error="Failed to start settings dispatcher",
                )
                raise
            started_settings_dispatcher = True
        if task_engine is not None:
            try:
                task_engine.start()
            except Exception:
                logger.exception(
                    API_APP_STARTUP,
                    error="Failed to start task engine",
                )
                raise
            started_task_engine = True
        if meeting_scheduler is not None:
            try:
                await meeting_scheduler.start()
            except Exception:
                logger.exception(
                    API_APP_STARTUP,
                    error="Failed to start meeting scheduler",
                )
                raise
            started_meeting_scheduler = True
        if backup_service is not None:
            try:
                app_state.set_backup_service(backup_service)
                started_backup_service = True
                await backup_service.start()
            except Exception:
                logger.exception(
                    API_APP_STARTUP,
                    error="Failed to start backup service",
                )
                raise

            # Create startup backup if configured
            if backup_service.on_startup:
                try:
                    await backup_service.create_backup(
                        BackupTrigger.STARTUP,
                    )
                except MemoryError, RecursionError:
                    raise
                except Exception:
                    logger.warning(
                        API_APP_STARTUP,
                        error="Startup backup failed (non-fatal)",
                        exc_info=True,
                    )
        if approval_timeout_scheduler is not None:
            try:
                app_state.set_approval_timeout_scheduler(
                    approval_timeout_scheduler,
                )
                approval_timeout_scheduler.start()
                started_approval_timeout_scheduler = True
            except Exception:
                logger.exception(
                    API_APP_STARTUP,
                    error="Failed to start approval timeout scheduler",
                )
                raise
    except Exception:
        await _cleanup_on_failure(
            persistence=persistence,
            started_persistence=started_persistence,
            message_bus=message_bus,
            started_bus=started_bus,
            bridge=bridge,
            started_bridge=started_bridge,
            settings_dispatcher=settings_dispatcher,
            started_settings_dispatcher=started_settings_dispatcher,
            task_engine=task_engine,
            started_task_engine=started_task_engine,
            meeting_scheduler=meeting_scheduler,
            started_meeting_scheduler=started_meeting_scheduler,
            backup_service=backup_service,
            started_backup_service=started_backup_service,
            approval_timeout_scheduler=approval_timeout_scheduler,
            started_approval_timeout_scheduler=started_approval_timeout_scheduler,
        )
        raise


async def _safe_shutdown(  # noqa: PLR0913, C901
    task_engine: TaskEngine | None,
    meeting_scheduler: MeetingScheduler | None,
    backup_service: BackupService | None,
    approval_timeout_scheduler: ApprovalTimeoutScheduler | None,
    settings_dispatcher: SettingsChangeDispatcher | None,
    bridge: MessageBusBridge | None,
    message_bus: MessageBus | None,
    persistence: PersistenceBackend | None,
) -> None:
    """Stop services in reverse startup order.

    Approval timeout scheduler first, then meeting scheduler
    (depends on orchestrator), then task engine so it can drain queued
    mutations and publish final snapshots through the still-running
    bridge.  Backup runs before persistence disconnect so shutdown
    backup can still access the DB.
    """
    if approval_timeout_scheduler is not None:
        await _try_stop(
            approval_timeout_scheduler.stop(),
            API_APP_SHUTDOWN,
            "Failed to stop approval timeout scheduler",
        )
    if meeting_scheduler is not None:
        await _try_stop(
            meeting_scheduler.stop(),
            API_APP_SHUTDOWN,
            "Failed to stop meeting scheduler",
        )
    if task_engine is not None:
        await _try_stop(
            task_engine.stop(),
            API_APP_SHUTDOWN,
            "Failed to stop task engine",
        )
    if backup_service is not None:
        # Create shutdown backup before stopping the backup scheduler
        if backup_service.on_shutdown:
            try:
                await backup_service.create_backup(
                    BackupTrigger.SHUTDOWN,
                )
            except MemoryError, RecursionError:
                raise
            except Exception:
                logger.warning(
                    API_APP_SHUTDOWN,
                    error="Shutdown backup failed (non-fatal)",
                    exc_info=True,
                )
        await _try_stop(
            backup_service.stop(),
            API_APP_SHUTDOWN,
            "Failed to stop backup service",
        )
    if settings_dispatcher is not None:
        await _try_stop(
            settings_dispatcher.stop(),
            API_APP_SHUTDOWN,
            "Failed to stop settings dispatcher",
        )
    if bridge is not None:
        await _try_stop(
            bridge.stop(),
            API_APP_SHUTDOWN,
            "Failed to stop message bus bridge",
        )
    if message_bus is not None:
        await _try_stop(
            message_bus.stop(),
            API_APP_SHUTDOWN,
            "Failed to stop message bus",
        )
    if persistence is not None:
        await _try_stop(
            persistence.disconnect(),
            API_APP_SHUTDOWN,
            "Failed to disconnect persistence",
        )


async def _maybe_start_health_prober(
    app_state: AppState,
) -> ProviderHealthProber | None:
    """Start the health prober if provider tracking is available.

    Non-fatal: logs and returns None on failure so the application
    continues serving requests without health probing.

    Args:
        app_state: Application state.  Requires
            ``provider_health_tracker`` and ``config_resolver``;
            optionally uses ``provider_management`` for SSRF policy.

    Returns:
        The started prober instance, or None if preconditions are
        not met or startup fails.
    """
    if not (app_state.has_provider_health_tracker and app_state.has_config_resolver):
        logger.debug(
            API_APP_STARTUP,
            note="Health prober skipped: tracker or resolver not available",
        )
        return None
    try:
        policy_loader = (
            app_state.provider_management.get_discovery_policy
            if app_state.has_provider_management
            else None
        )
        prober = ProviderHealthProber(
            health_tracker=app_state.provider_health_tracker,
            config_resolver=app_state.config_resolver,
            discovery_policy_loader=policy_loader,
        )
        await prober.start()
    except MemoryError, RecursionError:
        raise
    except Exception:
        logger.warning(
            API_APP_STARTUP,
            error="Health prober startup failed (non-fatal)",
            exc_info=True,
        )
        return None
    return prober
