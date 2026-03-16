"""Tests for health check endpoint."""

from typing import Any
from unittest.mock import PropertyMock, patch

import pytest
from litestar.testing import TestClient

from synthorg.api.app import create_app
from tests.unit.api.fakes import FakeMessageBus, FakePersistenceBackend


@pytest.mark.unit
class TestHealthCheck:
    def test_returns_ok_when_all_healthy(self, test_client: TestClient[Any]) -> None:
        response = test_client.get("/api/v1/health")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["status"] == "ok"
        assert body["data"]["persistence"] is True
        assert body["data"]["message_bus"] is True
        assert "version" in body["data"]
        assert body["data"]["uptime_seconds"] >= 0

    def test_reports_degraded_when_bus_down(
        self,
        test_client: TestClient[Any],
        fake_message_bus: Any,
    ) -> None:
        fake_message_bus._running = False
        response = test_client.get("/api/v1/health")
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["status"] == "degraded"
        assert body["data"]["message_bus"] is False

    def test_reports_down_when_all_unhealthy(
        self,
        test_client: TestClient[Any],
        fake_persistence: Any,
        fake_message_bus: Any,
    ) -> None:
        fake_persistence._connected = False
        fake_message_bus._running = False
        response = test_client.get("/api/v1/health")
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["status"] == "down"


@pytest.mark.unit
class TestHealthCheckUnconfiguredServices:
    """Health endpoint with partially or fully unconfigured services."""

    @pytest.mark.parametrize(
        (
            "persistence_state",
            "bus_state",
            "expected_status",
            "expected_persistence",
            "expected_bus",
        ),
        [
            pytest.param(None, None, "ok", None, None, id="no_services"),
            pytest.param(
                "healthy", None, "ok", True, None, id="persistence_only_healthy"
            ),
            pytest.param(
                "unhealthy",
                None,
                "down",
                False,
                None,
                id="persistence_only_unhealthy",
            ),
            pytest.param(None, "healthy", "ok", None, True, id="bus_only_healthy"),
            pytest.param(
                None,
                "unhealthy",
                "down",
                None,
                False,
                id="bus_only_unhealthy",
            ),
        ],
    )
    async def test_unconfigured_services(
        self,
        persistence_state: str | None,
        bus_state: str | None,
        expected_status: str,
        expected_persistence: bool | None,
        expected_bus: bool | None,
    ) -> None:
        backend = None
        bus = None
        if persistence_state is not None:
            backend = FakePersistenceBackend()
            await backend.connect()
        if bus_state is not None:
            bus = FakeMessageBus()
            await bus.start()

        with TestClient(
            create_app(persistence=backend, message_bus=bus),
        ) as client:
            # Simulate post-startup failures after app lifecycle completes.
            if persistence_state == "unhealthy" and backend is not None:
                backend._connected = False
            if bus_state == "unhealthy" and bus is not None:
                bus._running = False

            response = client.get("/api/v1/health")
            assert response.status_code == 200
            body = response.json()
            assert body["data"]["status"] == expected_status
            assert body["data"]["persistence"] is expected_persistence
            assert body["data"]["message_bus"] is expected_bus


@pytest.mark.unit
class TestHealthCheckExceptionPaths:
    """Health endpoint when a configured service raises an exception."""

    @pytest.mark.parametrize(
        ("service_spec", "response_key"),
        [
            pytest.param(
                {
                    "factory": FakePersistenceBackend,
                    "init": "connect",
                    "kwarg": "persistence",
                    "attr": "health_check",
                    "patch_kw": {},
                },
                "persistence",
                id="persistence_exception",
            ),
            pytest.param(
                {
                    "factory": FakeMessageBus,
                    "init": "start",
                    "kwarg": "message_bus",
                    "attr": "is_running",
                    "patch_kw": {"new_callable": PropertyMock},
                },
                "message_bus",
                id="message_bus_exception",
            ),
        ],
    )
    async def test_service_exception_returns_false(
        self,
        service_spec: dict[str, Any],
        response_key: str,
    ) -> None:
        service = service_spec["factory"]()
        await getattr(service, service_spec["init"])()
        with (
            TestClient(
                create_app(**{service_spec["kwarg"]: service}),
            ) as client,
            patch.object(
                type(service),
                service_spec["attr"],
                side_effect=RuntimeError("test error"),
                **service_spec["patch_kw"],
            ),
        ):
            response = client.get("/api/v1/health")
            assert response.status_code == 200
            body = response.json()
            assert body["data"][response_key] is False
            assert body["data"]["status"] == "down"
