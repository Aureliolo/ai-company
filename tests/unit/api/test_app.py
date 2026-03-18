"""Tests for application factory."""

from typing import Any

import pytest
from litestar import Litestar
from litestar.testing import TestClient

from synthorg.api.app import create_app
from synthorg.api.middleware import _SECURITY_HEADERS
from synthorg.api.state import AppState
from synthorg.budget.tracker import CostTracker
from synthorg.communication.bus_memory import InMemoryMessageBus
from synthorg.engine.task_engine import TaskEngine


@pytest.mark.unit
class TestCreateApp:
    def test_returns_litestar_instance(
        self,
        fake_persistence: Any,
        fake_message_bus: Any,
        cost_tracker: Any,
        root_config: Any,
    ) -> None:
        app = create_app(
            config=root_config,
            persistence=fake_persistence,
            message_bus=fake_message_bus,
            cost_tracker=cost_tracker,
        )
        assert isinstance(app, Litestar)

    def test_openapi_schema_accessible(self, test_client: TestClient[Any]) -> None:
        response = test_client.get("/docs/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert data["info"]["title"] == "SynthOrg API"

    @pytest.mark.parametrize(
        ("header", "expected"),
        list(_SECURITY_HEADERS.items()),
    )
    def test_security_response_headers(
        self,
        test_client: TestClient[Any],
        header: str,
        expected: str,
    ) -> None:
        # Use a non-docs endpoint — /docs paths relax COOP for Scalar UI.
        response = test_client.get("/api/v1/health")
        assert response.headers.get(header) == expected


@pytest.mark.unit
class TestCreateAppEnvAutoWire:
    """Verify create_app auto-wires SQLite persistence from SYNTHORG_DB_PATH."""

    @pytest.mark.parametrize(
        ("env_value", "expect_persistence"),
        [
            (":memory:", True),
            (None, False),
        ],
        ids=["with_env_var", "without_env_var"],
    )
    def test_persistence_from_env(
        self,
        monkeypatch: pytest.MonkeyPatch,
        root_config: Any,
        env_value: str | None,
        expect_persistence: bool,
    ) -> None:
        """Persistence is auto-wired when env var is set, None otherwise."""
        if env_value is not None:
            monkeypatch.setenv("SYNTHORG_DB_PATH", env_value)
        else:
            monkeypatch.delenv("SYNTHORG_DB_PATH", raising=False)
        app = create_app(config=root_config)
        state = app.state["app_state"]
        assert state.has_persistence == expect_persistence


@pytest.mark.unit
class TestAppLifecycle:
    async def test_startup_partial_failure_cleanup(
        self,
        root_config: Any,
    ) -> None:
        """Persistence ok, bus fails → persistence cleaned up."""
        from synthorg.api.app import _safe_startup
        from synthorg.api.approval_store import ApprovalStore
        from synthorg.api.state import AppState
        from tests.unit.api.conftest import (
            FakeMessageBus,
            FakePersistenceBackend,
        )

        persistence = FakePersistenceBackend()
        bus = FakeMessageBus()
        app_state = AppState(
            config=root_config,
            approval_store=ApprovalStore(),
            persistence=persistence,
        )

        async def failing_start() -> None:
            msg = "bus boom"
            raise RuntimeError(msg)

        bus.start = failing_start  # type: ignore[method-assign]

        with pytest.raises(RuntimeError, match="bus boom"):
            await _safe_startup(
                persistence,
                bus,
                None,
                None,
                None,
                None,
                None,
                app_state,
            )
        # Persistence should have been disconnected during cleanup
        assert not persistence.is_connected

    async def test_shutdown_error_handling(self) -> None:
        """Shutdown errors are logged but don't propagate."""
        from synthorg.api.app import _safe_shutdown
        from tests.unit.api.conftest import FakePersistenceBackend

        persistence = FakePersistenceBackend()

        async def failing_disconnect() -> None:
            msg = "disconnect boom"
            raise RuntimeError(msg)

        persistence.disconnect = failing_disconnect  # type: ignore[method-assign]

        # Should not raise even when disconnect fails
        await _safe_shutdown(None, None, None, None, None, None, persistence)

    async def test_task_engine_failure_cleans_up(
        self,
        root_config: Any,
    ) -> None:
        """Task engine start fails → persistence + bus cleaned up."""
        from unittest.mock import MagicMock

        from synthorg.api.app import _safe_startup
        from synthorg.api.approval_store import ApprovalStore
        from synthorg.api.state import AppState
        from tests.unit.api.conftest import (
            FakeMessageBus,
            FakePersistenceBackend,
        )

        persistence = FakePersistenceBackend()
        bus = FakeMessageBus()
        mock_te = MagicMock()
        mock_te.start = MagicMock(side_effect=RuntimeError("engine boom"))
        mock_te.stop = MagicMock()

        app_state = AppState(
            config=root_config,
            approval_store=ApprovalStore(),
            persistence=persistence,
        )

        with pytest.raises(RuntimeError, match="engine boom"):
            await _safe_startup(
                persistence,
                bus,
                None,
                None,
                mock_te,
                None,
                None,
                app_state,
            )

        # Persistence and bus should be cleaned up
        assert not persistence.is_connected
        assert not bus.is_running

    async def test_settings_dispatcher_failure_cleans_up(
        self,
        root_config: Any,
    ) -> None:
        """Settings dispatcher start fails → persistence + bus cleaned up."""
        from unittest.mock import AsyncMock, MagicMock

        from synthorg.api.app import _safe_startup
        from synthorg.api.approval_store import ApprovalStore
        from synthorg.api.state import AppState
        from tests.unit.api.conftest import (
            FakeMessageBus,
            FakePersistenceBackend,
        )

        persistence = FakePersistenceBackend()
        bus = FakeMessageBus()
        mock_dispatcher = MagicMock()
        mock_dispatcher.start = AsyncMock(
            side_effect=RuntimeError("dispatcher boom"),
        )
        mock_dispatcher.stop = AsyncMock()

        app_state = AppState(
            config=root_config,
            approval_store=ApprovalStore(),
            persistence=persistence,
        )

        with pytest.raises(RuntimeError, match="dispatcher boom"):
            await _safe_startup(
                persistence,
                bus,
                None,
                mock_dispatcher,
                None,
                None,
                None,
                app_state,
            )

        # Persistence and bus should be cleaned up
        assert not persistence.is_connected
        assert not bus.is_running

    async def test_shutdown_task_engine_failure_does_not_propagate(self) -> None:
        """Task engine stop failure during shutdown is logged, not raised."""
        from unittest.mock import AsyncMock, MagicMock

        from synthorg.api.app import _safe_shutdown

        mock_te = MagicMock()
        mock_te.stop = AsyncMock(side_effect=RuntimeError("stop boom"))

        # Should not raise even when task engine stop fails
        await _safe_shutdown(mock_te, None, None, None, None, None, None)

    async def test_meeting_scheduler_lifecycle(
        self,
        root_config: Any,
    ) -> None:
        """Meeting scheduler start/stop are called during lifecycle."""
        from unittest.mock import AsyncMock, MagicMock

        from synthorg.api.app import _safe_shutdown, _safe_startup
        from synthorg.api.approval_store import ApprovalStore
        from synthorg.api.state import AppState
        from tests.unit.api.conftest import (
            FakeMessageBus,
            FakePersistenceBackend,
        )

        persistence = FakePersistenceBackend()
        bus = FakeMessageBus()
        mock_sched = MagicMock()
        mock_sched.start = AsyncMock()
        mock_sched.stop = AsyncMock()

        app_state = AppState(
            config=root_config,
            approval_store=ApprovalStore(),
            persistence=persistence,
        )

        await _safe_startup(
            persistence,
            bus,
            None,
            None,
            None,
            mock_sched,
            None,
            app_state,
        )
        mock_sched.start.assert_awaited_once()

        await _safe_shutdown(None, mock_sched, None, None, None, None, None)
        mock_sched.stop.assert_awaited_once()


@pytest.mark.unit
class TestTryStop:
    """Tests for the _try_stop helper."""

    async def test_try_stop_success(self) -> None:
        """Successful coroutine runs without error."""
        from synthorg.api.app import _try_stop

        called = False

        async def noop() -> None:
            nonlocal called
            called = True

        await _try_stop(noop(), "event", "error msg")
        assert called is True

    async def test_try_stop_exception_swallowed(self) -> None:
        """Non-fatal exceptions are swallowed (logged)."""
        from synthorg.api.app import _try_stop

        async def fail() -> None:
            msg = "boom"
            raise RuntimeError(msg)

        # Should not raise
        await _try_stop(fail(), "event", "error msg")

    async def test_try_stop_memory_error_reraises(self) -> None:
        """MemoryError is re-raised immediately."""
        from synthorg.api.app import _try_stop

        async def oom() -> None:
            raise MemoryError

        with pytest.raises(MemoryError):
            await _try_stop(oom(), "event", "error msg")

    async def test_try_stop_recursion_error_reraises(self) -> None:
        """RecursionError is re-raised immediately."""
        from synthorg.api.app import _try_stop

        async def recurse() -> None:
            raise RecursionError

        with pytest.raises(RecursionError):
            await _try_stop(recurse(), "event", "error msg")


@pytest.mark.unit
class TestAutoWirePhase1:
    """Phase 1 auto-wiring: services created at construction time."""

    def test_auto_wires_message_bus(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Message bus is auto-wired when not provided."""
        monkeypatch.setenv("SYNTHORG_DB_PATH", ":memory:")
        app = create_app()
        state: AppState = app.state["app_state"]
        assert state.has_message_bus

    def test_auto_wired_message_bus_is_in_memory(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Auto-wired message bus is InMemoryMessageBus."""
        monkeypatch.setenv("SYNTHORG_DB_PATH", ":memory:")
        app = create_app()
        state: AppState = app.state["app_state"]
        # Access the private field to check the concrete type.
        assert isinstance(state._message_bus, InMemoryMessageBus)

    def test_auto_wires_cost_tracker(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Cost tracker is auto-wired when not provided."""
        monkeypatch.setenv("SYNTHORG_DB_PATH", ":memory:")
        app = create_app()
        state: AppState = app.state["app_state"]
        assert isinstance(state._cost_tracker, CostTracker)

    def test_auto_wires_task_engine(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Task engine is auto-wired when persistence is available."""
        monkeypatch.setenv("SYNTHORG_DB_PATH", ":memory:")
        app = create_app()
        state: AppState = app.state["app_state"]
        assert state.has_task_engine
        assert isinstance(state._task_engine, TaskEngine)

    def test_task_engine_not_wired_without_persistence(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Task engine is not auto-wired without persistence."""
        monkeypatch.delenv("SYNTHORG_DB_PATH", raising=False)
        app = create_app()
        state: AppState = app.state["app_state"]
        assert not state.has_task_engine

    def test_explicit_services_not_overridden(
        self,
        fake_persistence: Any,
        fake_message_bus: Any,
        cost_tracker: Any,
        root_config: Any,
        fake_task_engine: Any,
    ) -> None:
        """Explicitly provided services are not replaced by auto-wiring."""
        app = create_app(
            config=root_config,
            persistence=fake_persistence,
            message_bus=fake_message_bus,
            cost_tracker=cost_tracker,
            task_engine=fake_task_engine,
        )
        state: AppState = app.state["app_state"]
        assert state._message_bus is fake_message_bus
        assert state._cost_tracker is cost_tracker
        assert state._task_engine is fake_task_engine

    def test_no_persistence_warns(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Warning is logged when no persistence is available."""
        monkeypatch.delenv("SYNTHORG_DB_PATH", raising=False)
        import structlog

        with structlog.testing.capture_logs() as logs:
            create_app()
        warning_logs = [
            e
            for e in logs
            if e.get("log_level") == "warning"
            and "No persistence backend available" in str(e.get("note", ""))
        ]
        assert len(warning_logs) >= 1


@pytest.mark.unit
class TestAutoWirePhase2:
    """Phase 2 auto-wiring: settings_service after persistence connects."""

    async def test_auto_wire_settings_creates_service(
        self,
        fake_persistence: Any,
        fake_message_bus: Any,
        root_config: Any,
    ) -> None:
        """_auto_wire_settings creates SettingsService on AppState."""
        from synthorg.api.app import _auto_wire_settings
        from synthorg.api.approval_store import ApprovalStore

        app_state = AppState(
            config=root_config,
            approval_store=ApprovalStore(),
            persistence=fake_persistence,
            message_bus=fake_message_bus,
        )
        assert not app_state.has_settings_service

        dispatcher = await _auto_wire_settings(
            fake_persistence,
            fake_message_bus,
            root_config,
            app_state,
            None,
        )

        assert app_state.has_settings_service
        assert app_state.has_config_resolver  # type: ignore[unreachable]
        assert app_state.has_provider_management
        # Dispatcher is created when bus is available
        assert dispatcher is not None

        # Clean up
        await dispatcher.stop()

    async def test_auto_wire_settings_without_bus(
        self,
        fake_persistence: Any,
        root_config: Any,
    ) -> None:
        """_auto_wire_settings works without a message bus."""
        from synthorg.api.app import _auto_wire_settings
        from synthorg.api.approval_store import ApprovalStore

        app_state = AppState(
            config=root_config,
            approval_store=ApprovalStore(),
            persistence=fake_persistence,
        )
        dispatcher = await _auto_wire_settings(
            fake_persistence,
            None,
            root_config,
            app_state,
            None,
        )

        assert app_state.has_settings_service
        # No dispatcher without a bus
        assert dispatcher is None

    def test_phase2_flag_set_when_no_settings(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """auto_wire_settings flag is True when settings_service not provided."""
        monkeypatch.setenv("SYNTHORG_DB_PATH", ":memory:")
        app = create_app()
        state: AppState = app.state["app_state"]
        # Before startup, settings not yet wired (Phase 2 pending)
        assert not state.has_settings_service
        # But Phase 1 services are wired
        assert state.has_message_bus
        assert state.has_task_engine

    def test_phase2_skipped_when_settings_provided(
        self,
        fake_persistence: Any,
        fake_message_bus: Any,
        root_config: Any,
    ) -> None:
        """Phase 2 is skipped when settings_service is explicitly provided."""
        import synthorg.settings.definitions  # noqa: F401
        from synthorg.settings.registry import get_registry
        from synthorg.settings.service import SettingsService

        settings_svc = SettingsService(
            repository=fake_persistence.settings,
            registry=get_registry(),
            config=root_config,
        )
        app = create_app(
            config=root_config,
            persistence=fake_persistence,
            message_bus=fake_message_bus,
            settings_service=settings_svc,
        )
        state: AppState = app.state["app_state"]
        assert state.has_settings_service
        # Verify it's the same instance we passed
        assert state._settings_service is settings_svc


@pytest.mark.unit
class TestAppStateSetSettingsService:
    """Tests for AppState.set_settings_service()."""

    def test_creates_resolver_and_management(
        self,
        fake_persistence: Any,
        root_config: Any,
    ) -> None:
        """set_settings_service creates ConfigResolver + ProviderManagement."""
        import synthorg.settings.definitions  # noqa: F401
        from synthorg.api.approval_store import ApprovalStore
        from synthorg.settings.registry import get_registry
        from synthorg.settings.service import SettingsService

        app_state = AppState(
            config=root_config,
            approval_store=ApprovalStore(),
            persistence=fake_persistence,
        )
        assert not app_state.has_settings_service
        assert not app_state.has_config_resolver
        assert not app_state.has_provider_management

        settings_svc = SettingsService(
            repository=fake_persistence.settings,
            registry=get_registry(),
            config=root_config,
        )
        app_state.set_settings_service(settings_svc)

        assert app_state.has_settings_service
        assert app_state.has_config_resolver  # type: ignore[unreachable]
        assert app_state.has_provider_management

    def test_raises_if_already_set(
        self,
        fake_persistence: Any,
        root_config: Any,
    ) -> None:
        """set_settings_service raises RuntimeError if called twice."""
        import synthorg.settings.definitions  # noqa: F401
        from synthorg.api.approval_store import ApprovalStore
        from synthorg.settings.registry import get_registry
        from synthorg.settings.service import SettingsService

        app_state = AppState(
            config=root_config,
            approval_store=ApprovalStore(),
            persistence=fake_persistence,
        )
        settings_svc = SettingsService(
            repository=fake_persistence.settings,
            registry=get_registry(),
            config=root_config,
        )
        app_state.set_settings_service(settings_svc)

        with pytest.raises(RuntimeError, match="already configured"):
            app_state.set_settings_service(settings_svc)
