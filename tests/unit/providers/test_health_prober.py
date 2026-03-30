"""Tests for ProviderHealthProber."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from synthorg.providers.health import (
    ProviderHealthStatus,
    ProviderHealthTracker,
)
from synthorg.providers.health_prober import (
    ProviderHealthProber,
    _build_ping_url,
)


@pytest.mark.unit
class TestBuildPingUrl:
    def test_ollama_returns_root(self) -> None:
        assert (
            _build_ping_url("http://localhost:11434", "ollama")
            == "http://localhost:11434"
        )

    def test_ollama_detected_by_port(self) -> None:
        assert _build_ping_url("http://host:11434/", None) == "http://host:11434"

    def test_standard_appends_models(self) -> None:
        assert (
            _build_ping_url("http://localhost:1234/v1", None)
            == "http://localhost:1234/v1/models"
        )

    def test_strips_trailing_slash(self) -> None:
        assert (
            _build_ping_url("http://localhost:8000/v1/", "test-api")
            == "http://localhost:8000/v1/models"
        )


@pytest.mark.unit
class TestProviderHealthProber:
    async def test_probe_records_success(self) -> None:
        tracker = ProviderHealthTracker()
        config_resolver = MagicMock()

        mock_config = MagicMock()
        mock_config.base_url = "http://localhost:11434"
        mock_config.litellm_provider = "ollama"
        mock_config.auth_type = "none"
        mock_config.api_key = None

        config_resolver.get_provider_configs = AsyncMock(
            return_value={"test-local": mock_config},
        )

        prober = ProviderHealthProber(
            tracker,
            config_resolver,
            interval_seconds=3600,
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.is_success = True

        _patch = "synthorg.providers.health_prober.httpx.AsyncClient"
        with patch(_patch) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            await prober._probe_all()

        summary = await tracker.get_summary("test-local")
        assert summary.health_status == ProviderHealthStatus.UP
        assert summary.calls_last_24h == 1

    async def test_probe_records_failure(self) -> None:
        tracker = ProviderHealthTracker()
        config_resolver = MagicMock()

        mock_config = MagicMock()
        mock_config.base_url = "http://localhost:11434"
        mock_config.litellm_provider = "ollama"
        mock_config.auth_type = "none"
        mock_config.api_key = None

        config_resolver.get_provider_configs = AsyncMock(
            return_value={"test-local": mock_config},
        )

        prober = ProviderHealthProber(
            tracker,
            config_resolver,
            interval_seconds=3600,
        )

        _patch = "synthorg.providers.health_prober.httpx.AsyncClient"
        with patch(_patch) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            await prober._probe_all()

        summary = await tracker.get_summary("test-local")
        assert summary.health_status == ProviderHealthStatus.DOWN
        assert summary.calls_last_24h == 1

    async def test_skips_cloud_providers(self) -> None:
        tracker = ProviderHealthTracker()
        config_resolver = MagicMock()

        mock_config = MagicMock()
        mock_config.base_url = None  # cloud provider

        config_resolver.get_provider_configs = AsyncMock(
            return_value={"test-cloud": mock_config},
        )

        prober = ProviderHealthProber(tracker, config_resolver)

        _patch = "synthorg.providers.health_prober.httpx.AsyncClient"
        with patch(_patch) as mock_client_cls:
            await prober._probe_all()
            mock_client_cls.assert_not_called()

    async def test_skips_recently_active_providers(self) -> None:
        tracker = ProviderHealthTracker()
        config_resolver = MagicMock()

        mock_config = MagicMock()
        mock_config.base_url = "http://localhost:11434"
        mock_config.litellm_provider = "ollama"
        mock_config.auth_type = "none"
        mock_config.api_key = None

        config_resolver.get_provider_configs = AsyncMock(
            return_value={"test-local": mock_config},
        )

        # Record a recent health record
        from synthorg.providers.health import ProviderHealthRecord

        await tracker.record(
            ProviderHealthRecord(
                provider_name="test-local",
                timestamp=datetime.now(UTC),
                success=True,
                response_time_ms=50.0,
            ),
        )

        prober = ProviderHealthProber(
            tracker,
            config_resolver,
            interval_seconds=3600,
        )

        _patch = "synthorg.providers.health_prober.httpx.AsyncClient"
        with patch(_patch) as mock_client_cls:
            await prober._probe_all()
            mock_client_cls.assert_not_called()
