"""Tests for ProviderHealthProber."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from synthorg.providers.health import (
    ProviderHealthRecord,
    ProviderHealthStatus,
    ProviderHealthTracker,
)
from synthorg.providers.health_prober import (
    ProviderHealthProber,
    _build_auth_headers,
    _build_ping_url,
)


def _make_local_config(
    *,
    base_url: str = "http://localhost:11434",
    litellm_provider: str | None = "ollama",
    auth_type: str = "none",
    api_key: str | None = None,
) -> MagicMock:
    """Build a mock ProviderConfig for a local provider."""
    mock = MagicMock()
    mock.base_url = base_url
    mock.litellm_provider = litellm_provider
    mock.auth_type = auth_type
    mock.api_key = api_key
    return mock


@pytest.mark.unit
class TestBuildPingUrl:
    def test_root_url_provider_returns_root(self) -> None:
        # Provider type "ollama" uses root URL (liveness string)
        assert (
            _build_ping_url("http://localhost:11434", "ollama")
            == "http://localhost:11434"
        )

    def test_local_detected_by_port(self) -> None:
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
class TestBuildAuthHeaders:
    @pytest.mark.parametrize(
        ("auth_type", "api_key", "expected"),
        [
            ("api_key", "sk-123", {"Authorization": "Bearer sk-123"}),
            ("subscription", "sub-tok", {"Authorization": "Bearer sub-tok"}),
            ("api_key", None, {}),
            ("api_key", "", {}),
            ("none", "ignored", {}),
            ("oauth", "token", {}),
            ("custom_header", "val", {}),
        ],
        ids=[
            "api_key_with_key",
            "subscription_with_key",
            "api_key_none",
            "api_key_empty",
            "none_type",
            "oauth_type",
            "custom_header_type",
        ],
    )
    def test_header_construction(
        self,
        auth_type: str,
        api_key: str | None,
        expected: dict[str, str],
    ) -> None:
        assert _build_auth_headers(auth_type, api_key) == expected


@pytest.mark.unit
class TestProviderHealthProber:
    async def test_probe_records_success(self) -> None:
        tracker = ProviderHealthTracker()
        config_resolver = MagicMock()
        config_resolver.get_provider_configs = AsyncMock(
            return_value={"test-local": _make_local_config()},
        )

        prober = ProviderHealthProber(
            tracker,
            config_resolver,
            interval_seconds=3600,
        )

        mock_response = MagicMock()
        mock_response.status_code = 200

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
        config_resolver.get_provider_configs = AsyncMock(
            return_value={"test-local": _make_local_config()},
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

    async def test_probe_records_server_error(self) -> None:
        """HTTP 5xx responses are recorded as failures."""
        tracker = ProviderHealthTracker()
        config_resolver = MagicMock()
        config_resolver.get_provider_configs = AsyncMock(
            return_value={"test-local": _make_local_config()},
        )

        prober = ProviderHealthProber(
            tracker,
            config_resolver,
            interval_seconds=3600,
        )

        mock_response = MagicMock()
        mock_response.status_code = 503

        _patch = "synthorg.providers.health_prober.httpx.AsyncClient"
        with patch(_patch) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            await prober._probe_all()

        summary = await tracker.get_summary("test-local")
        assert summary.health_status == ProviderHealthStatus.DOWN

    async def test_probe_records_timeout(self) -> None:
        """Timeout exceptions are recorded as failures."""
        tracker = ProviderHealthTracker()
        config_resolver = MagicMock()
        config_resolver.get_provider_configs = AsyncMock(
            return_value={"test-local": _make_local_config()},
        )

        prober = ProviderHealthProber(
            tracker,
            config_resolver,
            interval_seconds=3600,
        )

        _patch = "synthorg.providers.health_prober.httpx.AsyncClient"
        with patch(_patch) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(
                side_effect=httpx.ReadTimeout("probe timeout"),
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            await prober._probe_all()

        summary = await tracker.get_summary("test-local")
        assert summary.health_status == ProviderHealthStatus.DOWN

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
        config_resolver.get_provider_configs = AsyncMock(
            return_value={"test-local": _make_local_config()},
        )

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

    def test_invalid_interval_raises(self) -> None:
        """interval_seconds < 1 raises ValueError."""
        tracker = ProviderHealthTracker()
        config_resolver = MagicMock()
        with pytest.raises(ValueError, match=r"interval_seconds must be >= 1"):
            ProviderHealthProber(
                tracker,
                config_resolver,
                interval_seconds=0,
            )

    def test_negative_interval_raises(self) -> None:
        tracker = ProviderHealthTracker()
        config_resolver = MagicMock()
        with pytest.raises(ValueError, match=r"interval_seconds must be >= 1"):
            ProviderHealthProber(
                tracker,
                config_resolver,
                interval_seconds=-5,
            )
