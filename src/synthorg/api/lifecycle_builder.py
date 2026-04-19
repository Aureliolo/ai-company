"""Startup/shutdown lifecycle builder for the Litestar application.

Contains the two-phase (construct + on_startup) wiring helpers that
were previously inlined in ``api/app.py``.
"""

import asyncio
import contextlib
from typing import TYPE_CHECKING, cast

from synthorg import __version__
from synthorg.api.lifecycle import (
    _maybe_start_health_prober,
    _safe_shutdown,
    _safe_startup,
    _try_stop,
)
from synthorg.notifications.factory import build_notification_dispatcher
from synthorg.observability import get_logger
from synthorg.observability.events.api import (
    API_APP_SHUTDOWN,
    API_APP_STARTUP,
    API_AUTH_LOCKOUT_CLEANUP,
    API_SERVICE_AUTO_WIRE_FAILED,
    API_SERVICE_AUTO_WIRED,
    API_SESSION_CLEANUP,
    API_WS_TICKET_CLEANUP,
)
from synthorg.observability.events.setup import SETUP_AGENT_BOOTSTRAP_FAILED
from synthorg.settings.dispatcher import SettingsChangeDispatcher
from synthorg.settings.enums import SettingNamespace
from synthorg.settings.subscribers import (
    BackupSettingsSubscriber,
    MemorySettingsSubscriber,
    ObservabilitySettingsSubscriber,
    ProviderSettingsSubscriber,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence
    from datetime import datetime as _datetime

    from synthorg.api.bus_bridge import MessageBusBridge
    from synthorg.api.state import AppState
    from synthorg.backup.service import BackupService
    from synthorg.communication.bus_protocol import MessageBus
    from synthorg.communication.meeting.scheduler import MeetingScheduler
    from synthorg.config.schema import RootConfig
    from synthorg.engine.task_engine import TaskEngine
    from synthorg.persistence.protocol import PersistenceBackend
    from synthorg.providers.health_prober import ProviderHealthProber
    from synthorg.security.timeout.scheduler import ApprovalTimeoutScheduler
    from synthorg.settings.service import SettingsService
    from synthorg.settings.subscriber import SettingsSubscriber

    _ = _datetime  # keep import consistent with original module

logger = get_logger(__name__)


async def _resolve_ticket_cleanup_interval(app_state: AppState) -> float:
    """Resolve the ticket cleanup interval, falling back to 60 seconds.

    A settings-backend outage, missing setting, or malformed value must
    not kill the cleanup task -- otherwise expired WS tickets and
    sessions accumulate indefinitely until the next restart. Any
    resolver failure is logged and the built-in default is returned.
    """
    if not app_state.has_config_resolver:
        return 60.0
    try:
        return await app_state.config_resolver.get_float(
            SettingNamespace.API.value, "ticket_cleanup_interval_seconds"
        )
    except asyncio.CancelledError:
        raise
    except MemoryError, RecursionError:
        raise
    except Exception:
        logger.warning(
            API_WS_TICKET_CLEANUP,
            error=(
                "Failed to resolve ticket_cleanup_interval_seconds;"
                " falling back to 60.0 seconds"
            ),
            exc_info=True,
        )
        return 60.0


async def _ticket_cleanup_loop(app_state: AppState) -> None:
    """Periodically prune expired WS tickets and sessions."""
    while True:
        await asyncio.sleep(await _resolve_ticket_cleanup_interval(app_state))
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
    from datetime import UTC, datetime  # noqa: PLC0415

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

        # Auto-wire the agent registry's identity-versioning service now
        # that persistence is connected.  Running this before
        # ``_safe_startup`` would access ``persistence.identity_versions``
        # on a disconnected backend, which raises and drops the system
        # into a no-versioning state (lost audit trail on rollback/evolve).
        if (
            app_state.has_agent_registry
            and persistence is not None
            and getattr(persistence, "is_connected", False)
            and not app_state.agent_registry.has_versioning
        ):
            try:
                from synthorg.versioning import VersioningService  # noqa: PLC0415

                app_state.agent_registry.bind_versioning(
                    VersioningService(persistence.identity_versions),
                )
                logger.info(
                    API_SERVICE_AUTO_WIRED,
                    service="agent_registry_versioning",
                )
            except MemoryError, RecursionError:
                raise
            except Exception as exc:
                logger.warning(
                    API_SERVICE_AUTO_WIRE_FAILED,
                    service="agent_registry_versioning",
                    error=f"{type(exc).__name__}: {exc}",
                    exc_info=True,
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
                from synthorg.api.auto_wire import auto_wire_settings  # noqa: PLC0415

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
        # Apply operator-tuned API bridge settings to mutable stores
        # that outlive this startup frame. Failure is non-fatal so the
        # app still boots with built-in defaults. Guarded by
        # ``bridge_config_applied`` so a re-entering Litestar lifespan
        # (shared-app test fixtures, multi-lifespan runs) does not
        # churn httpx/SMTP clients in the notification-dispatcher
        # sinks or rebuild the OAuth flow on every startup.
        if app_state.has_config_resolver and not app_state.bridge_config_applied:
            try:
                app_state.ticket_store.set_max_pending_per_user(
                    await app_state.config_resolver.get_int(
                        SettingNamespace.API.value,
                        "ws_ticket_max_pending_per_user",
                    )
                )
            except MemoryError, RecursionError:
                raise
            except Exception:
                logger.warning(
                    API_APP_STARTUP,
                    error=(
                        "Failed to apply ws_ticket_max_pending_per_user;"
                        " using built-in default"
                    ),
                    exc_info=True,
                )

            # Inject the resolver into services that were constructed
            # before AppState so their polling / refresh loops honour
            # operator-tuned settings.
            if app_state.oauth_token_manager is not None:
                app_state.oauth_token_manager.set_config_resolver(
                    app_state.config_resolver,
                )
            if app_state.webhook_event_bridge is not None:
                app_state.webhook_event_bridge.set_config_resolver(
                    app_state.config_resolver,
                )
            # Inject the resolver into the JetStream bus so history
            # queries honour the operator-tuned scan batch-size and
            # fetch timeout.
            _bus = app_state.message_bus if app_state.has_message_bus else None
            if _bus is not None:
                _set_resolver = getattr(_bus, "set_config_resolver", None)
                if callable(_set_resolver):
                    _set_resolver(app_state.config_resolver)

            # Resolve the audit-chain signing timeout and push it onto
            # every live ``AuditChainSink`` handler so runtime signing
            # calls honour the operator setting.
            try:
                signing_timeout = await app_state.config_resolver.get_float(
                    SettingNamespace.OBSERVABILITY.value,
                    "audit_chain_signing_timeout_seconds",
                )
            except MemoryError, RecursionError:
                raise
            except Exception:
                logger.warning(
                    API_APP_STARTUP,
                    error=(
                        "Failed to resolve"
                        " audit_chain_signing_timeout_seconds;"
                        " keeping sink default"
                    ),
                    exc_info=True,
                )
            else:
                from synthorg.observability.audit_chain.sink import (  # noqa: PLC0415
                    AuditChainSink,
                )
                from synthorg.observability.startup_wiring import (  # noqa: PLC0415
                    _iter_logging_handlers,
                )

                for _handler in _iter_logging_handlers():
                    if isinstance(_handler, AuditChainSink):
                        try:
                            _handler.set_signing_timeout_seconds(signing_timeout)
                        except MemoryError, RecursionError:
                            raise
                        except Exception:
                            logger.warning(
                                API_APP_STARTUP,
                                error=(
                                    "Failed to apply"
                                    " audit_chain_signing_timeout_seconds"
                                    " to handler"
                                ),
                                exc_info=True,
                            )

            # Rebuild the notification dispatcher with resolved adapter
            # timeouts so webhook/SMTP calls honour operator tuning.
            try:
                notif_bridge = (
                    await app_state.config_resolver.get_notifications_bridge_config()
                )
            except MemoryError, RecursionError:
                raise
            except Exception:
                logger.warning(
                    API_APP_STARTUP,
                    error=(
                        "Failed to resolve notifications bridge config;"
                        " keeping dispatcher default timeouts"
                    ),
                    exc_info=True,
                )
            else:
                if (
                    app_state.has_notification_dispatcher
                    and effective_config is not None
                ):
                    _new_dispatcher = build_notification_dispatcher(
                        effective_config.notifications,
                        bridge_config=notif_bridge,
                    )
                    _old_dispatcher = app_state.swap_notification_dispatcher(
                        _new_dispatcher
                    )
                    # Close the pre-startup dispatcher's sinks so their
                    # httpx clients do not leak. The swap returned the
                    # old instance atomically, so closing it now cannot
                    # race a concurrent reader landing on the new one.
                    if _old_dispatcher is not None:
                        try:
                            await _old_dispatcher.close()
                        except MemoryError, RecursionError:
                            raise
                        except Exception:
                            logger.warning(
                                API_APP_STARTUP,
                                error=(
                                    "Failed to close pre-startup notification"
                                    " dispatcher sinks after rebuild"
                                ),
                                exc_info=True,
                            )

            app_state.mark_bridge_config_applied()

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
        if app_state.escalation_sweeper is not None:
            try:
                await app_state.escalation_sweeper.start()
            except MemoryError, RecursionError:
                raise
            except Exception:
                logger.warning(
                    API_APP_STARTUP,
                    error="Escalation sweeper startup failed (non-fatal)",
                    exc_info=True,
                )
        if app_state.escalation_notify_subscriber is not None:
            try:
                await app_state.escalation_notify_subscriber.start()
            except MemoryError, RecursionError:
                raise
            except Exception:
                logger.warning(
                    API_APP_STARTUP,
                    error="Escalation notify subscriber startup failed (non-fatal)",
                    exc_info=True,
                )

    async def on_shutdown() -> None:  # noqa: C901, PLR0912
        nonlocal _ticket_cleanup_task, _auto_wired_dispatcher
        nonlocal _health_prober, _training_memory_backend
        # Disconnect training memory backend if auto-wired.
        if _training_memory_backend is not None:
            disconnect = getattr(_training_memory_backend, "disconnect", None)
            if callable(disconnect):
                # getattr + callable narrow statically only to ``object``
                # and "something callable", so the return type isn't
                # inferable.  Backends that expose a ``disconnect`` method
                # always return ``Awaitable[None]`` by contract
                # (see ``MemoryBackend.disconnect`` in training/memory).
                await _try_stop(
                    cast("Awaitable[None]", disconnect()),
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
        if app_state.escalation_notify_subscriber is not None:
            await _try_stop(
                app_state.escalation_notify_subscriber.stop(),
                API_APP_SHUTDOWN,
                "Failed to stop escalation notify subscriber",
            )
        if app_state.escalation_sweeper is not None:
            await _try_stop(
                app_state.escalation_sweeper.stop(),
                API_APP_SHUTDOWN,
                "Failed to stop escalation sweeper",
            )
        # Cancel any unresolved pending futures so coroutines awaiting
        # operator decisions get a clean CancelledError (instead of
        # hanging past shutdown) and the registry map is emptied.
        if app_state.escalation_registry is not None:
            await _try_stop(
                app_state.escalation_registry.close(),
                API_APP_SHUTDOWN,
                "Failed to close escalation pending-futures registry",
            )
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
