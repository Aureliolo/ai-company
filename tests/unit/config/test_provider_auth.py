"""Tests for ProviderConfig auth type validation."""

import pytest
from pydantic import ValidationError

from synthorg.config.schema import ProviderConfig
from synthorg.providers.enums import AuthType


@pytest.mark.unit
class TestAuthTypeEnum:
    def test_auth_type_enum_values(self) -> None:
        assert AuthType.API_KEY.value == "api_key"
        assert AuthType.OAUTH.value == "oauth"
        assert AuthType.CUSTOM_HEADER.value == "custom_header"
        assert AuthType.NONE.value == "none"
        assert len(AuthType) == 4


@pytest.mark.unit
class TestProviderConfigAuth:
    def test_backward_compat_defaults_to_api_key(self) -> None:
        config = ProviderConfig(driver="litellm")
        assert config.auth_type == AuthType.API_KEY

    def test_oauth_valid(self) -> None:
        config = ProviderConfig(
            driver="litellm",
            auth_type=AuthType.OAUTH,
            oauth_token_url="https://auth.example.com/token",
            oauth_client_id="client-123",
            oauth_client_secret="secret-456",
        )
        assert config.auth_type == AuthType.OAUTH
        assert config.oauth_token_url == "https://auth.example.com/token"

    def test_oauth_missing_token_url_raises(self) -> None:
        with pytest.raises(ValidationError, match="oauth_token_url"):
            ProviderConfig(
                driver="litellm",
                auth_type=AuthType.OAUTH,
                oauth_client_id="client-123",
                oauth_client_secret="secret-456",
            )

    def test_oauth_missing_client_id_raises(self) -> None:
        with pytest.raises(ValidationError, match="oauth_client_id"):
            ProviderConfig(
                driver="litellm",
                auth_type=AuthType.OAUTH,
                oauth_token_url="https://auth.example.com/token",
                oauth_client_secret="secret-456",
            )

    def test_oauth_missing_client_secret_raises(self) -> None:
        with pytest.raises(ValidationError, match="oauth_client_secret"):
            ProviderConfig(
                driver="litellm",
                auth_type=AuthType.OAUTH,
                oauth_token_url="https://auth.example.com/token",
                oauth_client_id="client-123",
            )

    def test_custom_header_valid(self) -> None:
        config = ProviderConfig(
            driver="litellm",
            auth_type=AuthType.CUSTOM_HEADER,
            custom_header_name="X-Custom-Auth",
            custom_header_value="token-789",
        )
        assert config.auth_type == AuthType.CUSTOM_HEADER
        assert config.custom_header_name == "X-Custom-Auth"

    def test_custom_header_missing_name_raises(self) -> None:
        with pytest.raises(ValidationError, match="custom_header_name"):
            ProviderConfig(
                driver="litellm",
                auth_type=AuthType.CUSTOM_HEADER,
                custom_header_value="token-789",
            )

    def test_custom_header_missing_value_raises(self) -> None:
        with pytest.raises(ValidationError, match="custom_header_value"):
            ProviderConfig(
                driver="litellm",
                auth_type=AuthType.CUSTOM_HEADER,
                custom_header_name="X-Custom-Auth",
            )

    def test_none_auth_no_requirements(self) -> None:
        config = ProviderConfig(
            driver="litellm",
            auth_type=AuthType.NONE,
        )
        assert config.auth_type == AuthType.NONE

    def test_api_key_auth_no_extra_requirements(self) -> None:
        config = ProviderConfig(
            driver="litellm",
            auth_type=AuthType.API_KEY,
        )
        assert config.auth_type == AuthType.API_KEY
        assert config.api_key is None

    def test_oauth_with_optional_scope(self) -> None:
        config = ProviderConfig(
            driver="litellm",
            auth_type=AuthType.OAUTH,
            oauth_token_url="https://auth.example.com/token",
            oauth_client_id="client-123",
            oauth_client_secret="secret-456",
            oauth_scope="read write",
        )
        assert config.oauth_scope == "read write"

    def test_api_key_auth_stores_key(self) -> None:
        """API key auth stores the provided key on the config."""
        config = ProviderConfig(
            driver="litellm",
            auth_type=AuthType.API_KEY,
            api_key="sk-test-key-001",
        )
        assert config.auth_type == AuthType.API_KEY
        assert config.api_key == "sk-test-key-001"
