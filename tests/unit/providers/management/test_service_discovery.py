"""Tests for provider discovery and trust resolution."""

from unittest.mock import AsyncMock, patch

import pytest

from synthorg.api.dto import CreateFromPresetRequest
from synthorg.config.schema import ProviderModelConfig
from synthorg.providers.enums import AuthType
from synthorg.providers.errors import ProviderNotFoundError
from synthorg.providers.management.service import ProviderManagementService

from .conftest import make_create_request


@pytest.mark.unit
class TestDiscoverModelsForProvider:
    """Tests for discover_models_for_provider."""

    async def test_discover_models_updates_provider(
        self,
        service: ProviderManagementService,
    ) -> None:
        """Discovery with results updates the provider config."""
        await service.create_provider(
            make_create_request(
                base_url="http://localhost:11434",
            ),
        )
        discovered = (
            ProviderModelConfig(id="ollama/test-model-a"),
            ProviderModelConfig(id="ollama/test-model-b"),
        )
        with patch(
            "synthorg.providers.management.service.discover_models",
            new_callable=AsyncMock,
            return_value=discovered,
        ):
            result = await service.discover_models_for_provider(
                "test-provider",
            )

        assert result == discovered
        # Verify the provider was updated with discovered models.
        updated = await service.get_provider("test-provider")
        assert updated.models == discovered

    async def test_discover_models_no_base_url_returns_empty(
        self,
        service: ProviderManagementService,
    ) -> None:
        """Provider with no base_url returns empty tuple without discovery."""
        await service.create_provider(
            make_create_request(base_url=None),
        )
        result = await service.discover_models_for_provider(
            "test-provider",
        )
        assert result == ()

    async def test_discover_models_provider_not_found_raises(
        self,
        service: ProviderManagementService,
    ) -> None:
        """Non-existent provider name raises ProviderNotFoundError."""
        with pytest.raises(ProviderNotFoundError, match="not found"):
            await service.discover_models_for_provider("nonexistent")

    async def test_discover_models_empty_result_no_update(
        self,
        service: ProviderManagementService,
    ) -> None:
        """Empty discovery result does not call update_provider."""
        await service.create_provider(
            make_create_request(
                base_url="http://localhost:11434",
            ),
        )
        with patch(
            "synthorg.providers.management.service.discover_models",
            new_callable=AsyncMock,
            return_value=(),
        ) as mock_discover:
            result = await service.discover_models_for_provider(
                "test-provider",
            )

        assert result == ()
        mock_discover.assert_awaited_once()
        # Original models should remain unchanged.
        original = await service.get_provider("test-provider")
        assert original.models == (
            ProviderModelConfig(
                id="test-model-001",
                alias="medium",
            ),
        )


@pytest.mark.unit
class TestCreateFromPresetAutoDiscovery:
    """Tests for auto-discovery in create_from_preset."""

    async def test_create_from_preset_auto_discovers_models(
        self,
        service: ProviderManagementService,
    ) -> None:
        """Preset with auth_type=none, empty models, and base_url triggers discovery."""
        discovered = (
            ProviderModelConfig(id="ollama/test-model-x"),
            ProviderModelConfig(id="ollama/test-model-y"),
        )
        with patch(
            "synthorg.providers.management.service.discover_models",
            new_callable=AsyncMock,
            return_value=discovered,
        ) as mock_discover:
            request = CreateFromPresetRequest(
                preset_name="ollama",
                name="my-ollama",
            )
            result = await service.create_from_preset(request)

        mock_discover.assert_awaited_once_with(
            "http://localhost:11434",
            "ollama",
            trust_url=True,
        )
        assert result.models == discovered

    async def test_create_from_preset_user_base_url_not_trusted(
        self,
        service: ProviderManagementService,
    ) -> None:
        """User-supplied base_url is NOT trusted (trust_url=False)."""
        discovered = (ProviderModelConfig(id="ollama/test-model-z"),)
        with patch(
            "synthorg.providers.management.service.discover_models",
            new_callable=AsyncMock,
            return_value=discovered,
        ) as mock_discover:
            request = CreateFromPresetRequest(
                preset_name="ollama",
                name="my-ollama",
                base_url="http://custom-host:11434",
            )
            result = await service.create_from_preset(request)

        mock_discover.assert_awaited_once_with(
            "http://custom-host:11434",
            "ollama",
            trust_url=False,
        )
        assert result.models == discovered


@pytest.mark.unit
class TestDiscoverModelsForProviderTrust:
    """Tests for trust logic in discover_models_for_provider."""

    async def test_valid_preset_hint_trusts_url(
        self,
        service: ProviderManagementService,
    ) -> None:
        """Valid preset_hint='ollama' results in trust_url=True."""
        await service.create_provider(
            make_create_request(
                base_url="http://localhost:11434",
            ),
        )
        with patch(
            "synthorg.providers.management.service.discover_models",
            new_callable=AsyncMock,
            return_value=(),
        ) as mock_discover:
            await service.discover_models_for_provider(
                "test-provider",
                preset_hint="ollama",
            )

        mock_discover.assert_awaited_once()
        call_kwargs = mock_discover.call_args
        assert call_kwargs.kwargs["trust_url"] is True

    async def test_invalid_preset_hint_does_not_trust_url(
        self,
        service: ProviderManagementService,
    ) -> None:
        """Invalid preset_hint='fake' results in trust_url=False."""
        await service.create_provider(
            make_create_request(
                base_url="http://localhost:11434",
            ),
        )
        with patch(
            "synthorg.providers.management.service.discover_models",
            new_callable=AsyncMock,
            return_value=(),
        ) as mock_discover:
            await service.discover_models_for_provider(
                "test-provider",
                preset_hint="fake",
            )

        mock_discover.assert_awaited_once()
        call_kwargs = mock_discover.call_args
        assert call_kwargs.kwargs["trust_url"] is False

    async def test_no_preset_hint_unknown_port_does_not_trust(
        self,
        service: ProviderManagementService,
    ) -> None:
        """No preset_hint with unrecognized port results in trust_url=False."""
        await service.create_provider(
            make_create_request(
                base_url="http://localhost:9999",
            ),
        )
        with patch(
            "synthorg.providers.management.service.discover_models",
            new_callable=AsyncMock,
            return_value=(),
        ) as mock_discover:
            await service.discover_models_for_provider(
                "test-provider",
            )

        mock_discover.assert_awaited_once()
        call_kwargs = mock_discover.call_args
        assert call_kwargs.kwargs["trust_url"] is False

    async def test_auth_type_none_unknown_port_does_not_trust(
        self,
        service: ProviderManagementService,
    ) -> None:
        """auth_type=none with unrecognized port does NOT trust the URL."""
        await service.create_provider(
            make_create_request(
                auth_type=AuthType.NONE,
                base_url="http://localhost:9999",
            ),
        )
        with patch(
            "synthorg.providers.management.service.discover_models",
            new_callable=AsyncMock,
            return_value=(),
        ) as mock_discover:
            await service.discover_models_for_provider(
                "test-provider",
            )

        mock_discover.assert_awaited_once()
        call_kwargs = mock_discover.call_args
        assert call_kwargs.kwargs["trust_url"] is False

    async def test_port_inferred_trust_for_known_preset_url(
        self,
        service: ProviderManagementService,
    ) -> None:
        """Port 11434 infers 'ollama' and localhost URL matches candidate_urls."""
        await service.create_provider(
            make_create_request(
                base_url="http://localhost:11434",
            ),
        )
        with patch(
            "synthorg.providers.management.service.discover_models",
            new_callable=AsyncMock,
            return_value=(),
        ) as mock_discover:
            await service.discover_models_for_provider(
                "test-provider",
            )

        mock_discover.assert_awaited_once()
        call_kwargs = mock_discover.call_args
        assert call_kwargs.kwargs["trust_url"] is True

    async def test_port_inferred_trust_for_docker_internal(
        self,
        service: ProviderManagementService,
    ) -> None:
        """Port 11434 infers 'ollama'; docker.internal matches candidates."""
        await service.create_provider(
            make_create_request(
                base_url="http://host.docker.internal:11434",
            ),
        )
        with patch(
            "synthorg.providers.management.service.discover_models",
            new_callable=AsyncMock,
            return_value=(),
        ) as mock_discover:
            await service.discover_models_for_provider(
                "test-provider",
            )

        mock_discover.assert_awaited_once()
        call_kwargs = mock_discover.call_args
        assert call_kwargs.kwargs["trust_url"] is True

    async def test_port_inferred_hint_mismatched_url_no_trust(
        self,
        service: ProviderManagementService,
    ) -> None:
        """Port 11434 infers 'ollama' but arbitrary host is not trusted."""
        await service.create_provider(
            make_create_request(
                base_url="http://evil.example.com:11434",
            ),
        )
        with patch(
            "synthorg.providers.management.service.discover_models",
            new_callable=AsyncMock,
            return_value=(),
        ) as mock_discover:
            await service.discover_models_for_provider(
                "test-provider",
            )

        mock_discover.assert_awaited_once()
        call_kwargs = mock_discover.call_args
        assert call_kwargs.kwargs["trust_url"] is False
