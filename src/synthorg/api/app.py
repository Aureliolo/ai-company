"""Litestar application factory.

Creates and configures the Litestar application with all
controllers, middleware, exception handlers, plugins, and
lifecycle hooks (startup/shutdown).
"""

import asyncio
import contextlib
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path, PurePath
from typing import TYPE_CHECKING, Any

from litestar import Litestar, Router
from litestar.config.compression import CompressionConfig
from litestar.config.cors import CORSConfig
from litestar.datastructures import State
from litestar.middleware.rate_limit import RateLimitConfig as LitestarRateLimitConfig
from litestar.openapi import OpenAPIConfig
from litestar.openapi.plugins import ScalarRenderPlugin

from synthorg import __version__
from synthorg.api.approval_store import ApprovalStore
from synthorg.api.auth.controller import require_password_changed
from synthorg.api.auth.middleware import create_auth_middleware_class
from synthorg.api.auth.service import AuthService  # noqa: TC001
from synthorg.api.auto_wire import auto_wire_phase1, auto_wire_settings
from synthorg.api.bus_bridge import MessageBusBridge
from synthorg.api.channels import (
    CHANNEL_APPROVALS,
    CHANNEL_MEETINGS,
    create_channels_plugin,
)
from synthorg.api.controllers import ALL_CONTROLLERS
from synthorg.api.controllers.ws import ws_handler
from synthorg.api.exception_handlers import EXCEPTION_HANDLERS
from synthorg.api.lifecycle import _safe_shutdown, _safe_startup, _try_stop
from synthorg.api.middleware import RequestLoggingMiddleware, security_headers_hook
from synthorg.api.state import AppState
from synthorg.api.ws_models import WsEvent, WsEventType
from synthorg.backup.factory import build_backup_service
from synthorg.backup.service import BackupService  # noqa: TC001
from synthorg.budget.tracker import CostTracker  # noqa: TC001
from synthorg.communication.bus_protocol import MessageBus  # noqa: TC001
from synthorg.communication.meeting.orchestrator import (
    MeetingOrchestrator,  # noqa: TC001
)
from synthorg.communication.meeting.scheduler import MeetingScheduler  # noqa: TC001
from synthorg.config import bootstrap_logging
from synthorg.config.schema import RootConfig
from synthorg.core.approval import ApprovalItem  # noqa: TC001
from synthorg.engine.coordination.service import MultiAgentCoordinator  # noqa: TC001
from synthorg.engine.review_gate import ReviewGateService
from synthorg.engine.task_engine import TaskEngine  # noqa: TC001
from synthorg.hr.performance.tracker import PerformanceTracker  # noqa: TC001
from synthorg.hr.registry import AgentRegistryService  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.config import DEFAULT_SINKS, LogConfig
from synthorg.observability.events.api import (
    API_APP_SHUTDOWN,
    API_APP_STARTUP,
    API_APPROVAL_PUBLISH_FAILED,
    API_WS_SEND_FAILED,
    API_WS_TICKET_CLEANUP,
)
from synthorg.persistence.config import PersistenceConfig, SQLiteConfig
from synthorg.persistence.factory import create_backend
from synthorg.persistence.protocol import PersistenceBackend  # noqa: TC001
from synthorg.providers.registry import ProviderRegistry  # noqa: TC001
from synthorg.security.timeout.scheduler import ApprovalTimeoutScheduler  # noqa: TC001
from synthorg.settings.dispatcher import SettingsChangeDispatcher
from synthorg.settings.subscribers import (
    BackupSettingsSubscriber,
    MemorySettingsSubscriber,
    ProviderSettingsSubscriber,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

    from litestar.channels import ChannelsPlugin
    from litestar.types import Middleware

    from synthorg.api.config import ApiConfig
    from synthorg.settings.service import SettingsService
    from synthorg.settings.subscriber import SettingsSubscriber

logger = get_logger(__name__)


def _make_expire_callback(
    channels_plugin: ChannelsPlugin,
) -> Callable[[ApprovalItem], None]:
    """Create a sync callback that publishes APPROVAL_EXPIRED events.

    The callback is invoked by ``ApprovalStore._check_expiration``
    when lazy expiry transitions an item to EXPIRED.  Best-effort:
    publish errors are logged and swallowed.

    Args:
        channels_plugin: Litestar channels plugin for WebSocket delivery.

    Returns:
        Sync callback accepting an expired ``ApprovalItem``.
    """

    def _on_expire(item: ApprovalItem) -> None:
        event = WsEvent(
            event_type=WsEventType.APPROVAL_EXPIRED,
            channel=CHANNEL_APPROVALS,
            timestamp=datetime.now(UTC),
            payload={
                "approval_id": item.id,
                "status": item.status.value,
                "action_type": item.action_type,
                "risk_level": item.risk_level.value,
            },
        )
        try:
            channels_plugin.publish(
                event.model_dump_json(),
                channels=[CHANNEL_APPROVALS],
            )
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.warning(
                API_APPROVAL_PUBLISH_FAILED,
                approval_id=item.id,
                event_type=WsEventType.APPROVAL_EXPIRED.value,
                exc_info=True,
            )

    return _on_expire


def _make_meeting_publisher(
    channels_plugin: ChannelsPlugin,
) -> Callable[[str, dict[str, Any]], None]:
    """Create a sync callback that publishes meeting events to WS.

    Args:
        channels_plugin: Litestar channels plugin for WebSocket delivery.

    Returns:
        Sync callback ``(event_name, payload) -> None``.
    """

    def _on_meeting_event(
        event_name: str,
        payload: dict[str, Any],
    ) -> None:
        event = WsEvent(
            event_type=WsEventType(event_name),
            channel=CHANNEL_MEETINGS,
            timestamp=datetime.now(UTC),
            payload=payload,
        )
        try:
            channels_plugin.publish(
                event.model_dump_json(),
                channels=[CHANNEL_MEETINGS],
            )
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.warning(
                API_WS_SEND_FAILED,
                note="Failed to publish meeting WebSocket event",
                event_name=event_name,
                exc_info=True,
            )

    return _on_meeting_event


async def _ticket_cleanup_loop(app_state: AppState) -> None:
    """Periodically prune expired WS tickets (runs as background task)."""
    while True:
        await asyncio.sleep(60)
        try:
            app_state.ticket_store.cleanup_expired()
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.warning(
                API_WS_TICKET_CLEANUP,
                error="Periodic ticket cleanup failed",
                exc_info=True,
            )


def _build_lifecycle(  # noqa: PLR0913, C901
    persistence: PersistenceBackend | None,
    message_bus: MessageBus | None,
    bridge: MessageBusBridge | None,
    settings_dispatcher: SettingsChangeDispatcher | None,
    task_engine: TaskEngine | None,
    meeting_scheduler: MeetingScheduler | None,
    backup_service: BackupService | None,
    approval_timeout_scheduler: ApprovalTimeoutScheduler | None,
    app_state: AppState,
    *,
    should_auto_wire_settings: bool = False,
    effective_config: RootConfig | None = None,
) -> tuple[
    Sequence[Callable[[], Awaitable[None]]],
    Sequence[Callable[[], Awaitable[None]]],
]:
    """Build startup and shutdown hooks.

    Args:
        persistence: Persistence backend (``None`` when unconfigured).
        message_bus: Internal message bus (``None`` when unconfigured).
        bridge: Message bus bridge to WebSocket channels.
        settings_dispatcher: Settings change dispatcher.
        task_engine: Centralized task state engine.
        meeting_scheduler: Meeting scheduler service.
        backup_service: Backup and restore service.
        approval_timeout_scheduler: Background approval timeout checker.
        app_state: Application state container.
        should_auto_wire_settings: When ``True``, Phase 2 auto-wiring
            creates ``SettingsService`` + dispatcher after persistence
            connects.
        effective_config: Root config needed for Phase 2 auto-wiring.

    Returns:
        A tuple of (on_startup, on_shutdown) callback lists.
    """
    _ticket_cleanup_task: asyncio.Task[None] | None = None
    _auto_wired_dispatcher: SettingsChangeDispatcher | None = None

    def _on_cleanup_task_done(task: asyncio.Task[None]) -> None:
        """Log unexpected cleanup-task death."""
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.error(
                API_WS_TICKET_CLEANUP,
                error="Ticket cleanup task died unexpectedly",
                exc_info=exc,
            )

    async def on_startup() -> None:
        nonlocal _ticket_cleanup_task, _auto_wired_dispatcher
        logger.info(API_APP_STARTUP, version=__version__)
        await _safe_startup(
            persistence,
            message_bus,
            bridge,
            settings_dispatcher,
            task_engine,
            meeting_scheduler,
            backup_service,
            approval_timeout_scheduler,
            app_state,
        )
        # Phase 2 auto-wire: SettingsService (needs connected persistence)
        if (
            should_auto_wire_settings
            and persistence is not None
            and effective_config is not None
            and not app_state.has_settings_service
        ):
            try:
                _auto_wired_dispatcher = await auto_wire_settings(
                    persistence,
                    message_bus,
                    effective_config,
                    app_state,
                    backup_service,
                    _build_settings_dispatcher,
                )
            except MemoryError, RecursionError:
                raise
            except Exception:
                logger.exception(
                    API_APP_STARTUP,
                    error="Phase 2 auto-wire failed",
                )
                await _safe_shutdown(
                    task_engine,
                    meeting_scheduler,
                    backup_service,
                    approval_timeout_scheduler,
                    settings_dispatcher,
                    bridge,
                    message_bus,
                    persistence,
                )
                raise
        _ticket_cleanup_task = asyncio.create_task(
            _ticket_cleanup_loop(app_state),
            name="ws-ticket-cleanup",
        )
        _ticket_cleanup_task.add_done_callback(_on_cleanup_task_done)

    async def on_shutdown() -> None:
        nonlocal _ticket_cleanup_task, _auto_wired_dispatcher
        if _ticket_cleanup_task is not None:
            _ticket_cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await _ticket_cleanup_task
            _ticket_cleanup_task = None
        logger.info(API_APP_SHUTDOWN, version=__version__)
        if _auto_wired_dispatcher is not None:
            await _try_stop(
                _auto_wired_dispatcher.stop(),
                API_APP_SHUTDOWN,
                "Failed to stop auto-wired settings dispatcher",
            )
            _auto_wired_dispatcher = None
        await _safe_shutdown(
            task_engine,
            meeting_scheduler,
            backup_service,
            approval_timeout_scheduler,
            settings_dispatcher,
            bridge,
            message_bus,
            persistence,
        )

    return [on_startup], [on_shutdown]


# ── 2-Phase Initialisation ────────────────────────────────────────
#
# Phase 1 (construct): Litestar bakes middleware, CORS, and routes
#   into the app at construction time — these read directly from
#   RootConfig and are immutable after construction.  Bootstrap-only
#   settings (server_host, server_port, api_prefix, cors_allowed_origins,
#   rate_limit_exclude_paths, auth_exclude_paths) are therefore NOT
#   resolved through SettingsService.
#
# Phase 2 (on_startup): After persistence connects and migrations
#   run, SettingsService + ConfigResolver become available.  Runtime-
#   editable settings (rate_limit_max_requests, rate_limit_time_unit,
#   jwt_expiry_minutes, min_password_length) are resolved through
#   ConfigResolver.get_api_config() by consumers that need current
#   values post-startup.
#
#   Note: Litestar's rate-limit middleware reads max_requests and
#   time_unit at construction; runtime DB changes are visible only
#   to code calling get_api_config(), not to the middleware itself.


def _bootstrap_app_logging(effective_config: RootConfig) -> RootConfig:
    """Activate the structured logging pipeline.

    Applies the ``SYNTHORG_LOG_DIR`` env var override (for Docker
    volume paths) before calling :func:`bootstrap_logging`.

    When the env var is set with an existing logging config, patches
    ``log_dir``.  When set without a logging config, creates a
    default config with ``DEFAULT_SINKS``.  Otherwise, delegates
    directly to ``bootstrap_logging``.

    Args:
        effective_config: Root config (possibly without a logging
            section).

    Returns:
        The config actually used for logging -- either the original
        ``effective_config`` or a patched copy with the
        ``SYNTHORG_LOG_DIR`` override applied.  Callers should use
        the returned value so that ``AppState.config.logging``
        reflects the active logging configuration.

    Raises:
        ValueError: If ``SYNTHORG_LOG_DIR`` contains ``..`` path
            traversal components.
    """
    log_dir = os.environ.get("SYNTHORG_LOG_DIR", "").strip()
    if not log_dir:
        bootstrap_logging(effective_config)
        return effective_config

    # Validate before model_copy -- Pydantic validators do not run
    # on model_copy(update=...), so we must check manually.
    if ".." in PurePath(log_dir).parts:
        msg = f"SYNTHORG_LOG_DIR contains '..' path traversal component: {log_dir!r}"
        raise ValueError(msg)

    base_log_cfg = effective_config.logging or LogConfig(
        sinks=DEFAULT_SINKS,
    )
    patched = effective_config.model_copy(
        update={
            "logging": base_log_cfg.model_copy(
                update={"log_dir": log_dir},
            ),
        },
    )
    bootstrap_logging(patched)
    return patched


def create_app(  # noqa: PLR0913
    *,
    config: RootConfig | None = None,
    persistence: PersistenceBackend | None = None,
    message_bus: MessageBus | None = None,
    cost_tracker: CostTracker | None = None,
    approval_store: ApprovalStore | None = None,
    auth_service: AuthService | None = None,
    task_engine: TaskEngine | None = None,
    coordinator: MultiAgentCoordinator | None = None,
    agent_registry: AgentRegistryService | None = None,
    meeting_orchestrator: MeetingOrchestrator | None = None,
    meeting_scheduler: MeetingScheduler | None = None,
    performance_tracker: PerformanceTracker | None = None,
    settings_service: SettingsService | None = None,
    provider_registry: ProviderRegistry | None = None,
) -> Litestar:
    """Create and configure the Litestar application.

    All parameters are optional for testing -- provide fakes via
    keyword arguments.  Services not explicitly provided are
    auto-wired from config and environment variables.

    Args:
        config: Root company configuration.
        persistence: Persistence backend.
        message_bus: Internal message bus.
        cost_tracker: Cost tracking service.
        approval_store: Approval queue store.
        auth_service: Pre-built auth service (for testing).
        task_engine: Centralized task state engine.
        coordinator: Multi-agent coordinator.
        agent_registry: Agent registry service.
        meeting_orchestrator: Meeting orchestrator.
        meeting_scheduler: Meeting scheduler.
        performance_tracker: Performance tracking service.
        settings_service: Settings service for runtime config.
        provider_registry: Provider registry.

    Returns:
        Configured Litestar application.
    """
    effective_config = config or RootConfig(company_name="default")

    # Activate the structured logging pipeline (8 sinks) before any
    # other setup so that auto-wiring, persistence, and bus logs all
    # flow through the configured sinks.  Respects SYNTHORG_LOG_DIR
    # env var for Docker log directory override.
    try:
        effective_config = _bootstrap_app_logging(effective_config)
    except Exception as exc:
        print(  # noqa: T201
            f"CRITICAL: Failed to initialise logging pipeline: {exc}. "
            "Check SYNTHORG_LOG_DIR, SYNTHORG_LOG_LEVEL, and the "
            "'logging' section of your config file.",
            file=sys.stderr,
            flush=True,
        )
        raise

    api_config = effective_config.api

    # Resolve runtime paths for backup service wiring.
    resolved_db_path: Path | None = None
    resolved_config_path_str = (os.environ.get("SYNTHORG_CONFIG_PATH") or "").strip()
    resolved_config_path: Path | None = (
        Path(resolved_config_path_str) if resolved_config_path_str else None
    )

    # Auto-wire persistence from SYNTHORG_DB_PATH env var (set by CLI
    # compose template).  The startup lifecycle handles connect() +
    # migrate() + auth service creation.
    if persistence is None:
        db_path = (os.environ.get("SYNTHORG_DB_PATH") or "").strip()
        if db_path:
            resolved_db_path = Path(db_path)
            try:
                persistence = create_backend(
                    PersistenceConfig(sqlite=SQLiteConfig(path=db_path)),
                )
            except Exception:
                logger.exception(
                    API_APP_STARTUP,
                    error="Failed to create persistence backend from env",
                )
                raise
            logger.info(
                API_APP_STARTUP,
                note="Auto-wired SQLite persistence from SYNTHORG_DB_PATH",
                db_name=Path(db_path).name,
            )

    # ── Phase 1 auto-wire: services that don't need connected persistence ──
    phase1 = auto_wire_phase1(
        effective_config=effective_config,
        persistence=persistence,
        message_bus=message_bus,
        cost_tracker=cost_tracker,
        task_engine=task_engine,
        provider_registry=provider_registry,
    )
    message_bus = phase1.message_bus
    cost_tracker = phase1.cost_tracker
    task_engine = phase1.task_engine
    provider_registry = phase1.provider_registry

    channels_plugin = create_channels_plugin()
    expire_callback = _make_expire_callback(channels_plugin)
    effective_approval_store = approval_store or ApprovalStore(
        on_expire=expire_callback,
    )

    # Wire meeting event publisher to the meetings WS channel.
    if meeting_scheduler is not None and meeting_scheduler._event_publisher is None:  # noqa: SLF001
        meeting_scheduler._event_publisher = _make_meeting_publisher(  # noqa: SLF001
            channels_plugin,
        )

    app_state = AppState(
        config=effective_config,
        persistence=persistence,
        message_bus=message_bus,
        cost_tracker=cost_tracker,
        approval_store=effective_approval_store,
        auth_service=auth_service,
        task_engine=task_engine,
        coordinator=coordinator,
        agent_registry=agent_registry,
        meeting_orchestrator=meeting_orchestrator,
        meeting_scheduler=meeting_scheduler,
        performance_tracker=performance_tracker,
        settings_service=settings_service,
        provider_registry=provider_registry,
        startup_time=time.monotonic(),
    )

    bridge = _build_bridge(message_bus, channels_plugin)
    backup_service = build_backup_service(
        effective_config,
        resolved_db_path=resolved_db_path,
        resolved_config_path=resolved_config_path,
    )
    settings_dispatcher = _build_settings_dispatcher(
        message_bus,
        settings_service,
        effective_config,
        app_state,
        backup_service,
    )
    plugins: list[ChannelsPlugin] = [channels_plugin]
    middleware = _build_middleware(api_config)

    api_router = Router(
        path=api_config.api_prefix,
        route_handlers=[*ALL_CONTROLLERS, ws_handler],
        guards=[require_password_changed],
    )

    # Phase 2 auto-wiring flag: persistence being non-None is the
    # enabling condition -- SettingsService needs connected persistence
    # and is created in on_startup after _init_persistence().
    _should_auto_wire = settings_service is None and persistence is not None

    # Review gate service -- transitions tasks from IN_REVIEW on approval.
    review_gate_service = ReviewGateService(task_engine=task_engine)
    app_state.set_review_gate_service(review_gate_service)

    # Approval timeout scheduler -- None here; auto-creation from
    # settings at startup is not yet wired.  Pass explicitly via the
    # lifecycle when a TimeoutChecker is available.
    approval_timeout_scheduler: ApprovalTimeoutScheduler | None = None

    startup, shutdown = _build_lifecycle(
        persistence,
        message_bus,
        bridge,
        settings_dispatcher,
        task_engine,
        meeting_scheduler,
        backup_service,
        approval_timeout_scheduler,
        app_state,
        should_auto_wire_settings=_should_auto_wire,
        effective_config=effective_config,
    )

    return Litestar(
        route_handlers=[api_router],
        # Disable Litestar's built-in logging config to preserve the
        # structlog multi-file-sink pipeline set up by
        # _bootstrap_app_logging() above.  Without this, Litestar calls
        # dictConfig() at startup which triggers _clearExistingHandlers
        # and replaces structlog's file sinks with a stdlib
        # queue_listener, causing all runtime logs to go only to Docker
        # stdout.
        logging_config=None,
        state=State({"app_state": app_state}),
        cors_config=CORSConfig(
            allow_origins=list(api_config.cors.allowed_origins),
            allow_methods=list(api_config.cors.allow_methods),  # type: ignore[arg-type]
            allow_headers=list(api_config.cors.allow_headers),
            allow_credentials=api_config.cors.allow_credentials,
        ),
        compression_config=CompressionConfig(
            backend="brotli",
            minimum_size=1000,
        ),
        request_max_body_size=2_097_152,  # 2 MB
        before_send=[security_headers_hook],
        middleware=middleware,
        plugins=plugins,
        exception_handlers=dict(EXCEPTION_HANDLERS),  # type: ignore[arg-type]
        openapi_config=OpenAPIConfig(
            title="SynthOrg API",
            version=__version__,
            path="/docs",
            render_plugins=[
                ScalarRenderPlugin(path="/api"),
            ],
        ),
        on_startup=startup,
        on_shutdown=shutdown,
    )


def _build_bridge(
    message_bus: MessageBus | None,
    channels_plugin: ChannelsPlugin,
) -> MessageBusBridge | None:
    """Create message bus bridge if bus is available."""
    if message_bus is None:
        return None
    return MessageBusBridge(message_bus, channels_plugin)


def _build_settings_dispatcher(
    message_bus: MessageBus | None,
    settings_service: SettingsService | None,
    config: RootConfig,
    app_state: AppState,
    backup_service: BackupService | None = None,
) -> SettingsChangeDispatcher | None:
    """Create settings change dispatcher if bus and settings are available."""
    if message_bus is None or settings_service is None:
        return None
    provider_sub = ProviderSettingsSubscriber(
        config=config,
        app_state=app_state,
        settings_service=settings_service,
    )
    memory_sub = MemorySettingsSubscriber()
    subs: list[SettingsSubscriber] = [provider_sub, memory_sub]
    if backup_service is not None:
        subs.append(
            BackupSettingsSubscriber(
                backup_service=backup_service,
                settings_service=settings_service,
            ),
        )
    return SettingsChangeDispatcher(
        message_bus=message_bus,
        subscribers=tuple(subs),
    )


def _build_middleware(api_config: ApiConfig) -> list[Middleware]:
    """Build the middleware stack from configuration."""
    rl = api_config.rate_limit
    prefix = api_config.api_prefix
    ws_path = f"^{prefix}/ws$"

    # Exclude the WS path from rate limiting -- rate limiting
    # HTTP-style makes no sense for persistent WebSocket connections.
    rl_exclude = list(rl.exclude_paths)
    if ws_path not in rl_exclude:
        rl_exclude.append(ws_path)
    rate_limit = LitestarRateLimitConfig(
        rate_limit=(rl.time_unit, rl.max_requests),  # type: ignore[arg-type]
        exclude=rl_exclude,
    )
    auth = api_config.auth
    setup_status_path = f"^{prefix}/setup/status$"
    exclude_paths = (
        auth.exclude_paths
        if auth.exclude_paths is not None
        else (
            f"^{prefix}/health$",
            "^/docs",
            "^/api$",
            f"^{prefix}/auth/setup$",
            f"^{prefix}/auth/login$",
            setup_status_path,
        )
    )
    # Always ensure the setup status endpoint is publicly accessible
    # even when custom exclude_paths are provided via config.
    if setup_status_path not in exclude_paths:
        exclude_paths = (*exclude_paths, setup_status_path)
    # Always ensure the WS upgrade path is excluded -- the WS handler
    # performs its own ticket-based auth, so the JWT middleware must
    # not run on the upgrade request.
    if ws_path not in exclude_paths:
        exclude_paths = (*exclude_paths, ws_path)
    auth = auth.model_copy(update={"exclude_paths": exclude_paths})
    auth_middleware = create_auth_middleware_class(auth)
    return [
        auth_middleware,
        RequestLoggingMiddleware,
        rate_limit.middleware,
    ]
