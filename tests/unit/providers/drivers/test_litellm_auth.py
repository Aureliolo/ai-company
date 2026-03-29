"""Tests for LiteLLM driver multi-auth support."""

from datetime import UTC, datetime
from typing import Any

import pytest

from synthorg.config.schema import ProviderConfig, ProviderModelConfig
from synthorg.core.resilience_config import RateLimiterConfig, RetryConfig
from synthorg.providers.drivers.litellm_driver import LiteLLMDriver
from synthorg.providers.enums import AuthType, MessageRole
from synthorg.providers.models import ChatMessage


def _make_config(
    *,
    auth_type: AuthType = AuthType.API_KEY,
    api_key: str | None = None,
    base_url: str | None = None,
    custom_header_name: str | None = None,
    custom_header_value: str | None = None,
    **kwargs: Any,
) -> ProviderConfig:
    """Build a ProviderConfig with auth fields for testing."""
    return ProviderConfig(
        driver="litellm",
        auth_type=auth_type,
        api_key=api_key,
        base_url=base_url,
        custom_header_name=custom_header_name,
        custom_header_value=custom_header_value,
        models=(
            ProviderModelConfig(
                id="test-model-001",
                alias="medium",
            ),
        ),
        retry=RetryConfig(max_retries=0),
        rate_limiter=RateLimiterConfig(),
        **kwargs,
    )


def _build_kwargs(config: ProviderConfig) -> dict[str, Any]:
    """Extract _build_kwargs result from a driver."""
    driver = LiteLLMDriver("test-provider", config)
    messages = [ChatMessage(role=MessageRole.USER, content="ping")]
    return driver._build_kwargs(
        messages,
        "test-provider/test-model-001",
    )


@pytest.mark.unit
class TestLiteLLMDriverAuth:
    def test_build_kwargs_api_key_auth(self) -> None:
        config = _make_config(
            auth_type=AuthType.API_KEY,
            api_key="sk-test",
        )
        kwargs = _build_kwargs(config)
        assert kwargs["api_key"] == "sk-test"

    def test_build_kwargs_api_key_none_omitted(self) -> None:
        config = _make_config(
            auth_type=AuthType.API_KEY,
            api_key=None,
        )
        kwargs = _build_kwargs(config)
        assert "api_key" not in kwargs

    def test_build_kwargs_custom_header_auth(self) -> None:
        config = _make_config(
            auth_type=AuthType.CUSTOM_HEADER,
            custom_header_name="X-Api-Token",
            custom_header_value="my-token",
        )
        kwargs = _build_kwargs(config)
        assert kwargs["extra_headers"] == {"X-Api-Token": "my-token"}
        assert "api_key" not in kwargs

    def test_build_kwargs_none_auth(self) -> None:
        config = _make_config(auth_type=AuthType.NONE)
        kwargs = _build_kwargs(config)
        assert "api_key" not in kwargs
        assert "extra_headers" not in kwargs

    def test_build_kwargs_oauth_passes_api_key(self) -> None:
        config = _make_config(
            auth_type=AuthType.OAUTH,
            api_key="oauth-token-123",
            oauth_token_url="https://auth.example.com/token",
            oauth_client_id="client-id",
            oauth_client_secret="client-secret",
        )
        kwargs = _build_kwargs(config)
        assert kwargs["api_key"] == "oauth-token-123"

    def test_build_kwargs_base_url_always_set(self) -> None:
        config = _make_config(
            auth_type=AuthType.NONE,
            base_url="http://localhost:11434",
        )
        kwargs = _build_kwargs(config)
        assert kwargs["api_base"] == "http://localhost:11434"

    def test_build_kwargs_no_base_url_omitted(self) -> None:
        config = _make_config(auth_type=AuthType.NONE)
        kwargs = _build_kwargs(config)
        assert "api_base" not in kwargs

    def test_build_kwargs_oauth_no_token_omits_api_key(self) -> None:
        """OAuth auth without a pre-fetched token omits api_key from kwargs."""
        config = _make_config(
            auth_type=AuthType.OAUTH,
            api_key=None,
            oauth_token_url="https://auth.example.com/token",
            oauth_client_id="client-id",
            oauth_client_secret="client-secret",
        )
        kwargs = _build_kwargs(config)
        assert "api_key" not in kwargs

    def test_build_kwargs_subscription_sets_api_key(self) -> None:
        """Subscription auth passes token as api_key for LiteLLM.

        ``api_key`` is the correct kwarg for authentication.
        ``auth_token`` is NOT a ``litellm.completion()`` parameter
        and would be silently discarded.
        """
        config = _make_config(
            auth_type=AuthType.SUBSCRIPTION,
            subscription_token="test-subscription-token",
            tos_accepted_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        kwargs = _build_kwargs(config)
        assert kwargs["api_key"] == "test-subscription-token"
        assert "auth_token" not in kwargs
        assert "extra_headers" not in kwargs

    def test_build_kwargs_subscription_no_token_skips_api_key(self) -> None:
        """Subscription auth without a token omits api_key."""
        config = _make_config(
            auth_type=AuthType.SUBSCRIPTION,
            subscription_token="test-subscription-token",
            tos_accepted_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        # Bypass frozen model to simulate a runtime-cleared token.
        # model_copy(update=...) is the normal convention, but here the
        # _validate_auth_fields validator rejects None for subscription
        # auth.  object.__setattr__ is the only way to test this branch.
        object.__setattr__(config, "subscription_token", None)
        kwargs = _build_kwargs(config)
        assert "api_key" not in kwargs
        assert "auth_token" not in kwargs
