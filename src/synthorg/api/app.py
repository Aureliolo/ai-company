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
from typing import TYPE_CHECKING, Any, get_args
from urllib.parse import unquote, urlparse

from litestar import Controller, Litestar, Request, Router
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
from pydantic import SecretStr

from synthorg import __version__
from synthorg.api.approval_store import ApprovalStore
from synthorg.api.auth.controller import require_password_changed
from synthorg.api.auth.csrf import create_csrf_middleware_class
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
from synthorg.api.controllers import BASE_CONTROLLERS
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
from synthorg.budget.coordination_store import (
    CoordinationMetricsStore,
)
from synthorg.budget.tracker import CostTracker  # noqa: TC001
from synthorg.communication.bus_protocol import MessageBus  # noqa: TC001
from synthorg.communication.delegation.record_store import (
    DelegationRecordStore,  # noqa: TC001
)
from synthorg.communication.event_stream.interrupt import InterruptStore
from synthorg.communication.event_stream.stream import EventStreamHub
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
from synthorg.hr.training.service import TrainingService  # noqa: TC001
from synthorg.notifications.factory import build_notification_dispatcher
from synthorg.observability import get_logger
from synthorg.observability.config import DEFAULT_SINKS, LogConfig
from synthorg.observability.events.api import (
    API_APP_SHUTDOWN,
    API_APP_STARTUP,
    API_APPROVAL_PUBLISH_FAILED,
    API_AUTH_LOCKOUT_CLEANUP,
    API_NETWORK_EXPOSURE_WARNING,
    API_SERVICE_AUTO_WIRED,
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
from synthorg.persistence.config import (
    PersistenceConfig,
    PostgresConfig,
    PostgresSslMode,
    SQLiteConfig,
)
from synthorg.persistence.factory import create_backend
from synthorg.persistence.filesystem_artifact_storage import (
    FileSystemArtifactStorage,
)
from synthorg.persistence.protocol import PersistenceBackend  # noqa: TC001
from synthorg.providers.errors import DriverNotRegisteredError
from synthorg.providers.health import ProviderHealthTracker  # noqa: TC001
from synthorg.providers.health_prober import ProviderHealthProber  # noqa: TC001
from synthorg.providers.registry import ProviderRegistry  # noqa: TC001
from synthorg.security.audit import AuditLog
from synthorg.security.timeout.scheduler import ApprovalTimeoutScheduler  # noqa: TC001
from synthorg.security.trust.config import TrustConfig
from synthorg.security.trust.disabled_strategy import DisabledTrustStrategy
from synthorg.security.trust.service import TrustService
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
    from synthorg.integrations.mcp_catalog.installations import (
        McpInstallationRepository,
    )
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


def _postgres_config_from_url(db_url: str) -> PostgresConfig:
    """Build a PostgresConfig from a libpq-style URL.

    Accepts the canonical form the CLI compose template emits:
    ``postgresql://user:password@host:5432/dbname``. Userinfo,
    hostname, port, and path are URL-decoded so credentials with
    reserved characters survive the round-trip. The parser is strict
    about presence of the user, password, host, and database fields
    -- ambiguous URLs are rejected up front so the auto-wire path
    fails fast rather than producing a half-configured backend that
    explodes later under load.

    The default ``ssl_mode`` from PostgresConfig (``"require"``)
    rejects plaintext connections; for local Docker compose where the
    backend talks to Postgres over an internal network without TLS,
    callers can override via ``SYNTHORG_POSTGRES_SSL_MODE`` env var.
    """
    parsed = urlparse(db_url)
    # Source-level logging for each validation branch so operators
    # debugging startup see the specific reason a DSN was rejected
    # even if the caller's catch block truncates the stack trace.
    # The caller also logs via logger.exception(...) on raise, but
    # that only captures the final ValueError message.
    if parsed.scheme not in {"postgres", "postgresql"}:
        msg = (
            f"SYNTHORG_DATABASE_URL scheme {parsed.scheme!r} is not "
            f"supported; expected 'postgresql://...'"
        )
        logger.warning(API_APP_STARTUP, error=msg, reason="invalid_scheme")
        raise ValueError(msg)
    if not parsed.hostname:
        msg = "SYNTHORG_DATABASE_URL is missing a host component"
        logger.warning(API_APP_STARTUP, error=msg, reason="missing_host")
        raise ValueError(msg)
    if not parsed.username or not parsed.password:
        msg = (
            "SYNTHORG_DATABASE_URL must include a username and password "
            "(postgresql://user:pass@host:port/db)"
        )
        logger.warning(API_APP_STARTUP, error=msg, reason="missing_credentials")
        raise ValueError(msg)
    database = parsed.path.lstrip("/")
    if not database:
        msg = (
            "SYNTHORG_DATABASE_URL must include a database name in the "
            "path (postgresql://user:pass@host:port/db)"
        )
        logger.warning(API_APP_STARTUP, error=msg, reason="missing_database")
        raise ValueError(msg)

    ssl_override = (os.environ.get("SYNTHORG_POSTGRES_SSL_MODE") or "").strip()
    ssl_kwargs: dict[str, Any] = {}
    if ssl_override:
        # Validate up front rather than letting Pydantic raise a less
        # actionable error during PostgresConfig construction. Derive
        # the allow-list from PostgresSslMode itself so adding or
        # removing a mode in persistence/config.py automatically keeps
        # this check in sync (no duplicate literal sets to drift).
        valid_modes = set(get_args(PostgresSslMode))
        if ssl_override not in valid_modes:
            msg = (
                f"SYNTHORG_POSTGRES_SSL_MODE={ssl_override!r} is invalid; "
                f"must be one of: {sorted(valid_modes)}"
            )
            logger.warning(API_APP_STARTUP, error=msg, reason="invalid_ssl_mode")
            raise ValueError(msg)
        ssl_kwargs["ssl_mode"] = ssl_override

    return PostgresConfig(
        host=unquote(parsed.hostname),
        port=parsed.port or 5432,
        database=unquote(database),
        username=unquote(parsed.username),
        password=SecretStr(unquote(parsed.password)),
        **ssl_kwargs,
    )


def _resolve_artifact_dir_env() -> str:
    """Resolve the postgres-mode artifact directory from the environment.

    Reads ``SYNTHORG_ARTIFACT_DIR`` and falls back to ``/data`` (the
    compose template's mount point) when the variable is unset or
    consists only of whitespace. Rejects relative or traversal paths
    at the env boundary so artifacts cannot end up in the process
    working directory or outside the mounted volume.

    Returns:
        The absolute directory string to hand to
        :class:`FileSystemArtifactStorage`.

    Raises:
        ValueError: If the env var is set to a non-absolute path. A
            previous implementation used ``os.environ.get(...) or
            "/data"`` which treated whitespace as truthy and
            collapsed to ``Path("")``; this helper strips first and
            then validates.
    """
    artifact_dir_str = os.environ.get("SYNTHORG_ARTIFACT_DIR", "").strip()
    if not artifact_dir_str:
        return "/data"
    if not Path(artifact_dir_str).is_absolute():
        msg = (
            f"SYNTHORG_ARTIFACT_DIR={artifact_dir_str!r} must be an absolute "
            f"path to avoid writing artifacts to the process working directory"
        )
        logger.warning(API_APP_STARTUP, error=msg, reason="non_absolute_artifact_dir")
        raise ValueError(msg)
    return artifact_dir_str


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
        # Lockout cleanup.
        try:
            if app_state.has_lockout_store:
                await app_state.lockout_store.cleanup_expired()
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.warning(
                API_AUTH_LOCKOUT_CLEANUP,
                error="Periodic lockout cleanup failed",
                exc_info=True,
            )


async def _maybe_promote_first_owner(app_state: AppState) -> None:
    """Promote the first user to owner if no owner exists.

    This is a one-time idempotent migration that runs on every boot
    until at least one user has the ``OrgRole.OWNER`` role.
    """
    if not app_state.has_persistence:
        return
    try:
        users = await app_state.persistence.users.list_users()
    except MemoryError, RecursionError:
        raise
    except Exception:
        logger.warning(
            API_APP_STARTUP,
            note="Owner auto-promote skipped: failed to list users",
            exc_info=True,
        )
        return
    if not users:
        return

    from synthorg.api.auth.models import OrgRole  # noqa: PLC0415

    has_owner = any(OrgRole.OWNER in u.org_roles for u in users)
    if has_owner:
        return

    # Promote the first user (by created_at, oldest first from list_users)
    first = users[0]
    promoted = first.model_copy(
        update={
            "org_roles": (*first.org_roles, OrgRole.OWNER),
            "updated_at": datetime.now(UTC),
        },
    )
    try:
        await app_state.persistence.users.save(promoted)
    except MemoryError, RecursionError:
        raise
    except Exception:
        logger.warning(
            API_APP_STARTUP,
            note="Owner auto-promote failed",
            exc_info=True,
        )
        return
    logger.info(
        API_APP_STARTUP,
        note="Auto-promoted first user to owner",
        user_id=first.id,
        username=first.username,
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


def _build_lifecycle(  # noqa: PLR0913, PLR0915, C901
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
    _training_memory_backend: object | None = None

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

    async def on_startup() -> None:  # noqa: C901, PLR0912, PLR0915
        nonlocal _ticket_cleanup_task, _auto_wired_dispatcher
        nonlocal _health_prober, _training_memory_backend
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
        # Wire Prometheus collector (no dependencies, runs in-process).
        # Non-fatal: /metrics degrades to 503 if this fails.
        if not app_state.has_prometheus_collector:
            try:
                from synthorg.observability.prometheus_collector import (  # noqa: PLC0415
                    PrometheusCollector,
                )

                app_state.set_prometheus_collector(PrometheusCollector())
            except MemoryError, RecursionError:
                raise
            except Exception:
                logger.warning(
                    API_APP_STARTUP,
                    error="Prometheus collector init failed (non-fatal)",
                    exc_info=True,
                )

        # Wire distributed trace handler and bridge OTLP log /
        # audit-chain export outcomes to the Prometheus collector.
        # ``wire_observability_callbacks`` is idempotent so it is
        # safe to re-run across test-fixture startup cycles.
        try:
            from synthorg.observability.startup_wiring import (  # noqa: PLC0415
                wire_observability_callbacks,
            )

            wire_observability_callbacks(app_state)
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.warning(
                API_APP_STARTUP,
                error="observability callback wiring failed (non-fatal)",
                exc_info=True,
            )

        # Wire workflow execution observer (needs connected persistence).
        # Idempotent: only register when no WorkflowExecutionObserver is
        # already present.  Startup may re-enter via the shared-app test
        # fixture, and ``register_observer`` is append-only.
        if (
            task_engine is not None
            and persistence is not None
            and hasattr(persistence, "workflow_definitions")
            and hasattr(persistence, "workflow_executions")
        ):
            from synthorg.engine.workflow.execution_observer import (  # noqa: PLC0415
                WorkflowExecutionObserver,
            )

            _already_registered = any(
                isinstance(o, WorkflowExecutionObserver)
                for o in getattr(task_engine, "_observers", ())
            )
            if not _already_registered:
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
                    distributed_task_queue=app_state.distributed_task_queue,
                )
                raise
        # Phase 3 auto-wire: TrainingService.
        # Needs agent_registry, tool_invocation_tracker, and
        # performance_tracker (all wired in Phase 1).  Uses
        # InMemoryBackend for the memory layer; production callers
        # inject a real Mem0 backend via the training_service param.
        if (
            not app_state.has_training_service
            and effective_config is not None
            and effective_config.training.enabled
            and app_state.has_agent_registry
            and app_state.has_tool_invocation_tracker
        ):
            try:
                from synthorg.hr.training.factory import (  # noqa: PLC0415
                    build_training_service,
                )
                from synthorg.memory.backends.inmemory import (  # noqa: PLC0415
                    InMemoryBackend,
                )

                _perf = app_state._performance_tracker  # noqa: SLF001
                if _perf is not None:
                    _mem = InMemoryBackend()
                    await _mem.connect()
                    try:
                        _ts = build_training_service(
                            config=effective_config.training,
                            memory_backend=_mem,
                            tracker=_perf,
                            registry=app_state.agent_registry,
                            approval_store=app_state.approval_store,
                            tool_tracker=app_state.tool_invocation_tracker,
                        )
                        app_state.set_training_service(_ts)
                    except MemoryError, RecursionError:
                        await _mem.disconnect()
                        raise
                    except Exception:
                        await _mem.disconnect()
                        raise
                    _training_memory_backend = _mem
            except MemoryError, RecursionError:
                raise
            except Exception:
                logger.warning(
                    API_APP_STARTUP,
                    error="Training service auto-wire failed (non-fatal)",
                    exc_info=True,
                )

        await _maybe_bootstrap_agents(app_state)
        await _maybe_promote_first_owner(app_state)
        # Idempotent: a prior ticket-cleanup task from a previous
        # startup may still be alive when lifespan re-enters (e.g.
        # shared-app test fixture).  Cancel it before spawning a
        # fresh one so tasks do not accumulate.  Any non-cancellation
        # exception from the prior task has already been logged by
        # ``_on_cleanup_task_done``; it is discarded here because we
        # are replacing the task, not handling its outcome.
        if _ticket_cleanup_task is not None and not _ticket_cleanup_task.done():
            _ticket_cleanup_task.cancel()
            try:
                await _ticket_cleanup_task
            except asyncio.CancelledError:
                pass
            except MemoryError, RecursionError:
                raise
            except Exception:  # noqa: S110 -- already logged via done-callback
                pass
        _ticket_cleanup_task = asyncio.create_task(
            _ticket_cleanup_loop(app_state),
            name="ws-ticket-cleanup",
        )
        _ticket_cleanup_task.add_done_callback(_on_cleanup_task_done)
        # Idempotent: stop any prior health prober instance before
        # starting a new one so probers do not accumulate when the
        # shared app re-enters lifespan.
        if _health_prober is not None:
            await _try_stop(
                _health_prober.stop(),
                API_APP_STARTUP,
                "Failed to stop prior health prober before restart",
            )
            _health_prober = None
        _health_prober = await _maybe_start_health_prober(app_state)

        # Start integration background services (non-fatal).
        if app_state.webhook_event_bridge is not None:
            try:
                await app_state.webhook_event_bridge.start()
            except MemoryError, RecursionError:
                raise
            except Exception:
                logger.warning(
                    API_APP_STARTUP,
                    error="Webhook event bridge startup failed (non-fatal)",
                    exc_info=True,
                )
        if app_state.health_prober_service is not None:
            try:
                await app_state.health_prober_service.start()
            except MemoryError, RecursionError:
                raise
            except Exception:
                logger.warning(
                    API_APP_STARTUP,
                    error="Integration health prober startup failed (non-fatal)",
                    exc_info=True,
                )
        if app_state.oauth_token_manager is not None:
            try:
                await app_state.oauth_token_manager.start()
            except MemoryError, RecursionError:
                raise
            except Exception:
                logger.warning(
                    API_APP_STARTUP,
                    error="OAuth token manager startup failed (non-fatal)",
                    exc_info=True,
                )

    async def on_shutdown() -> None:  # noqa: C901, PLR0912
        nonlocal _ticket_cleanup_task, _auto_wired_dispatcher
        nonlocal _health_prober, _training_memory_backend
        # Disconnect training memory backend if auto-wired.
        if _training_memory_backend is not None:
            disconnect = getattr(_training_memory_backend, "disconnect", None)
            if callable(disconnect):
                await _try_stop(
                    disconnect(),
                    API_APP_SHUTDOWN,
                    "Failed to disconnect training memory backend",
                )
            _training_memory_backend = None
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
        # Stop integration background services (reverse start order).
        if app_state.oauth_token_manager is not None:
            await _try_stop(
                app_state.oauth_token_manager.stop(),
                API_APP_SHUTDOWN,
                "Failed to stop OAuth token manager",
            )
        if app_state.health_prober_service is not None:
            await _try_stop(
                app_state.health_prober_service.stop(),
                API_APP_SHUTDOWN,
                "Failed to stop integration health prober",
            )
        if app_state.webhook_event_bridge is not None:
            await _try_stop(
                app_state.webhook_event_bridge.stop(),
                API_APP_SHUTDOWN,
                "Failed to stop webhook event bridge",
            )
        if app_state.has_tunnel_provider:
            await _try_stop(
                app_state.tunnel_provider.stop(),
                API_APP_SHUTDOWN,
                "Failed to stop tunnel provider",
            )
        # Stop every cached rate-limit coordinator and clear the
        # module-level factory so background poll tasks and bus
        # subscriptions cannot outlive the app (matters for
        # hot-reload / test teardown where ``create_app`` runs
        # multiple times in the same process).
        try:
            from synthorg.integrations.rate_limiting import (  # noqa: PLC0415
                shared_state as _rate_limit_shared_state,
            )

            await _rate_limit_shared_state.set_coordinator_factory(None)
        except Exception:
            logger.warning(
                API_APP_SHUTDOWN,
                error="Failed to stop rate-limit coordinators",
                exc_info=True,
            )
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
            distributed_task_queue=app_state.distributed_task_queue,
        )
        if app_state.has_notification_dispatcher:
            await _try_stop(
                app_state.notification_dispatcher.close(),
                API_APP_SHUTDOWN,
                "Failed to stop notification dispatcher",
            )
        # Close A2A outbound HTTP client if wired.
        try:
            a2a_client_obj = app_state._a2a_client  # noqa: SLF001
            if a2a_client_obj is not None and hasattr(a2a_client_obj, "aclose"):
                await a2a_client_obj.aclose()
        except Exception:
            logger.warning(
                API_APP_SHUTDOWN,
                error="Failed to close A2A client",
                exc_info=True,
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


def _build_default_trust_service() -> TrustService:
    """Build a default no-op TrustService for agent health queries."""
    return TrustService(
        strategy=DisabledTrustStrategy(),
        config=TrustConfig(),
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


def create_app(  # noqa: C901, PLR0912, PLR0913, PLR0915
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
    audit_log: AuditLog | None = None,
    trust_service: TrustService | None = None,
    coordination_metrics_store: CoordinationMetricsStore | None = None,
    training_service: TrainingService | None = None,
    event_stream_hub: EventStreamHub | None = None,
    interrupt_store: InterruptStore | None = None,
    _skip_lifecycle_shutdown: bool = False,
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
        audit_log: Pre-built audit log (auto-wired if None).
        trust_service: Pre-built trust service.
        coordination_metrics_store: Pre-built metrics store
            (auto-wired if None).
        training_service: Pre-built training service (auto-wired
            in startup if None and dependencies are available).
        event_stream_hub: Pre-built event stream hub (auto-created
            if None).
        interrupt_store: Pre-built interrupt store (auto-created
            if None).
        _skip_lifecycle_shutdown: Test-only flag.  When ``True``, the
            Litestar app is built with an empty ``on_shutdown`` list so
            the lifespan exit is a no-op.  Used by the session-scoped
            test fixture in ``tests/unit/api/conftest.py`` to reuse the
            same app across tests without tearing down the task engine,
            message bus, and persistence between each one.  Never use
            in production: shutdown hooks perform critical cleanup
            (task-engine drain, persistence disconnect, health prober
            stop, etc.).

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

    # Read persistence env vars unconditionally so downstream code
    # (e.g. the secret-backend gate below) can still observe which
    # environment choice won, even when ``persistence`` was injected
    # by the caller rather than auto-wired here.
    db_url = (os.environ.get("SYNTHORG_DATABASE_URL") or "").strip()
    db_path = (os.environ.get("SYNTHORG_DB_PATH") or "").strip()

    # Auto-wire persistence from CLI-provided env vars. The CLI compose
    # template sets ONE of these per init choice:
    #   * SYNTHORG_DATABASE_URL=postgresql://user:pass@host:port/db   (postgres)
    #   * SYNTHORG_DB_PATH=/data/synthorg.db                          (sqlite)
    # Postgres takes precedence so a half-converted state (both env
    # vars present) does not silently fall back to SQLite. The startup
    # lifecycle handles connect() + migrate() + auth service creation.
    if persistence is None:
        if db_url:
            try:
                pg_config = _postgres_config_from_url(db_url)
                persistence = create_backend(
                    PersistenceConfig(backend="postgres", postgres=pg_config),
                )
            except MemoryError, RecursionError:
                raise
            except Exception:
                logger.exception(
                    API_APP_STARTUP,
                    error="Postgres persistence creation failed",
                )
                raise
            logger.info(
                API_APP_STARTUP,
                note="Auto-wired Postgres persistence from SYNTHORG_DATABASE_URL",
                host=pg_config.host,
                database=pg_config.database,
            )
            # Postgres has no on-disk artifact directory tied to the DB
            # path, so default artifact storage to /data (the standard
            # data volume in the CLI compose template) when not set.
            if artifact_storage is None:
                artifact_dir_str = _resolve_artifact_dir_env()
                artifact_storage = FileSystemArtifactStorage(
                    data_dir=Path(artifact_dir_str),
                )
                logger.info(
                    API_APP_STARTUP,
                    note="Auto-wired filesystem artifact storage (postgres mode)",
                    data_dir=artifact_dir_str,
                )
        elif db_path:
            resolved_db_path = Path(db_path)
            try:
                persistence = create_backend(
                    PersistenceConfig(sqlite=SQLiteConfig(path=db_path)),
                )
            except MemoryError, RecursionError:
                raise
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
    distributed_task_queue = phase1.distributed_task_queue

    # ── Meeting auto-wire: orchestrator + scheduler (Phase 1 level) ──
    meeting_wire = auto_wire_meetings(
        effective_config=effective_config,
        meeting_orchestrator=meeting_orchestrator,
        meeting_scheduler=meeting_scheduler,
        agent_registry=agent_registry,
        provider_registry=provider_registry,
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

    # -- Integration services auto-wire ──────────────────────────────────
    connection_catalog = None
    oauth_token_manager = None
    health_prober_service = None
    tunnel_provider = None
    webhook_event_bridge = None
    mcp_catalog_service = None
    mcp_installations_repo: McpInstallationRepository | None = None

    # Bundled MCP catalog is stateless (loads static JSON) and has no
    # runtime dependencies, so it is wired unconditionally.
    try:
        from synthorg.integrations.mcp_catalog.service import (  # noqa: PLC0415
            CatalogService,
        )

        mcp_catalog_service = CatalogService()
        logger.info(API_SERVICE_AUTO_WIRED, service="mcp_catalog_service")
    except MemoryError, RecursionError:
        raise
    except Exception:
        logger.warning(
            API_APP_STARTUP,
            error="MCP catalog auto-wire failed (non-fatal)",
            exc_info=True,
        )

    # MCP installations repo: SQLite-backed when persistence is
    # already connected and exposes an aiosqlite handle, otherwise
    # an in-memory stub that keeps install/uninstall callable (so the
    # endpoint works in tests and dev without a database). The merged
    # MCPConfig is stitched at bridge startup time via
    # ``synthorg.integrations.mcp_catalog.install.merge_installed_servers``.
    #
    # NB: ``create_app`` runs synchronously on every test that builds a
    # Litestar app, so we MUST NOT call into code that raises on an
    # unconnected backend or captures a traceback per miss. Both are
    # hot-path regressions at suite scale. Check ``is_connected`` up
    # front and fall through silently to in-memory otherwise.
    try:
        from synthorg.integrations.mcp_catalog.sqlite_repo import (  # noqa: PLC0415
            InMemoryMcpInstallationRepository,
            SQLiteMcpInstallationRepository,
        )

        sqlite_db = None
        if persistence is not None and getattr(persistence, "is_connected", False):
            get_db_fn = getattr(persistence, "get_db", None)
            if callable(get_db_fn):
                try:
                    sqlite_db = get_db_fn()
                except MemoryError, RecursionError:
                    raise
                except Exception:
                    # Fall through to in-memory silently; the repo is a
                    # degraded-mode fallback by design and a startup
                    # warning here would fire on every test that builds
                    # an app without a SQLite backend.
                    sqlite_db = None
        if sqlite_db is not None:
            mcp_installations_repo = SQLiteMcpInstallationRepository(sqlite_db)
            logger.info(
                API_SERVICE_AUTO_WIRED,
                service="mcp_installations_repo",
                backend="sqlite",
            )
        else:
            mcp_installations_repo = InMemoryMcpInstallationRepository()
            logger.debug(
                API_SERVICE_AUTO_WIRED,
                service="mcp_installations_repo",
                backend="in_memory",
            )
    except MemoryError, RecursionError:
        raise
    except Exception:
        logger.warning(
            API_APP_STARTUP,
            error="MCP installations repo auto-wire failed (non-fatal)",
            exc_info=True,
        )

    if effective_config.integrations.enabled and persistence is not None:
        try:
            from synthorg.integrations.connections.catalog import (  # noqa: PLC0415
                ConnectionCatalog,
            )
            from synthorg.integrations.connections.secret_backends.factory import (  # noqa: PLC0415
                create_secret_backend,
            )
            from synthorg.integrations.health.prober import (  # noqa: PLC0415
                HealthProberService,
                bind_health_check_catalog,
            )
            from synthorg.integrations.oauth.token_manager import (  # noqa: PLC0415
                OAuthTokenManager,
            )
            from synthorg.integrations.tunnel.ngrok_adapter import (  # noqa: PLC0415
                NgrokAdapter,
            )

            # Prefer the active SQLite persistence path so the
            # encrypted_sqlite secret backend lands in the same DB
            # file as ``connections`` -- otherwise a diverging
            # SYNTHORG_DB_PATH can orphan connection_secrets in a
            # separate file or fail outright.
            #
            # Resolution order:
            #   1. ``resolved_db_path`` -- populated when persistence
            #      was auto-wired from ``SYNTHORG_DB_PATH``.
            #   2. Injected persistence's SQLite config path --
            #      picked up when ``create_app()`` was handed an
            #      already-built ``SQLitePersistenceBackend``.
            #   3. ``SYNTHORG_DB_PATH`` env var as a last resort.
            #
            # Resolve a SQLite path for the encrypted_sqlite backend.
            # Postgres mode has no SQLite file at all, so the path stays
            # None there -- the auto-select below promotes the default
            # ``encrypted_sqlite`` config to ``encrypted_postgres``.
            secret_db_path: str | None
            postgres_mode = bool(db_url)
            if resolved_db_path is not None:
                secret_db_path = str(resolved_db_path)
            elif postgres_mode:
                secret_db_path = None
            else:
                secret_db_path = None
                injected_cfg = getattr(persistence, "_config", None)
                injected_path = getattr(injected_cfg, "path", None)
                if (
                    isinstance(injected_path, str)
                    and injected_path
                    and injected_path != ":memory:"
                ):
                    secret_db_path = injected_path
                else:
                    env_db_path = (os.environ.get("SYNTHORG_DB_PATH") or "").strip()
                    secret_db_path = env_db_path or None

            # Wire a lazy pool getter for the encrypted_postgres
            # backend. ``persistence.connect()`` runs later in the
            # startup lifecycle (_safe_startup), so we cannot acquire
            # a pool during create_app itself -- ``get_db()`` would
            # raise ``PersistenceConnectionError`` and permanently
            # lock the secret backend into env_var for the life of
            # the process. Passing ``persistence.get_db`` as a
            # callable defers the lookup to the first store/retrieve,
            # which always runs after startup has succeeded. A
            # broken pool at first use surfaces as a normal
            # ``SecretStorageError`` with full context.
            pg_pool_getter = persistence.get_db if postgres_mode else None

            # Auto-select the correct Fernet-backed adapter for the
            # active persistence backend. See
            # ``resolve_secret_backend_config`` in factory.py for the
            # full rule table -- this call honours explicit config,
            # promotes the default to match postgres persistence, and
            # downgrades to env_var with an ERROR log when the master
            # key is unset or the underlying store is unavailable.
            from synthorg.integrations.connections.secret_backends.factory import (  # noqa: PLC0415
                resolve_secret_backend_config,
            )

            selection = resolve_secret_backend_config(
                effective_config.integrations.secret_backend,
                postgres_mode=postgres_mode,
                pg_pool_available=pg_pool_getter is not None,
                sqlite_db_path=secret_db_path,
            )
            if selection.reason:
                log_fn = {
                    "info": logger.info,
                    "warning": logger.warning,
                    "error": logger.error,
                }.get(selection.level, logger.info)
                log_fn(API_APP_STARTUP, note=selection.reason)
            secret_backend = create_secret_backend(
                selection.config,
                db_path=secret_db_path,
                pg_pool=pg_pool_getter,
            )
            connection_catalog = ConnectionCatalog(
                repository=persistence.connections,
                secret_backend=secret_backend,
            )
            bind_health_check_catalog(connection_catalog)
            logger.info(API_SERVICE_AUTO_WIRED, service="connection_catalog")

            health_cfg = effective_config.integrations.health
            health_prober_service = HealthProberService(
                catalog=connection_catalog,
                interval_seconds=health_cfg.check_interval_seconds,
                unhealthy_threshold=health_cfg.unhealthy_threshold,
            )
            logger.info(API_SERVICE_AUTO_WIRED, service="health_prober_service")

            oauth_token_manager = OAuthTokenManager(
                catalog=connection_catalog,
                refresh_threshold_seconds=effective_config.integrations.oauth.auto_refresh_threshold_seconds,
            )
            logger.info(API_SERVICE_AUTO_WIRED, service="oauth_token_manager")

            tunnel_provider = NgrokAdapter(
                auth_token_env=effective_config.integrations.tunnel.auth_token_env,
            )
            logger.info(API_SERVICE_AUTO_WIRED, service="tunnel_provider")

            if message_bus is not None and ceremony_scheduler is not None:
                from synthorg.engine.workflow.webhook_bridge import (  # noqa: PLC0415
                    WebhookEventBridge,
                )

                webhook_event_bridge = WebhookEventBridge(
                    bus=message_bus,
                    ceremony_scheduler=ceremony_scheduler,
                )
                logger.info(
                    API_SERVICE_AUTO_WIRED,
                    service="webhook_event_bridge",
                )

            if message_bus is not None:
                from synthorg.integrations.rate_limiting.shared_state import (  # noqa: PLC0415
                    SharedRateLimitCoordinator,
                    set_coordinator_factory_sync,
                )

                _bus = message_bus
                _catalog = connection_catalog

                def _make_coordinator(
                    name: str,
                ) -> SharedRateLimitCoordinator:
                    # Honour the connection's configured rate
                    # limiter so each coordinator enforces the
                    # correct per-connection global budget. Previously
                    # the default 60 RPM was hard-coded, which
                    # silently ignored any higher/lower setting on
                    # the connection row.
                    max_rpm = 60
                    try:
                        conn = _catalog._cache.get(name)  # noqa: SLF001
                        if (
                            conn is not None
                            and conn.rate_limiter is not None
                            and conn.rate_limiter.max_requests_per_minute > 0
                        ):
                            max_rpm = conn.rate_limiter.max_requests_per_minute
                    except Exception:
                        logger.warning(
                            API_SERVICE_AUTO_WIRED,
                            service="rate_limit_coordinator_factory",
                            note=(
                                "could not read rate_limit_rpm from "
                                "catalog cache; using default"
                            ),
                            connection_name=name,
                            exc_info=True,
                        )
                    return SharedRateLimitCoordinator(
                        bus=_bus,
                        connection_name=name,
                        max_rpm=max_rpm,
                    )

                set_coordinator_factory_sync(_make_coordinator)
                logger.info(
                    API_SERVICE_AUTO_WIRED,
                    service="rate_limit_coordinator_factory",
                )
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.warning(
                API_APP_STARTUP,
                error="Integration services auto-wire failed (non-fatal)",
                exc_info=True,
            )

    # Auto-wire control-plane services when not injected.
    if audit_log is None:
        audit_log = AuditLog()
    if coordination_metrics_store is None:
        coordination_metrics_store = CoordinationMetricsStore()
    if trust_service is None:
        trust_service = _build_default_trust_service()

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
        audit_log=audit_log,
        trust_service=trust_service,
        coordination_metrics_store=coordination_metrics_store,
        event_stream_hub=event_stream_hub or EventStreamHub(),
        interrupt_store=interrupt_store or InterruptStore(),
        connection_catalog=connection_catalog,
        oauth_token_manager=oauth_token_manager,
        health_prober_service=health_prober_service,
        tunnel_provider=tunnel_provider,
        webhook_event_bridge=webhook_event_bridge,
        mcp_catalog_service=mcp_catalog_service,
        mcp_installations_repo=mcp_installations_repo,
        training_service=training_service,
        startup_time=time.monotonic(),
    )
    if distributed_task_queue is not None:
        app_state.set_distributed_task_queue(distributed_task_queue)

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
    middleware = _build_middleware(
        api_config,
        a2a_enabled=effective_config.a2a.enabled,
    )

    # Integration controllers add ~20 routes (~0.7s of Litestar
    # registration per create_app). Skip them entirely when the
    # integrations subsystem is disabled, so unit tests that do not
    # exercise integration endpoints pay no registration cost.
    #
    # When enabled, gate each controller by its own collaborators
    # instead of a single boolean. ``MCPCatalogController`` only
    # needs ``mcp_catalog_service``; ``WebhooksController`` needs a
    # bus; ``TunnelController`` needs ``tunnel_provider``. A single
    # global gate either under-exposes controllers that are ready
    # or over-exposes ones whose dependencies failed to auto-wire.
    integration_controllers: tuple[type[Controller], ...] = ()
    if effective_config.integrations.enabled:
        from synthorg.api.controllers.connections import (  # noqa: PLC0415
            ConnectionsController,
        )
        from synthorg.api.controllers.integration_health import (  # noqa: PLC0415
            IntegrationHealthController,
        )
        from synthorg.api.controllers.mcp_catalog import (  # noqa: PLC0415
            MCPCatalogController,
        )
        from synthorg.api.controllers.oauth import OAuthController  # noqa: PLC0415
        from synthorg.api.controllers.tunnel import (  # noqa: PLC0415
            TunnelController,
        )
        from synthorg.api.controllers.webhooks import (  # noqa: PLC0415
            WebhooksController,
        )

        controller_readiness: tuple[
            tuple[type[Controller], tuple[tuple[str, object], ...]], ...
        ] = (
            (
                ConnectionsController,
                (("connection_catalog", connection_catalog),),
            ),
            (
                IntegrationHealthController,
                (("connection_catalog", connection_catalog),),
            ),
            (
                OAuthController,
                (
                    ("connection_catalog", connection_catalog),
                    ("persistence", persistence),
                ),
            ),
            (
                WebhooksController,
                (
                    ("connection_catalog", connection_catalog),
                    ("message_bus", message_bus),
                ),
            ),
            (
                MCPCatalogController,
                (("mcp_catalog_service", mcp_catalog_service),),
            ),
            (
                TunnelController,
                (("tunnel_provider", tunnel_provider),),
            ),
        )
        ready: list[type[Controller]] = []
        for controller_cls, deps in controller_readiness:
            missing = [name for name, value in deps if value is None]
            if missing:
                logger.warning(
                    API_APP_STARTUP,
                    note="skipping integration controller (missing deps)",
                    controller=controller_cls.__name__,
                    missing=missing,
                )
                continue
            ready.append(controller_cls)
        integration_controllers = tuple(ready)

    # ── A2A gateway auto-wire ─────────────────────────────────────
    a2a_controllers: tuple[type[Controller], ...] = ()
    a2a_root_controllers: tuple[type[Controller], ...] = ()
    if effective_config.a2a.enabled:
        try:
            from synthorg.a2a.agent_card import (  # noqa: PLC0415
                AgentCardBuilder,
            )
            from synthorg.a2a.models import A2AAuthSchemeInfo  # noqa: PLC0415
            from synthorg.a2a.well_known import (  # noqa: PLC0415
                WellKnownAgentCardController,
            )

            auth_schemes = (
                A2AAuthSchemeInfo(
                    scheme=str(
                        effective_config.a2a.auth.inbound_scheme,
                    ),
                ),
            )
            card_builder = AgentCardBuilder(
                default_auth_schemes=auth_schemes,
            )
            app_state.set_a2a_card_builder(card_builder)
            a2a_root_controllers = (WellKnownAgentCardController,)

            # Outbound client + JSON-RPC gateway need the connection
            # catalog and integrations enabled.
            if effective_config.integrations.enabled and connection_catalog is not None:
                import httpx  # noqa: PLC0415

                from synthorg.a2a.client import A2AClient  # noqa: PLC0415
                from synthorg.a2a.gateway import (  # noqa: PLC0415
                    A2AGatewayController,
                )
                from synthorg.a2a.peer_registry import (  # noqa: PLC0415
                    PeerRegistry,
                )

                peer_registry = PeerRegistry()
                a2a_http_client = httpx.AsyncClient(timeout=30.0)
                from synthorg.tools.network_validator import (  # noqa: PLC0415
                    NetworkPolicy,
                )

                a2a_network_policy = NetworkPolicy()
                a2a_client = A2AClient(
                    connection_catalog,
                    network_validator=a2a_network_policy,
                    http_client=a2a_http_client,
                )

                app_state.set_a2a_peer_registry(peer_registry)
                app_state.set_a2a_client(a2a_client)
                a2a_controllers = (A2AGatewayController,)

            logger.info(
                API_SERVICE_AUTO_WIRED,
                service="a2a_gateway",
            )
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.warning(
                API_APP_STARTUP,
                error="A2A gateway auto-wire failed (non-fatal)",
                exc_info=True,
            )

    api_router = Router(
        path=api_config.api_prefix,
        route_handlers=[
            *BASE_CONTROLLERS,
            *integration_controllers,
            *a2a_controllers,
            ws_handler,
        ],
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
    if _skip_lifecycle_shutdown:
        shutdown = []

    return Litestar(
        route_handlers=[api_router, *a2a_root_controllers],
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
    *,
    a2a_enabled: bool = False,
) -> tuple[str, ...]:
    """Compute auth middleware exclude paths with fail-safe defaults."""
    setup_status_path = f"^{prefix}/setup/status$"
    metrics_path = f"^{prefix}/metrics$"
    # The OAuth provider redirects the user's browser here without a
    # session cookie, so the global auth middleware has to let it
    # through. CSRF protection is handled by the state token the
    # callback validates against the oauth_states repo.
    oauth_callback_path = f"^{prefix}/oauth/callback$"
    exclude_paths = (
        auth.exclude_paths
        if auth.exclude_paths is not None
        else (
            f"^{prefix}/health$",
            metrics_path,
            "^/docs",
            "^/api$",
            f"^{prefix}/auth/setup$",
            f"^{prefix}/auth/login$",
            setup_status_path,
            oauth_callback_path,
        )
    )
    if metrics_path not in exclude_paths:
        exclude_paths = (*exclude_paths, metrics_path)
    if setup_status_path not in exclude_paths:
        exclude_paths = (*exclude_paths, setup_status_path)
    if ws_path not in exclude_paths:
        exclude_paths = (*exclude_paths, ws_path)
    if oauth_callback_path not in exclude_paths:
        exclude_paths = (*exclude_paths, oauth_callback_path)
    if a2a_enabled:
        a2a_gateway_path = f"^{prefix}/a2a"
        well_known_path = r"^/\.well-known"
        if a2a_gateway_path not in exclude_paths:
            exclude_paths = (*exclude_paths, a2a_gateway_path)
        if well_known_path not in exclude_paths:
            exclude_paths = (*exclude_paths, well_known_path)
    return exclude_paths


def _build_middleware(
    api_config: ApiConfig,
    *,
    a2a_enabled: bool = False,
) -> list[Middleware]:
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
        a2a_enabled=a2a_enabled,
    )
    auth = api_config.auth.model_copy(
        update={"exclude_paths": exclude_paths},
    )
    auth_middleware = create_auth_middleware_class(auth)

    # CSRF middleware: exempt login/setup (they set the cookie, client
    # cannot carry a CSRF token on the first request) and health.
    csrf_exempt = frozenset(
        {
            f"{prefix}/auth/login",
            f"{prefix}/auth/setup",
            f"{prefix}/health",
        }
    )
    csrf_middleware = create_csrf_middleware_class(
        auth,
        exempt_paths=csrf_exempt,
    )

    return [
        unauth_rate_limit.middleware,
        csrf_middleware,
        auth_middleware,
        RequestLoggingMiddleware,
        auth_rate_limit.middleware,
    ]
