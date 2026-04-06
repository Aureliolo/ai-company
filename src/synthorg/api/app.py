"""Litestar application factory.

Creates and configures the Litestar application with all
controllers, middleware, exception handlers, plugins, and
lifecycle hooks (startup/shutdown).
"""

import asyncio
import contextlib
import functools
import os
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path, PurePath
from typing import TYPE_CHECKING, Any

from litestar import Litestar, Request, Router
from litestar.config.compression import CompressionConfig
from litestar.config.cors import CORSConfig
from litestar.datastructures import State
from litestar.middleware.rate_limit import (
    RateLimitConfig as LitestarRateLimitConfig,
)
from litestar.middleware.rate_limit import (
    get_remote_address,
)
from litestar.openapi import OpenAPIConfig
from litestar.openapi.plugins import ScalarRenderPlugin

from synthorg import __version__
from synthorg.api.approval_store import ApprovalStore
from synthorg.api.auth.controller import require_password_changed
from synthorg.api.auth.middleware import create_auth_middleware_class
from synthorg.api.auth.service import AuthService  # noqa: TC001
from synthorg.api.auto_wire import (
    auto_wire_meetings,
    auto_wire_phase1,
    auto_wire_settings,
)
from synthorg.api.bus_bridge import MessageBusBridge
from synthorg.api.channels import (
    CHANNEL_AGENTS,
    CHANNEL_APPROVALS,
    CHANNEL_MEETINGS,
    create_channels_plugin,
)
from synthorg.api.controllers import ALL_CONTROLLERS
from synthorg.api.controllers.ws import ws_handler
from synthorg.api.exception_handlers import EXCEPTION_HANDLERS
from synthorg.api.lifecycle import (
    _maybe_start_health_prober,
    _safe_shutdown,
    _safe_startup,
    _try_stop,
)
from synthorg.api.middleware import RequestLoggingMiddleware, security_headers_hook
from synthorg.api.state import AppState
from synthorg.api.ws_models import WsEvent, WsEventType
from synthorg.backup.factory import build_backup_service
from synthorg.backup.service import BackupService  # noqa: TC001
from synthorg.budget.tracker import CostTracker  # noqa: TC001
from synthorg.communication.bus_protocol import MessageBus  # noqa: TC001
from synthorg.communication.delegation.record_store import (
    DelegationRecordStore,  # noqa: TC001
)
from synthorg.communication.meeting.orchestrator import (
    MeetingOrchestrator,  # noqa: TC001
)
from synthorg.communication.meeting.scheduler import MeetingScheduler  # noqa: TC001
from synthorg.config import bootstrap_logging
from synthorg.config.schema import RootConfig
from synthorg.core.approval import ApprovalItem  # noqa: TC001
from synthorg.engine.agent_engine import (  # noqa: TC001
    PersonalityTrimNotifier,
    PersonalityTrimPayload,
)
from synthorg.engine.coordination.service import MultiAgentCoordinator  # noqa: TC001
from synthorg.engine.review_gate import ReviewGateService
from synthorg.engine.task_engine import TaskEngine  # noqa: TC001
from synthorg.hr.performance.config import PerformanceConfig
from synthorg.hr.performance.quality_protocol import (
    QualityScoringStrategy,  # noqa: TC001
)
from synthorg.hr.performance.tracker import PerformanceTracker
from synthorg.hr.registry import AgentRegistryService  # noqa: TC001
from synthorg.notifications.factory import build_notification_dispatcher
from synthorg.observability import get_logger
from synthorg.observability.config import DEFAULT_SINKS, LogConfig
from synthorg.observability.events.api import (
    API_APP_SHUTDOWN,
    API_APP_STARTUP,
    API_APPROVAL_PUBLISH_FAILED,
    API_NETWORK_EXPOSURE_WARNING,
    API_SESSION_CLEANUP,
    API_WS_SEND_FAILED,
    API_WS_TICKET_CLEANUP,
)
from synthorg.observability.events.prompt import (
    PROMPT_PERSONALITY_NOTIFY_FAILED,
)
from synthorg.observability.events.setup import (
    SETUP_AGENT_BOOTSTRAP_FAILED,
)
from synthorg.persistence.artifact_storage import (
    ArtifactStorageBackend,  # noqa: TC001
)
from synthorg.persistence.config import PersistenceConfig, SQLiteConfig
from synthorg.persistence.factory import create_backend
from synthorg.persistence.filesystem_artifact_storage import (
    FileSystemArtifactStorage,
)
from synthorg.persistence.protocol import PersistenceBackend  # noqa: TC001
from synthorg.providers.errors import DriverNotRegisteredError
from synthorg.providers.health import ProviderHealthTracker  # noqa: TC001
from synthorg.providers.health_prober import ProviderHealthProber  # noqa: TC001
from synthorg.providers.registry import ProviderRegistry  # noqa: TC001
from synthorg.security.timeout.scheduler import ApprovalTimeoutScheduler  # noqa: TC001
from synthorg.settings.dispatcher import SettingsChangeDispatcher
from synthorg.settings.subscribers import (
    BackupSettingsSubscriber,
    MemorySettingsSubscriber,
    ObservabilitySettingsSubscriber,
    ProviderSettingsSubscriber,
)
from synthorg.tools.invocation_tracker import ToolInvocationTracker  # noqa: TC001

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

    from litestar.channels import ChannelsPlugin
    from litestar.types import Middleware

    from synthorg.api.auth.config import AuthConfig
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


def make_personality_trim_notifier(
    channels_plugin: ChannelsPlugin,
) -> PersonalityTrimNotifier:
    """Create an async callback that publishes ``personality.trimmed`` events.

    The returned callback matches the
    :data:`~synthorg.engine.agent_engine.PersonalityTrimNotifier` contract and
    can be passed to ``AgentEngine`` via the ``personality_trim_notifier``
    constructor parameter.  It publishes a ``WsEvent(event_type=
    WsEventType.PERSONALITY_TRIMMED, channel=agents)`` so the dashboard can
    render a live toast when personality trimming fires.

    External engine runners (CLI workers, Kubernetes jobs, etc.) that host an
    ``AgentEngine`` should call this factory with their ``ChannelsPlugin``
    instance and wire the result into the engine constructor.  ``create_app``
    itself does not instantiate ``AgentEngine`` and therefore does not call
    this factory -- it exists as a public wiring utility for downstream
    consumers.

    The callback is declared ``async`` to match the
    :data:`PersonalityTrimNotifier` contract.  The underlying
    :meth:`ChannelsPlugin.publish` call is synchronous -- a fire-and-forget
    enqueue onto the channels backlog that normally completes in
    microseconds.  We wrap it in :func:`asyncio.to_thread` so that:
    (a) a pathological channels-plugin implementation cannot block the
    event loop, and (b) the engine-side :func:`asyncio.timeout` has an
    actual ``await`` point to cancel at.  Without the ``to_thread`` hop a
    synchronous stall would bypass the timeout entirely.

    Best-effort error handling distinguishes ordinary transport failures
    from system-level or cancellation conditions:

    * Ordinary ``Exception`` subclasses raised during the publish (broken
      channel, serialization error, backend unavailable) are logged via
      ``PROMPT_PERSONALITY_NOTIFY_FAILED`` and **swallowed** so a broken
      notification pipeline never blocks task execution.
    * :class:`MemoryError` and :class:`RecursionError` are re-raised so the
      enclosing task can tear down cleanly under resource exhaustion.
    * :class:`asyncio.CancelledError` propagates naturally because it is a
      :class:`BaseException` subclass and is not caught by ``except
      Exception``, preserving structured cancellation.

    Args:
        channels_plugin: Litestar channels plugin for WebSocket delivery.

    Returns:
        Async callback accepting a ``PersonalityTrimPayload``.
    """

    async def _on_personality_trimmed(payload: PersonalityTrimPayload) -> None:
        event = WsEvent(
            event_type=WsEventType.PERSONALITY_TRIMMED,
            channel=CHANNEL_AGENTS,
            timestamp=datetime.now(UTC),
            payload=dict(payload),
        )
        try:
            await asyncio.to_thread(
                functools.partial(
                    channels_plugin.publish,
                    event.model_dump_json(),
                    channels=[CHANNEL_AGENTS],
                ),
            )
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.warning(
                PROMPT_PERSONALITY_NOTIFY_FAILED,
                reason="failed to publish personality.trimmed WebSocket event",
                agent_id=payload.get("agent_id"),
                agent_name=payload.get("agent_name"),
                task_id=payload.get("task_id"),
                trim_tier=payload.get("trim_tier"),
                before_tokens=payload.get("before_tokens"),
                after_tokens=payload.get("after_tokens"),
                exc_info=True,
            )

    return _on_personality_trimmed


async def _ticket_cleanup_loop(app_state: AppState) -> None:
    """Periodically prune expired WS tickets and sessions."""
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
        # Session cleanup also runs every iteration.
        try:
            if app_state.has_session_store:
                await app_state.session_store.cleanup_expired()
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.warning(
                API_SESSION_CLEANUP,
                error="Periodic session cleanup failed",
                exc_info=True,
            )


async def _maybe_bootstrap_agents(app_state: AppState) -> None:
    """Bootstrap agents if setup is complete and services are available.

    On first run, setup isn't complete yet so bootstrap is deferred
    to ``POST /setup/complete``.  On subsequent starts, agents are
    loaded from persisted config into the runtime registry.
    """
    if not (
        app_state.has_config_resolver
        and app_state.has_agent_registry
        and app_state.has_settings_service
    ):
        logger.debug(
            API_APP_STARTUP,
            note="Agent bootstrap skipped: required services not available",
        )
        return

    try:
        setup_entry = await app_state.settings_service.get_entry(
            "api",
            "setup_complete",
        )
        is_complete = setup_entry.value == "true"
    except MemoryError, RecursionError:
        raise
    except Exception:
        logger.warning(
            API_APP_STARTUP,
            note="Could not read setup_complete setting; skipping agent bootstrap",
            exc_info=True,
        )
        is_complete = False

    if not is_complete:
        logger.debug(
            API_APP_STARTUP,
            note="Agent bootstrap skipped: setup not complete",
        )
        return

    try:
        from synthorg.api.bootstrap import bootstrap_agents  # noqa: PLC0415

        await bootstrap_agents(
            config_resolver=app_state.config_resolver,
            agent_registry=app_state.agent_registry,
        )
    except MemoryError, RecursionError:
        raise
    except Exception:
        logger.warning(
            SETUP_AGENT_BOOTSTRAP_FAILED,
            error="Agent bootstrap failed at startup (non-fatal)",
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
    _health_prober: ProviderHealthProber | None = None

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
        nonlocal _ticket_cleanup_task, _auto_wired_dispatcher, _health_prober
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
        # Wire workflow execution observer (needs connected persistence)
        if (
            task_engine is not None
            and persistence is not None
            and hasattr(persistence, "workflow_definitions")
            and hasattr(persistence, "workflow_executions")
        ):
            from synthorg.engine.workflow.execution_observer import (  # noqa: PLC0415
                WorkflowExecutionObserver,
            )

            _wf_observer = WorkflowExecutionObserver(
                definition_repo=persistence.workflow_definitions,
                execution_repo=persistence.workflow_executions,
                task_engine=task_engine,
            )
            task_engine.register_observer(_wf_observer)

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
                    performance_tracker=app_state._performance_tracker,  # noqa: SLF001
                )
                raise
        await _maybe_bootstrap_agents(app_state)
        _ticket_cleanup_task = asyncio.create_task(
            _ticket_cleanup_loop(app_state),
            name="ws-ticket-cleanup",
        )
        _ticket_cleanup_task.add_done_callback(_on_cleanup_task_done)
        _health_prober = await _maybe_start_health_prober(app_state)

    async def on_shutdown() -> None:
        nonlocal _ticket_cleanup_task, _auto_wired_dispatcher, _health_prober
        if _ticket_cleanup_task is not None:
            _ticket_cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await _ticket_cleanup_task
            _ticket_cleanup_task = None
        logger.info(API_APP_SHUTDOWN, version=__version__)
        if _health_prober is not None:
            await _try_stop(
                _health_prober.stop(),
                API_APP_SHUTDOWN,
                "Failed to stop health prober",
            )
            _health_prober = None
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
            performance_tracker=app_state._performance_tracker,  # noqa: SLF001
        )
        if app_state.has_notification_dispatcher:
            await _try_stop(
                app_state.notification_dispatcher.close(),
                API_APP_SHUTDOWN,
                "Failed to stop notification dispatcher",
            )

    return [on_startup], [on_shutdown]


# 2-Phase Init: Phase 1 (construct) bakes immutable middleware/CORS/routes
# from RootConfig.  Phase 2 (on_startup) wires SettingsService + ConfigResolver
# for runtime-editable settings.  Litestar rate-limit middleware reads config at
# construction; runtime DB changes only affect code calling get_api_config().


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


def _resolve_llm_judge_strategy(
    cfg: PerformanceConfig,
    *,
    provider_registry: ProviderRegistry,
    cost_tracker: CostTracker | None,
) -> QualityScoringStrategy | None:
    """Resolve the LLM judge strategy from config.

    Returns ``None`` if the judge model is not configured, the named
    provider is not registered, or no providers are available.

    Args:
        cfg: Performance configuration.
        provider_registry: Provider registry for LLM judge calls.
        cost_tracker: Optional cost tracker for judge cost recording.

    Returns:
        Configured LLM judge strategy, or ``None``.
    """
    if cfg.quality_judge_model is None:
        return None

    judge_provider_name = cfg.quality_judge_provider
    if judge_provider_name is not None:
        try:
            provider_driver = provider_registry.get(str(judge_provider_name))
        except DriverNotRegisteredError:
            logger.warning(
                API_APP_STARTUP,
                note="Quality judge provider not found, LLM judge disabled",
                provider=str(judge_provider_name),
            )
            return None
    else:
        available = provider_registry.list_providers()
        if not available:
            logger.warning(
                API_APP_STARTUP,
                note="No providers available, LLM judge disabled",
            )
            return None
        provider_driver = provider_registry.get(available[0])

    from synthorg.hr.performance.llm_judge_quality_strategy import (  # noqa: PLC0415
        LlmJudgeQualityStrategy,
    )

    logger.info(
        API_APP_STARTUP,
        note="Quality LLM judge configured",
        model=str(cfg.quality_judge_model),
    )
    return LlmJudgeQualityStrategy(
        provider=provider_driver,
        model=cfg.quality_judge_model,
        cost_tracker=cost_tracker,
    )


def _build_performance_tracker(
    *,
    cost_tracker: CostTracker | None = None,
    provider_registry: ProviderRegistry | None = None,
    perf_config: PerformanceConfig | None = None,
) -> PerformanceTracker:
    """Build a PerformanceTracker with composite quality strategy.

    Always wires a ``QualityOverrideStore`` (human overrides are free).
    Delegates LLM judge resolution to :func:`_resolve_llm_judge_strategy`.

    Args:
        cost_tracker: Optional cost tracker for judge cost recording.
        provider_registry: Provider registry for LLM judge calls.
        perf_config: Performance configuration (default config if None).

    Returns:
        Configured performance tracker.
    """
    from synthorg.hr.performance.ci_quality_strategy import (  # noqa: PLC0415
        CISignalQualityStrategy,
    )
    from synthorg.hr.performance.composite_quality_strategy import (  # noqa: PLC0415
        CompositeQualityStrategy,
    )
    from synthorg.hr.performance.quality_override_store import (  # noqa: PLC0415
        QualityOverrideStore,
    )

    cfg = perf_config or PerformanceConfig()
    quality_override_store = QualityOverrideStore()

    llm_strategy = (
        _resolve_llm_judge_strategy(
            cfg,
            provider_registry=provider_registry,
            cost_tracker=cost_tracker,
        )
        if provider_registry is not None
        else None
    )

    composite = CompositeQualityStrategy(
        ci_strategy=CISignalQualityStrategy(),
        llm_strategy=llm_strategy,
        override_store=quality_override_store,
        ci_weight=cfg.quality_ci_weight,
        llm_weight=cfg.quality_llm_weight,
    )

    return PerformanceTracker(
        quality_strategy=composite,
        config=cfg,
        quality_override_store=quality_override_store,
    )


def create_app(  # noqa: PLR0913, PLR0915
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
    provider_health_tracker: ProviderHealthTracker | None = None,
    tool_invocation_tracker: ToolInvocationTracker | None = None,
    delegation_record_store: DelegationRecordStore | None = None,
    artifact_storage: ArtifactStorageBackend | None = None,
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
        provider_health_tracker: Provider health tracking service.
        tool_invocation_tracker: Tool invocation tracking service.
        delegation_record_store: Delegation record store.
        artifact_storage: Artifact storage backend.

    Returns:
        Configured Litestar application.
    """
    effective_config = config or RootConfig(company_name="default")

    # Activate the structured logging pipeline before any
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
            # Auto-wire artifact storage from the same data directory.
            if artifact_storage is None:
                artifact_storage = FileSystemArtifactStorage(
                    data_dir=resolved_db_path.parent,
                )
                logger.info(
                    API_APP_STARTUP,
                    note="Auto-wired filesystem artifact storage",
                )

    # ── Phase 1 auto-wire: services that don't need connected persistence ──
    phase1 = auto_wire_phase1(
        effective_config=effective_config,
        persistence=persistence,
        message_bus=message_bus,
        cost_tracker=cost_tracker,
        task_engine=task_engine,
        provider_registry=provider_registry,
        provider_health_tracker=provider_health_tracker,
    )
    message_bus = phase1.message_bus
    cost_tracker = phase1.cost_tracker
    task_engine = phase1.task_engine
    provider_registry = phase1.provider_registry
    provider_health_tracker = phase1.provider_health_tracker

    # ── Meeting auto-wire: orchestrator + scheduler (Phase 1 level) ──
    meeting_wire = auto_wire_meetings(
        effective_config=effective_config,
        meeting_orchestrator=meeting_orchestrator,
        meeting_scheduler=meeting_scheduler,
        agent_registry=agent_registry,
    )
    meeting_orchestrator = meeting_wire.meeting_orchestrator
    meeting_scheduler = meeting_wire.meeting_scheduler
    ceremony_scheduler = meeting_wire.ceremony_scheduler

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

    # Auto-wire performance tracker with composite quality strategy
    # when not explicitly injected (production path).
    if performance_tracker is None:
        performance_tracker = _build_performance_tracker(
            cost_tracker=cost_tracker,
            provider_registry=provider_registry,
            perf_config=effective_config.performance,
        )

    notification_dispatcher = build_notification_dispatcher(
        effective_config.notifications,
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
        ceremony_scheduler=ceremony_scheduler,
        performance_tracker=performance_tracker,
        settings_service=settings_service,
        provider_registry=provider_registry,
        provider_health_tracker=provider_health_tracker,
        tool_invocation_tracker=tool_invocation_tracker,
        delegation_record_store=delegation_record_store,
        artifact_storage=artifact_storage,
        notification_dispatcher=notification_dispatcher,
        startup_time=time.monotonic(),
    )

    bridge = (
        MessageBusBridge(message_bus, channels_plugin)
        if message_bus is not None
        else None
    )
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
    # Needs ``task_engine`` for self-review enforcement (preflight) and
    # state transitions; ``persistence`` is OPTIONAL and only used for
    # the auditable decisions drop-box.  Construct the service whenever
    # ``task_engine`` exists so the fail-fast self-review / missing-task
    # preflight still runs in task-engine-only deployments; decision
    # recording gracefully degrades to a WARNING-level no-op when
    # persistence is absent.
    if task_engine is not None:
        review_gate_service = ReviewGateService(
            task_engine=task_engine,
            persistence=persistence,
        )
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
        # Must be >= artifact API max payload (50 MB) so endpoint-level
        # validation can enforce exact storage limits.
        request_max_body_size=52_428_800,  # 50 MB
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
    log_dir = config.logging.log_dir if config.logging is not None else "logs"
    observability_sub = ObservabilitySettingsSubscriber(
        settings_service=settings_service,
        log_dir=log_dir,
    )
    subs: list[SettingsSubscriber] = [provider_sub, memory_sub, observability_sub]
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


def _build_unauth_identifier(
    trusted: frozenset[str],
) -> Callable[[Request[Any, Any, Any]], str]:
    """Build a proxy-aware client IP extractor for the unauth tier.

    When ``trusted_proxies`` is configured, extracts the real client
    IP from the ``X-Forwarded-For`` header (rightmost untrusted hop).
    Without trusted proxies, falls back to ``request.client.host``.

    Args:
        trusted: Frozen set of trusted proxy IPs/CIDRs.

    Returns:
        Callable that extracts a rate-limit key from a request.
    """
    if not trusted:
        return get_remote_address

    def _extract_forwarded_ip(
        request: Request[Any, Any, Any],
    ) -> str:
        # Only trust X-Forwarded-For when the immediate peer is a
        # known proxy. Otherwise any client can spoof the header.
        peer_ip = get_remote_address(request)
        if peer_ip not in trusted:
            return peer_ip
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            # X-Forwarded-For: client, proxy1, proxy2
            # Walk from the right, skip trusted proxies.
            hops = [h.strip() for h in forwarded.split(",")]
            for hop in reversed(hops):
                if hop not in trusted:
                    return hop
        return peer_ip

    return _extract_forwarded_ip


def _auth_identifier_for_request(
    request: Request[Any, Any, Any],
) -> str:
    """Return the authenticated user's ID as the rate limit key.

    Falls back to client IP when the user is not set in scope
    (e.g. auth-excluded paths that are not excluded from the
    auth rate limiter).

    Args:
        request: The incoming request.

    Returns:
        User ID string or client IP as fallback.
    """
    user = request.scope.get("user")
    if user is not None and hasattr(user, "user_id"):
        return str(user.user_id)
    return get_remote_address(request)


def _build_auth_exclude_paths(
    auth: AuthConfig,
    prefix: str,
    ws_path: str,
) -> tuple[str, ...]:
    """Compute auth middleware exclude paths with fail-safe defaults."""
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
    if setup_status_path not in exclude_paths:
        exclude_paths = (*exclude_paths, setup_status_path)
    if ws_path not in exclude_paths:
        exclude_paths = (*exclude_paths, ws_path)
    return exclude_paths


def _build_middleware(api_config: ApiConfig) -> list[Middleware]:
    """Build the middleware stack from configuration.

    Two rate-limit tiers are stacked around the auth middleware:

    1. **Unauth tier** (outermost) -- keyed by client IP, low budget.
    2. Auth middleware -- populates ``scope["user"]``.
    3. Request logging.
    4. **Auth tier** (innermost) -- keyed by user ID, high budget.

    When ``trusted_proxies`` is configured, the unauth tier reads
    ``X-Forwarded-For`` to extract the real client IP. Without it,
    all clients behind a proxy share one IP-based rate limit bucket.
    """
    rl = api_config.rate_limit
    prefix = api_config.api_prefix
    ws_path = f"^{prefix}/ws$"
    trusted = frozenset(api_config.server.trusted_proxies)

    if not trusted and api_config.server.host not in ("127.0.0.1", "localhost", "::1"):
        logger.warning(
            API_NETWORK_EXPOSURE_WARNING,
            note=(
                "No trusted_proxies configured. If this server is behind "
                "a reverse proxy or load balancer, all proxied clients "
                "will share a single unauth rate-limit bucket. Set "
                "api.server.trusted_proxies to the proxy IPs."
            ),
        )

    rl_exclude = list(rl.exclude_paths)
    if ws_path not in rl_exclude:
        rl_exclude.append(ws_path)

    unauth_identifier = _build_unauth_identifier(trusted)
    unauth_rate_limit = LitestarRateLimitConfig(
        rate_limit=(rl.time_unit, rl.unauth_max_requests),  # type: ignore[arg-type]
        exclude=rl_exclude,
        identifier_for_request=unauth_identifier,
        store="rate_limit_unauth",
    )
    auth_rate_limit = LitestarRateLimitConfig(
        rate_limit=(rl.time_unit, rl.auth_max_requests),  # type: ignore[arg-type]
        exclude=rl_exclude,
        identifier_for_request=_auth_identifier_for_request,
        store="rate_limit_auth",
    )

    exclude_paths = _build_auth_exclude_paths(
        api_config.auth,
        prefix,
        ws_path,
    )
    auth = api_config.auth.model_copy(
        update={"exclude_paths": exclude_paths},
    )
    auth_middleware = create_auth_middleware_class(auth)
    return [
        unauth_rate_limit.middleware,
        auth_middleware,
        RequestLoggingMiddleware,
        auth_rate_limit.middleware,
    ]
