"""Tests for provider health endpoint."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from litestar.testing import TestClient

from synthorg.config.schema import ProviderConfig, ProviderModelConfig, RootConfig
from synthorg.providers.health import (
    ProviderHealthRecord,
    ProviderHealthTracker,
)
from synthorg.settings.registry import get_registry
from synthorg.settings.service import SettingsService
from tests.unit.api.conftest import (
    FakeMessageBus,
    FakePersistenceBackend,
    make_auth_headers,
)

_NOW = datetime.now(UTC)
_HEADERS = make_auth_headers("ceo")


def _make_health_record(
    *,
    provider_name: str = "test-provider",
    timestamp: datetime | None = None,
    success: bool = True,
    response_time_ms: float = 100.0,
) -> ProviderHealthRecord:
    return ProviderHealthRecord(
        provider_name=provider_name,
        timestamp=timestamp or _NOW,
        success=success,
        response_time_ms=response_time_ms,
    )


def _build_provider_client(
    *,
    fake_persistence: FakePersistenceBackend,
    fake_message_bus: FakeMessageBus,
    provider_health_tracker: ProviderHealthTracker | None = None,
) -> TestClient[Any]:
    """Build a TestClient with a provider configured."""
    from synthorg.api.app import create_app
    from synthorg.api.auth.service import AuthService
    from synthorg.budget.tracker import CostTracker
    from tests.unit.api.conftest import _make_test_auth_service, _seed_test_users

    config = RootConfig(
        company_name="test",
        providers={
            "test-provider": ProviderConfig(
                driver="litellm",
                models=(
                    ProviderModelConfig(
                        id="test-small-001",
                        alias="small",
                    ),
                ),
            ),
        },
    )
    auth_service: AuthService = _make_test_auth_service()
    _seed_test_users(fake_persistence, auth_service)
    settings_service = SettingsService(
        repository=fake_persistence.settings,
        registry=get_registry(),
        config=config,
    )
    app = create_app(
        config=config,
        persistence=fake_persistence,
        message_bus=fake_message_bus,
        cost_tracker=CostTracker(),
        auth_service=auth_service,
        settings_service=settings_service,
        provider_health_tracker=provider_health_tracker or ProviderHealthTracker(),
    )
    return TestClient(app)


@pytest.mark.unit
class TestProviderHealth:
    def test_provider_not_found(
        self,
        test_client: TestClient[Any],
    ) -> None:
        resp = test_client.get("/api/v1/providers/nonexistent/health")
        assert resp.status_code == 404
        assert resp.json()["success"] is False

    def test_auth_required(self, test_client: TestClient[Any]) -> None:
        resp = test_client.get(
            "/api/v1/providers/test-provider/health",
            headers={"Authorization": "Bearer invalid"},
        )
        assert resp.status_code == 401

    def test_empty_health(
        self,
        fake_persistence: FakePersistenceBackend,
        fake_message_bus: FakeMessageBus,
    ) -> None:
        """Provider exists but no health records."""
        with _build_provider_client(
            fake_persistence=fake_persistence,
            fake_message_bus=fake_message_bus,
        ) as client:
            resp = client.get(
                "/api/v1/providers/test-provider/health",
                headers=_HEADERS,
            )
            assert resp.status_code == 200
            data = resp.json()["data"]
            assert data["health_status"] == "up"
            assert data["last_check_timestamp"] is None
            assert data["avg_response_time_ms"] is None
            assert data["error_rate_percent_24h"] == 0.0
            assert data["calls_last_24h"] == 0

    async def test_healthy_provider(
        self,
        fake_persistence: FakePersistenceBackend,
        fake_message_bus: FakeMessageBus,
    ) -> None:
        """Provider with all successful calls."""
        tracker = ProviderHealthTracker()
        for i in range(5):
            await tracker.record(
                _make_health_record(
                    timestamp=_NOW - timedelta(minutes=i),
                    response_time_ms=100.0 + i * 10,
                ),
            )
        with _build_provider_client(
            fake_persistence=fake_persistence,
            fake_message_bus=fake_message_bus,
            provider_health_tracker=tracker,
        ) as client:
            resp = client.get(
                "/api/v1/providers/test-provider/health",
                headers=_HEADERS,
            )
            assert resp.status_code == 200
            data = resp.json()["data"]
            assert data["health_status"] == "up"
            assert data["calls_last_24h"] == 5
            assert data["error_rate_percent_24h"] == 0.0
            assert data["avg_response_time_ms"] is not None

    async def test_degraded_provider(
        self,
        fake_persistence: FakePersistenceBackend,
        fake_message_bus: FakeMessageBus,
    ) -> None:
        """Provider with 20% error rate -> degraded."""
        tracker = ProviderHealthTracker()
        for i in range(10):
            await tracker.record(
                _make_health_record(
                    timestamp=_NOW - timedelta(minutes=i),
                    success=i >= 2,  # 2 failures out of 10
                ),
            )
        with _build_provider_client(
            fake_persistence=fake_persistence,
            fake_message_bus=fake_message_bus,
            provider_health_tracker=tracker,
        ) as client:
            resp = client.get(
                "/api/v1/providers/test-provider/health",
                headers=_HEADERS,
            )
            assert resp.status_code == 200
            data = resp.json()["data"]
            assert data["health_status"] == "degraded"
            assert data["error_rate_percent_24h"] == 20.0

    async def test_down_provider(
        self,
        fake_persistence: FakePersistenceBackend,
        fake_message_bus: FakeMessageBus,
    ) -> None:
        """Provider with 100% error rate -> down."""
        tracker = ProviderHealthTracker()
        for i in range(3):
            await tracker.record(
                _make_health_record(
                    timestamp=_NOW - timedelta(minutes=i),
                    success=False,
                ),
            )
        with _build_provider_client(
            fake_persistence=fake_persistence,
            fake_message_bus=fake_message_bus,
            provider_health_tracker=tracker,
        ) as client:
            resp = client.get(
                "/api/v1/providers/test-provider/health",
                headers=_HEADERS,
            )
            assert resp.status_code == 200
            data = resp.json()["data"]
            assert data["health_status"] == "down"
            assert data["error_rate_percent_24h"] == 100.0
